import os
import glob
import json
import shutil
import zipfile
from datetime import datetime
from pathlib import Path

from django.conf import settings
from django.core.files.storage import FileSystemStorage
from django.http import JsonResponse
from django.shortcuts import render, redirect
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth import authenticate, login, logout, get_user_model

# Imaging
try:
    from PIL import Image
except Exception:
    Image = None

# YOLO (Ultralytics)
try:
    from ultralytics import YOLO
except Exception:
    YOLO = None

# For saving annotated frames
try:
    import cv2
except Exception:
    cv2 = None

User = get_user_model()

# ----------------- Small helpers -----------------
def _urlify(p: str) -> str:
    if not p:
        return ""
    p = p.replace("\\", "/")
    return p if p.startswith("/") else f"/{p}"

def _ts() -> str:
    # yyyymmddHHMMSSmmm
    return datetime.utcnow().strftime("%Y%m%d%H%M%S%f")[:-3]

def _ensure(*dirs):
    for d in dirs:
        os.makedirs(d, exist_ok=True)

def unzip_file(zip_path: str, extract_to: str) -> None:
    _ensure(extract_to)
    with zipfile.ZipFile(zip_path, "r") as z:
        z.extractall(extract_to)

def zip_folder(src_folder: str, zip_path: str, extra_files: list[str] | None = None) -> None:
    _ensure(os.path.dirname(zip_path))
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
        for root, _, files in os.walk(src_folder):
            for f in files:
                abs_f = os.path.join(root, f)
                rel_f = os.path.relpath(abs_f, src_folder)
                z.write(abs_f, rel_f)
        # optionally add single files (e.g., geojson that sits outside src_folder)
        if extra_files:
            for abs_file, arcname in extra_files:
                if os.path.exists(abs_file):
                    z.write(abs_file, arcname)

_IMG_EXTS = (".jpg", ".jpeg", ".png", ".tif", ".tiff", ".bmp", ".gif", ".webp")
_PROCESSED_HINTS = {"result", "results", "processed", "output", "outputs"}

def _is_processed_like(path: str) -> bool:
    parts = Path(path).parts
    return any(seg.lower() in _PROCESSED_HINTS for seg in parts)

def _scan_images(root_dir: str):
    """Return (originals, processed_like) absolute paths (recursive)."""
    originals, processed = [], []
    for r, _, files in os.walk(root_dir):
        for fn in files:
            if fn.lower().endswith(_IMG_EXTS):
                p = os.path.join(r, fn)
                (processed if _is_processed_like(p) else originals).append(p)
    return originals, processed

def _name_index(paths):
    idx = {}
    for p in paths:
        idx.setdefault(os.path.basename(p).lower(), []).append(p)
    return idx

def _save_annotated(dst_path: str, annot_bgr):
    _ensure(os.path.dirname(dst_path))
    if annot_bgr is None:
        return False
    if cv2 is not None:
        try:
            cv2.imwrite(dst_path, annot_bgr)
            return True
        except Exception:
            pass
    try:
        from PIL import Image as _PILImage
        _PILImage.fromarray(annot_bgr[:, :, ::-1]).save(dst_path, quality=95)
        return True
    except Exception:
        return False

def _load_yolo_model(model_selection: str, model_name: str):
    """
    Load a YOLO .pt from:
      static/models/germany_summer_ai_model/
      static/models/germany_winter_ai_model/
    Returns (model_or_None, chosen_path_or_msg, error_msg)
    """
    if YOLO is None:
        return None, "", "ultralytics not installed"

    base = os.path.join(settings.BASE_DIR, "static", "models")
    model_dir = os.path.join(
        base, "germany_summer_ai_model" if model_selection == "summer" else "germany_winter_ai_model"
    )

    if model_name:
        cand = os.path.join(model_dir, model_name)
        if not os.path.exists(cand):
            return None, cand, f"model not found: {cand}"
        try:
            return YOLO(cand), cand, ""
        except Exception as e:
            return None, cand, f"failed to load model: {e}"

    pts = [f for f in os.listdir(model_dir)] if os.path.isdir(model_dir) else []
    pts = [os.path.join(model_dir, f) for f in pts if f.lower().endswith(".pt")]
    if not pts:
        return None, model_dir, f"no .pt file in {model_dir}"
    try:
        return YOLO(pts[0]), pts[0], ""
    except Exception as e:
        return None, pts[0], f"failed to load model: {e}"

def _pick_dir_to_zip(run_result_dir: str) -> str:
    """
    If run_result_dir has exactly one non-empty child dir (like 'Eichhalde_MA_Robert(1)'),
    return that child's absolute path. Otherwise return run_result_dir.
    """
    if not os.path.isdir(run_result_dir):
        return run_result_dir
    children = [d for d in os.listdir(run_result_dir)
                if os.path.isdir(os.path.join(run_result_dir, d))]
    non_empty = [d for d in children if any(os.scandir(os.path.join(run_result_dir, d)))]
    if len(non_empty) == 1:
        return os.path.join(run_result_dir, non_empty[0])
    return run_result_dir

def _save_run_json(run_id: str, label: str, zipped_dir_abs: str, zip_rel: str,
                   output_images: list, all_output_files: list, geojson_rel: str) -> str:
    """Write a per-run JSON and update runs_index.json. Return json_rel."""
    json_rel = os.path.join("static", "json", f"{run_id}.json")
    json_abs = os.path.join(settings.BASE_DIR, json_rel)

    record = {
        "run_id": run_id,
        "label": label,
        "created_at": datetime.utcnow().isoformat() + "Z",
        "zipped_dir": _urlify(os.path.relpath(zipped_dir_abs, settings.BASE_DIR)),
        "zip_path": _urlify(zip_rel),
        "result_dir": _urlify(os.path.join("static", "result", run_id)),
        "output_images": output_images,
        "all_output_files": all_output_files,
        "geojson_path": _urlify(geojson_rel) if geojson_rel else "",
    }
    _ensure(os.path.dirname(json_abs))
    with open(json_abs, "w", encoding="utf-8") as f:
        json.dump(record, f, indent=2)

    # update master index
    index_abs = os.path.join(settings.BASE_DIR, "static", "json", "runs_index.json")
    try:
        with open(index_abs, "r", encoding="utf-8") as f:
            idx = json.load(f)
    except Exception:
        idx = {}
    runs = idx.get("runs", {})
    runs[run_id] = record
    idx["runs"] = runs
    idx["updated_at"] = datetime.utcnow().isoformat() + "Z"
    with open(index_abs, "w", encoding="utf-8") as f:
        json.dump(idx, f, indent=2)

    return json_rel

def _find_geojson_for_run(run_result_dir: str, run_id: str) -> tuple[str, list[tuple[str, str]]]:
    """
    Try to locate a geojson produced for this run.
    Priority:
      1) Any *.geojson inside run_result_dir (recursive). If many, prefer file
         named like run_id*.geojson or 'tiff_output.geojson' / 'output.geojson'.
      2) Legacy fallbacks at static/tiff_output.geojson or static/output.geojson.
    If we find a legacy file outside the run dir, we COPY it into the run dir
    as <run_id>.geojson so it’s per-run and can be zipped. Returns:
        (geojson_rel_path_from_base, extra_zip_files)
    where extra_zip_files is a list of (abs_path, arcname) to force-add into the zip.
    """
    base = settings.BASE_DIR
    # Search inside run dir
    best_abs = ""
    candidates = []
    for r, _, files in os.walk(run_result_dir):
        for fn in files:
            if fn.lower().endswith(".geojson"):
                p = os.path.join(r, fn)
                candidates.append(p)

    def score(fn: str) -> int:
        f = os.path.basename(fn).lower()
        s = 0
        if run_id.lower() in f:
            s += 10
        if "tiff" in f:   s += 3
        if "output" in f: s += 2
        return s

    if candidates:
        best_abs = sorted(candidates, key=score, reverse=True)[0]
        rel = os.path.relpath(best_abs, base)
        return rel.replace("\\", "/"), []  # no extra zip files; it’s already under the run

    # Legacy fallback(s)
    legacy_list = [
        os.path.join(base, "static", "tiff_output.geojson"),
        os.path.join(base, "static", "output.geojson"),
    ]
    legacy = next((p for p in legacy_list if os.path.exists(p)), "")

    if legacy:
        # Copy into run dir as <run_id>.geojson so it becomes run-scoped
        dst_abs = os.path.join(run_result_dir, f"{run_id}.geojson")
        try:
            shutil.copyfile(legacy, dst_abs)
            rel = os.path.relpath(dst_abs, base).replace("\\", "/")
            # also ensure it goes into the zip even if we zip a nested subfolder
            return rel, [(dst_abs, f"{run_id}.geojson")]
        except Exception:
            # if copy fails, just return legacy path
            rel = os.path.relpath(legacy, base).replace("\\", "/")
            return rel, [(legacy, f"{run_id}.geojson")]  # still add to zip with nice name

    # Nothing found
    return "", []

# ----------------- Auth (unchanged) -----------------
@csrf_exempt
def signup_request(request):
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
def login_request(request):
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
def logout_request(request):
    logout(request)
    return redirect("login")

# ----------------- Model mgmt (unchanged) -----------------
@csrf_exempt
def model_upload(request):
    if request.method == "POST":
        user_model_file = request.FILES.get("model_path")
        model_selection = request.POST.get("model", "").strip()
        if not user_model_file or model_selection not in {"summer", "winter"}:
            return JsonResponse({"status": False, "error": "send valid request"})

        base = os.path.join(settings.BASE_DIR, "static", "models")
        dst_dir = os.path.join(base, "germany_summer_ai_model" if model_selection == "summer" else "germany_winter_ai_model")
        _ensure(dst_dir)
        FileSystemStorage(location=dst_dir).save(user_model_file.name, user_model_file)
        return JsonResponse({"status": True, "message": "Model Upload Successfully"})

    summer_dir = os.path.join(settings.BASE_DIR, "static", "models", "germany_summer_ai_model")
    winter_dir = os.path.join(settings.BASE_DIR, "static", "models", "germany_winter_ai_model")
    return JsonResponse({
        "summer_path": os.listdir(summer_dir) if os.path.isdir(summer_dir) else [],
        "winter_path": os.listdir(winter_dir) if os.path.isdir(winter_dir) else [],
    })

@csrf_exempt
def model_upload1(request):
    model = request.GET.get("model", "summer").strip()
    base = os.path.join(settings.BASE_DIR, "static", "models")
    target = os.path.join(base, "germany_summer_ai_model" if model == "summer" else "germany_winter_ai_model")
    return JsonResponse({"model_path": os.listdir(target) if os.path.isdir(target) else []})

@csrf_exempt
def delete_file(request):
    if request.method == "POST":
        filename = request.POST.get("filename", "").strip()
        for p in (
            os.path.join(settings.BASE_DIR, "static", "models", "germany_summer_ai_model", filename),
            os.path.join(settings.BASE_DIR, "static", "models", "germany_winter_ai_model", filename),
        ):
            if os.path.exists(p):
                os.remove(p)
                return JsonResponse({"success": True})
        return JsonResponse({"success": False, "error": "File not found"})
    return JsonResponse({"success": False, "error": "Invalid request"})

# ----------------- Main flow (YOLO + images + downloads) -----------------
@csrf_exempt
def index(request):
    """
    POST:
      - file (zip of images, nested ok)
      - tif_file (optional)
      - model ('summer'|'winter')
      - model_name (filename in the model folder)
      - label (optional) -> stored in per-run JSON

    Returns JSON:
      - input_image_list, output_image_list, zip_path, geojson_path, json_path
      - aliases: input_img, op_img, download_zip, download_geojson
    """
    base_static = os.path.join(settings.BASE_DIR, "static")
    input_root  = os.path.join(base_static, "input_img")
    result_root = os.path.join(base_static, "result")
    zip_root    = os.path.join(base_static, "zip")
    json_root   = os.path.join(base_static, "json")
    logs_root   = os.path.join(base_static, "logs")
    _ensure(input_root, result_root, zip_root, json_root, logs_root)

    if request.method == "POST":
        try:
            # Do NOT delete static/result anymore; keep history.
            # Optionally clear previous temp inputs:
            for f in glob.glob(os.path.join(settings.BASE_DIR, "static", "input_img", "*")):
                if os.path.isdir(f):
                    shutil.rmtree(f, ignore_errors=True)

            folder_name = _ts()
            run_input_dir = os.path.join(input_root, folder_name)
            run_result_dir = os.path.join(result_root, folder_name)
            _ensure(run_input_dir, run_result_dir)

            # receive
            zip_file = request.FILES.get("file")
            tif_file = request.FILES.get("tif_file")
            model_selection = request.POST.get("model", "summer").strip()
            model_name = request.POST.get("model_name", "").strip()
            label      = request.POST.get("label", "").strip()

            if zip_file:
                FileSystemStorage(location=run_input_dir).save(zip_file.name, zip_file)
                unzip_file(os.path.join(run_input_dir, zip_file.name), run_input_dir)
            if tif_file:
                FileSystemStorage(location=run_input_dir).save(tif_file.name, tif_file)

            originals_abs, processed_abs_in_zip = _scan_images(run_input_dir)
            processed_idx = _name_index(processed_abs_in_zip)

            # YOLO load (optional)
            model, chosen_model_path, yolo_error = _load_yolo_model(model_selection, model_name)

            input_image_list = []
            output_image_list = []

            for abs_img in originals_abs:
                rel = os.path.relpath(abs_img, run_input_dir)  # keep nested structure
                dst = os.path.join(run_result_dir, rel)
                _ensure(os.path.dirname(dst))

                annotated_ok = False

                # Try YOLO
                if YOLO is not None and model is not None and not yolo_error:
                    try:
                        if Image is not None:
                            _ = Image.open(abs_img)  # validates image
                        results = model.predict(
                            source=abs_img, conf=0.25, iou=0.45, imgsz=1024, device="cpu", verbose=False
                        )
                        if results and len(results) > 0:
                            annot_bgr = results[0].plot()
                            annotated_ok = _save_annotated(dst, annot_bgr)
                    except Exception:
                        annotated_ok = False

                # Use pre-annotated file from ZIP if present (by basename)
                if not annotated_ok:
                    base = os.path.basename(abs_img).lower()
                    if base in processed_idx:
                        try:
                            shutil.copyfile(processed_idx[base][0], dst)
                            annotated_ok = True
                        except Exception:
                            annotated_ok = False

                # Last fallback: copy original so UI still shows something
                if not annotated_ok:
                    shutil.copyfile(abs_img, dst)

                input_image_list.append(_urlify(f"static/input_img/{folder_name}/{rel}"))
                output_image_list.append(_urlify(f"static/result/{folder_name}/{rel}"))

            # -------- figure out GeoJSON (prefer run-scoped; fallback to legacy) --------
            geojson_rel, extra_zip_files = _find_geojson_for_run(run_result_dir, folder_name)

            # -------- ZIP THE RESULT (not the input) --------
            to_zip_abs = _pick_dir_to_zip(run_result_dir)
            # if we copied legacy geojson into run root but we’re zipping a nested child,
            # we must force-add the geojson to the zip
            extras = []
            if geojson_rel:
                geo_abs = os.path.join(settings.BASE_DIR, geojson_rel)
                if not geo_abs.startswith(to_zip_abs):
                    # arcname at top level of zip
                    extras.append((geo_abs, os.path.basename(geo_abs)))
            # plus anything _find_geojson_for_run wanted to force add
            extras.extend(extra_zip_files)

            zip_rel = os.path.join("static", "zip", f"{folder_name}.zip")
            zip_folder(to_zip_abs, os.path.join(settings.BASE_DIR, zip_rel), extras)

            # Collect lists for JSON (walk the chosen folder we zipped)
            all_out_files = []
            img_out_files = []
            for r, _, files in os.walk(to_zip_abs):
                for fn in files:
                    p_abs = os.path.join(r, fn)
                    rel_from_ziproot = os.path.relpath(p_abs, to_zip_abs)
                    rel_url = _urlify(os.path.join("static", "result", folder_name, rel_from_ziproot))
                    all_out_files.append(rel_url)
                    if fn.lower().endswith(_IMG_EXTS):
                        img_out_files.append(rel_url)

            # -------- Per-run JSON + master index --------
            per_run_json_rel = _save_run_json(
                folder_name, label, to_zip_abs, zip_rel, img_out_files, all_out_files, geojson_rel
            )

            # (Optional legacy file some UIs read)
            legacy_json_rel = os.path.join("static", "json", "output.json")
            with open(os.path.join(settings.BASE_DIR, legacy_json_rel), "w") as jf:
                json.dump({"final_result": output_image_list}, jf)

            # Final response: exact keys + aliases
            # If no geojson found, we keep empty string (or you can default to /static/tiff_output.geojson)
            download_geo = _urlify(geojson_rel) if geojson_rel else "/static/tiff_output.geojson"
            payload = {
                "status": True,
                "error": "" if input_image_list else "No images found in the uploaded archive.",
                "label": label,
                "geojson_path": download_geo,
                "zip_path": _urlify(zip_rel),                 # zip of RESULT
                "input_image_list": input_image_list,
                "output_image_list": output_image_list,       # full list of produced images
                "json_path": _urlify(per_run_json_rel),       # UNIQUE per run
                # aliases many frontends expect
                "input_img": input_image_list,
                "op_img": output_image_list,
                "download_zip": _urlify(zip_rel),
                "download_geojson": download_geo,
            }
            return JsonResponse(payload)

        except Exception as e:
            return JsonResponse({
                "status": False,
                "error": f"{type(e).__name__}: {e}",
                "geojson_path": "",
                "zip_path": "",
                "input_image_list": [],
                "output_image_list": [],
                "json_path": "",
                "input_img": [],
                "op_img": [],
                "download_zip": "",
                "download_geojson": "",
            })

    # GET -> landing page
    return render(request, "index.html")

# ----------------- GeoJSON helper (compat) -----------------
@csrf_exempt
def geo_json_path(request):
    """
    Return the latest run's geojson if present, otherwise the legacy files.
    Shape matches your previous contract.
    """
    try:
        base = os.path.join(settings.BASE_DIR, "static")
        result_root = os.path.join(base, "result")
        latest_geo_path = ""
        if os.path.isdir(result_root):
            # newest run first
            runs = [d for d in os.listdir(result_root) if os.path.isdir(os.path.join(result_root, d))]
            runs.sort(reverse=True)
            for rid in runs:
                run_dir = os.path.join(result_root, rid)
                # prefer a file named like run or legacy names under this run
                candidates = []
                for r, _, files in os.walk(run_dir):
                    for fn in files:
                        if fn.lower().endswith(".geojson"):
                            candidates.append(os.path.join(r, fn))
                if candidates:
                    # pick the most relevant one
                    def score(fn):
                        f = os.path.basename(fn).lower()
                        s = 0
                        if rid.lower() in f: s += 10
                        if "tiff" in f:      s += 3
                        if "output" in f:    s += 2
                        return s
                    best = sorted(candidates, key=score, reverse=True)[0]
                    latest_geo_path = os.path.relpath(best, settings.BASE_DIR).replace("\\", "/")
                    break

        # If still nothing, fall back to legacy locations
        if not latest_geo_path:
            for cand in ("static/tiff_output.geojson", "static/output.geojson"):
                if os.path.exists(os.path.join(settings.BASE_DIR, cand)):
                    latest_geo_path = cand
                    break

        geojson_data = {}
        tiff_geojson_data = {}
        output_geo = os.path.join(settings.BASE_DIR, "static", "output.geojson")
        tiff_geo = os.path.join(settings.BASE_DIR, "static", "tiff_output.geojson")

        if os.path.exists(output_geo):
            with open(output_geo, "r", encoding="utf-8") as f:
                geojson_data = json.load(f)
        if os.path.exists(tiff_geo):
            with open(tiff_geo, "r", encoding="utf-8") as f:
                tiff_geojson_data = json.load(f)

        return JsonResponse({
            "geo_path": "static/output.geojson",
            "geojson_data": geojson_data,
            "tiff_geo_path": latest_geo_path or "static/tiff_output.geojson",
            "tiff_geojson_data": tiff_geojson_data if latest_geo_path.endswith("tiff_output.geojson") else tiff_geojson_data,
        })
    except Exception as e:
        return JsonResponse({"status": False, "error": str(e)})
