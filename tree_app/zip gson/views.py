import os
import glob
import json
import shutil
import zipfile
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional

from django.conf import settings
from django.http import JsonResponse, HttpRequest, HttpResponse
from django.shortcuts import render, redirect
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods, require_GET
from django.contrib.auth import authenticate, login, logout, get_user_model

# ---- Optional deps (safe if missing) ----
try:
    from ultralytics import YOLO  # type: ignore
except Exception:
    YOLO = None

try:
    import cv2  # type: ignore
except Exception:
    cv2 = None

try:
    from PIL import Image as PILImage  # type: ignore
except Exception:
    PILImage = None

User = get_user_model()

# ---------------- paths & helpers ----------------
BASE_DIR   = settings.BASE_DIR
STATIC_DIR = os.path.join(BASE_DIR, "static")
INPUT_ROOT = os.path.join(STATIC_DIR, "input_img")
RESULT_ROOT= os.path.join(STATIC_DIR, "result")
ZIP_ROOT   = os.path.join(STATIC_DIR, "zip")

def _ensure(*dirs):
    for d in dirs:
        os.makedirs(d, exist_ok=True)

_ensure(INPUT_ROOT, RESULT_ROOT, ZIP_ROOT)

def _urlify(p: str) -> str:
    if not p: return ""
    p = p.replace("\\", "/")
    return p if p.startswith("/") else f"/{p}"

def _ts() -> str:
    dt, micro = datetime.utcnow().strftime("%Y%m%d%H%M%S.%f").split(".")
    return f"{dt}{int(micro)//1000:03d}"

def _scan_images(root_dir: str) -> List[str]:
    imgs = []
    for r, _, files in os.walk(root_dir):
        for fn in files:
            if fn.lower().endswith((".jpg", ".jpeg", ".png")):
                imgs.append(os.path.join(r, fn))
    return imgs

def _zip_folder_with_extra(src_folder: str, zip_abs_path: str, extra_files: List[str]) -> None:
    """Zip src_folder, then add extra_files at the root of the zip."""
    _ensure(os.path.dirname(zip_abs_path))
    with zipfile.ZipFile(zip_abs_path, "w", zipfile.ZIP_DEFLATED) as z:
        for root, _, files in os.walk(src_folder):
            for f in files:
                abs_f = os.path.join(root, f)
                rel_f = os.path.relpath(abs_f, src_folder)
                z.write(abs_f, rel_f)
        # add extras at root
        for ef in extra_files:
            if ef and os.path.exists(ef) and os.path.getsize(ef) > 0:
                z.write(ef, os.path.basename(ef))

def _save_json(abs_path: str, data) -> None:
    _ensure(os.path.dirname(abs_path))
    with open(abs_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

def _copy(src: str, dst: str) -> None:
    if os.path.abspath(src) != os.path.abspath(dst):
        _ensure(os.path.dirname(dst))
        shutil.copyfile(src, dst)

def _is_nonempty_geojson(p: str) -> bool:
    try:
        if not p or not os.path.exists(p) or os.path.getsize(p) <= 2:
            return False
        with open(p, "r", encoding="utf-8") as f:
            data = json.load(f)
        return isinstance(data, dict) and data.get("type") == "FeatureCollection"
    except Exception:
        return False

def _pick_geojson_for_run(run_result_dir: str) -> Optional[str]:
    """
    Best-geojson strategy (no blank file creation here):
      1) Any *.geojson INSIDE this run's result folder (prefer first)
      2) static/tiff_output.geojson if non-empty & valid
      3) existing static/output.geojson if non-empty & valid
      4) None  (caller may decide to create a tiny placeholder)
    """
    # 1)
    run_geojsons = sorted(glob.glob(os.path.join(run_result_dir, "*.geojson")))
    for gj in run_geojsons:
        if _is_nonempty_geojson(gj):
            return gj

    # 2)
    tiff_gj = os.path.join(STATIC_DIR, "tiff_output.geojson")
    if _is_nonempty_geojson(tiff_gj):
        return tiff_gj

    # 3)
    public_gj = os.path.join(STATIC_DIR, "output.geojson")
    if _is_nonempty_geojson(public_gj):
        return public_gj

    # 4) none
    return None

# ---------------- AUTH (unchanged) ----------------
@csrf_exempt
def signup_request(request: HttpRequest) -> HttpResponse:
    if request.method == "POST":
        username = request.POST.get("username", "").strip()
        email    = request.POST.get("email", "").strip()
        password = request.POST.get("password", "").strip()
        full_name= request.POST.get("full_name", "").strip()

        if not username or not email or not password:
            return JsonResponse({"status": False, "error": "Missing fields"})
        if User.objects.filter(username=username).exists():
            return JsonResponse({"status": False, "error": "This username already exist"})
        if User.objects.filter(email=email).exists():
            return JsonResponse({"status": False, "error": "This email already exist"})

        user = User.objects.create_user(username=username, email=email, password=password)
        if hasattr(user, "full_name") and full_name:
            user.full_name = full_name
            user.save()
        return JsonResponse({"status": True, "error": "", "message": "Signup successful"})
    return render(request, "signup.html")

@csrf_exempt
def login_request(request: HttpRequest) -> HttpResponse:
    if request.method == "POST":
        email = request.POST.get("email", "").strip()
        password = request.POST.get("password", "").strip()
        qs = User.objects.filter(email=email)
        if not qs.exists():
            return JsonResponse({"status": False, "error": "Invalid email or password"})
        username = qs.first().username
        user = authenticate(request, username=username, password=password)
        if user:
            login(request, user)
            return JsonResponse({
                "status": True, "error": "",
                "user_id": user.id, "username": user.username,
                "email": user.email, "full_name": getattr(user, "full_name", ""),
            })
        return JsonResponse({"status": False, "error": "Invalid email or password"})
    return render(request, "login.html")

@csrf_exempt
def logout_request(request: HttpRequest) -> HttpResponse:
    logout(request)
    return redirect("login")

# ---------------- Model mgmt (unchanged) ----------------
@csrf_exempt
def model_upload(request: HttpRequest) -> HttpResponse:
    if request.method == "POST":
        f = request.FILES.get("model_path")
        model_selection = request.POST.get("model", "").strip()
        if not f or model_selection not in {"summer", "winter"}:
            return JsonResponse({"status": False, "error": "send valid request"})

        dst_dir = os.path.join(
            STATIC_DIR, "models",
            "germany_summer_ai_model" if model_selection == "summer" else "germany_winter_ai_model"
        )
        _ensure(dst_dir)
        with open(os.path.join(dst_dir, f.name), "wb") as out:
            for chunk in f.chunks():
                out.write(chunk)
        return JsonResponse({"status": True, "message": "Model Upload Successfully"})

    summer_dir = os.path.join(STATIC_DIR, "models", "germany_summer_ai_model")
    winter_dir = os.path.join(STATIC_DIR, "models", "germany_winter_ai_model")
    return JsonResponse({
        "summer_path": os.listdir(summer_dir) if os.path.isdir(summer_dir) else [],
        "winter_path": os.listdir(winter_dir) if os.path.isdir(winter_dir) else [],
    })

@csrf_exempt
def model_upload1(request: HttpRequest) -> HttpResponse:
    model = request.GET.get("model", "summer").strip()
    target = os.path.join(STATIC_DIR, "models",
                          "germany_summer_ai_model" if model == "summer" else "germany_winter_ai_model")
    return JsonResponse({"model_path": os.listdir(target) if os.path.isdir(target) else []})

@csrf_exempt
def delete_file(request: HttpRequest) -> HttpResponse:
    if request.method == "POST":
        filename = (request.POST.get("filename") or "").strip()
        for p in (
            os.path.join(STATIC_DIR, "models", "germany_summer_ai_model", filename),
            os.path.join(STATIC_DIR, "models", "germany_winter_ai_model", filename),
        ):
            if os.path.exists(p):
                os.remove(p)
                return JsonResponse({"success": True})
        return JsonResponse({"success": False, "error": "File not found"})
    return JsonResponse({"success": False, "error": "Invalid request"})

# ---------------- PROCESS (no blank geojson overwrites) ----------------
@csrf_exempt
@require_http_methods(["GET", "POST"])
def index(request: HttpRequest) -> HttpResponse:
    if request.method == "GET":
        return render(request, "index.html")

    run_id = _ts()
    run_input_dir  = os.path.join(INPUT_ROOT, run_id)
    run_result_dir = os.path.join(RESULT_ROOT, run_id)
    _ensure(run_input_dir, run_result_dir)

    # receive files
    zip_file = request.FILES.get("file")
    tif_file = request.FILES.get("tif_file")
    model_selection = request.POST.get("model", "summer").strip()
    model_name = request.POST.get("model_name", "").strip()

    if zip_file:
        save_abs = os.path.join(run_input_dir, zip_file.name)
        with open(save_abs, "wb") as f:
            for c in zip_file.chunks():
                f.write(c)
        try:
            with zipfile.ZipFile(save_abs, "r") as z:
                z.extractall(run_input_dir)
        except Exception:
            pass

    if tif_file:
        tif_abs = os.path.join(run_input_dir, tif_file.name)
        with open(tif_abs, "wb") as f:
            for c in tif_file.chunks():
                f.write(c)

    # optional YOLO
    model = None
    if YOLO is not None:
        try:
            base_models = os.path.join(STATIC_DIR, "models")
            folder = "germany_summer_ai_model" if model_selection == "summer" else "germany_winter_ai_model"
            model_dir = os.path.join(base_models, folder)
            cand = os.path.join(model_dir, model_name) if model_name else None
            if not cand or not os.path.exists(cand):
                pts = [p for p in os.listdir(model_dir)] if os.path.isdir(model_dir) else []
                pts = [os.path.join(model_dir, p) for p in pts if p.lower().endswith(".pt")]
                cand = pts[0] if pts else None
            if cand and os.path.exists(cand):
                model = YOLO(cand)
        except Exception:
            model = None

    input_image_list: List[str] = []
    output_image_list: List[str] = []

    originals = _scan_images(run_input_dir)
    # also support single images at root
    if not originals:
        for fn in os.listdir(run_input_dir):
            if fn.lower().endswith((".jpg", ".jpeg", ".png")):
                originals.append(os.path.join(run_input_dir, fn))

    for abs_img in originals:
        rel = os.path.relpath(abs_img, run_input_dir)
        out_abs = os.path.join(run_result_dir, rel)
        _ensure(os.path.dirname(out_abs))

        wrote = False
        if model is not None and PILImage is not None and cv2 is not None:
            try:
                _ = PILImage.open(abs_img)
                res = model.predict(source=abs_img, conf=0.25, iou=0.45, imgsz=1024, device="cpu", verbose=False)
                if res and len(res) > 0:
                    cv2.imwrite(out_abs, res[0].plot())
                    wrote = True
            except Exception:
                wrote = False

        if not wrote:
            shutil.copyfile(abs_img, out_abs)

        input_image_list.append(_urlify(os.path.join("static", "input_img", run_id, rel)))
        output_image_list.append(_urlify(os.path.join("static", "result", run_id, rel)))

    # ---- Choose best GeoJSON for this run (never blank out a good one) ----
    chosen_geojson_abs = _pick_geojson_for_run(run_result_dir)
    if chosen_geojson_abs is None:
        # create a minimal placeholder ONLY if nothing exists anywhere
        chosen_geojson_abs = os.path.join(run_result_dir, f"{run_id}.geojson")
        _save_json(chosen_geojson_abs, {"type": "FeatureCollection", "features": []})

    # Update the public file ONLY by copying a non-empty, valid geojson
    public_geojson_abs = os.path.join(STATIC_DIR, "output.geojson")
    if _is_nonempty_geojson(chosen_geojson_abs):
        _copy(chosen_geojson_abs, public_geojson_abs)

    # ---- Build ZIP of OUTPUTS and include the geojson in the archive ----
    # If the chosen geojson is not inside the run folder, include it as <run_id>.geojson
    extras = []
    try:
        same_tree = os.path.commonpath([os.path.abspath(run_result_dir), os.path.abspath(chosen_geojson_abs)]) == os.path.abspath(run_result_dir)
    except Exception:
        same_tree = False
    if not same_tree and os.path.exists(chosen_geojson_abs):
        temp_copy = os.path.join(run_result_dir, f"{run_id}.geojson")
        try:
            _copy(chosen_geojson_abs, temp_copy)
            extras.append(temp_copy)  # if already inside run_result_dir, zip step will pick it anyway
        except Exception:
            pass

    zip_rel = os.path.join("static", "zip", f"{run_id}.zip")
    zip_abs = os.path.join(BASE_DIR, zip_rel)
    _zip_folder_with_extra(run_result_dir, zip_abs, extras)

    # ---- Response ----
    return JsonResponse({
        "status": True,
        "run_id": run_id,
        "zip_path": _urlify(zip_rel),
        "geojson_path": _urlify(os.path.relpath(public_geojson_abs, BASE_DIR)) if os.path.exists(public_geojson_abs) else "",
        "input_image_list": input_image_list,
        "output_image_list": output_image_list,
    })

# ---------------- HISTORY (filesystem scan) ----------------
@require_GET
def runs_history(request: HttpRequest) -> HttpResponse:
    """Return a list of runs scanning static/result/* (newest first)."""
    runs: List[Dict] = []
    if not os.path.isdir(RESULT_ROOT):
        return JsonResponse({"runs": runs})

    for d in os.listdir(RESULT_ROOT):
        run_dir = os.path.join(RESULT_ROOT, d)
        if not os.path.isdir(run_dir):
            continue

        # mtime as created_at
        try:
            mtime = os.path.getmtime(run_dir)
        except Exception:
            mtime = 0

        outs = []
        for r, _, files in os.walk(run_dir):
            for fn in files:
                if fn.lower().endswith((".jpg", ".jpeg", ".png")):
                    rel = os.path.relpath(os.path.join(r, fn), BASE_DIR)
                    outs.append(_urlify(rel))
        outs.sort()
        thumb = outs[0] if outs else ""

        # geojson selection for listing (prefer run-local)
        run_gj = _pick_geojson_for_run(run_dir) or os.path.join(STATIC_DIR, "output.geojson")
        gj_rel = _urlify(os.path.relpath(run_gj, BASE_DIR)) if os.path.exists(run_gj) else ""

        zip_rel = os.path.join("static", "zip", f"{d}.zip")
        if not os.path.exists(os.path.join(BASE_DIR, zip_rel)):
            zip_rel = ""

        runs.append({
            "id": d,
            "created_at": datetime.utcfromtimestamp(mtime).isoformat() + "Z",
            "zip_path": _urlify(zip_rel) if zip_rel else "",
            "geojson_path": gj_rel,
            "output_images": outs,
            "input_images": [],
            "thumbnail": thumb,
        })

    runs.sort(key=lambda x: x["created_at"], reverse=True)
    return JsonResponse({"runs": runs})

@require_GET
def runs_history_detail(request: HttpRequest, run_id: str) -> HttpResponse:
    run_dir = os.path.join(RESULT_ROOT, run_id)
    if not os.path.isdir(run_dir):
        return JsonResponse({"ok": False, "error": "not found"}, status=404)

    outs = []
    for r, _, files in os.walk(run_dir):
        for fn in files:
            if fn.lower().endswith((".jpg", ".jpeg", ".png")):
                rel = os.path.relpath(os.path.join(r, fn), BASE_DIR)
                outs.append(_urlify(rel))
    outs.sort()
    thumb = outs[0] if outs else ""

    run_gj = _pick_geojson_for_run(run_dir) or os.path.join(STATIC_DIR, "output.geojson")
    gj_rel = _urlify(os.path.relpath(run_gj, BASE_DIR)) if os.path.exists(run_gj) else ""

    zip_rel = os.path.join("static", "zip", f"{run_id}.zip")
    if not os.path.exists(os.path.join(BASE_DIR, zip_rel)):
        zip_rel = ""

    return JsonResponse({
        "ok": True,
        "run": {
            "id": run_id,
            "zip_path": _urlify(zip_rel) if zip_rel else "",
            "geojson_path": gj_rel,
            "output_images": outs,
            "thumbnail": thumb,
        },
    })

# ---------------- Single GeoJSON helper ----------------
@csrf_exempt
def geo_json_path(request: HttpRequest) -> HttpResponse:
    """
    Always serves the single public GeoJSON used by the map:
    /static/output.geojson
    """
    public_geojson = os.path.join(STATIC_DIR, "output.geojson")
    if not os.path.exists(public_geojson):
        _save_json(public_geojson, {"type": "FeatureCollection", "features": []})
    try:
        with open(public_geojson, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        data = {"type": "FeatureCollection", "features": []}
    return JsonResponse({
        "geo_path": "static/output.geojson",
        "geojson_data": data,
    })
