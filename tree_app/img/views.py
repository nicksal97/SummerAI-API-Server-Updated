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

# Optional libs (keep/remove as you need)
try:
    from ultralytics import YOLO  # if you actually run inference
except Exception:
    YOLO = None

try:
    import rasterio
except Exception:
    rasterio = None

User = get_user_model()

# -------- URL normalizer (important for frontend) --------
def _urlify(p: str) -> str:
    if not p:
        return ""
    p = p.replace("\\", "/")
    return p if p.startswith("/") else f"/{p}"


# ------------------------
# Utility helpers
# ------------------------
def get_date_time_for_naming() -> str:
    dt, micro = datetime.utcnow().strftime("%Y%m%d%H%M%S.%f").split(".")
    return f"{dt}{int(micro)/1000:03.0f}"

def unzip_file(zip_path: str, extract_to: str) -> None:
    os.makedirs(extract_to, exist_ok=True)
    with zipfile.ZipFile(zip_path, "r") as z:
        z.extractall(extract_to)

def tif_to_jgw_for_folder(folder_path: str) -> None:
    """Create .jgw files for all .tif/.tiff in a folder (non-recursive)."""
    if not rasterio:
        return
    for file in os.listdir(folder_path):
        if file.lower().endswith((".tif", ".tiff")):
            file_path = os.path.join(folder_path, file)
            file_name = Path(file).stem
            with rasterio.open(file_path) as src:
                transform = src.transform
            with open(os.path.join(folder_path, f"{file_name}.jgw"), "w") as jgw:
                jgw.write(f"{transform.a}\n")  # pixel width
                jgw.write(f"{transform.e}\n")  # pixel height
                jgw.write(f"{transform.c}\n")  # upper-left X
                jgw.write(f"{transform.f}\n")  # upper-left Y
                jgw.write("0.0\n")             # rotation
                jgw.write("0.0\n")

def zip_folder(src_folder: str, zip_path: str) -> None:
    os.makedirs(os.path.dirname(zip_path), exist_ok=True)
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
        for root, _, files in os.walk(src_folder):
            for f in files:
                abs_f = os.path.join(root, f)
                rel_f = os.path.relpath(abs_f, src_folder)
                z.write(abs_f, rel_f)


# ------------------------
# Auth endpoints
# ------------------------
@csrf_exempt
def signup_request(request):
    if request.method == "POST":
        username = request.POST.get("username", "").strip()
        email = request.POST.get("email", "").strip()
        password = request.POST.get("password", "").strip()
        full_name = request.POST.get("full_name", "").strip()

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
                "status": True,
                "error": "",
                "user_id": user.id,
                "username": user.username,
                "email": user.email,
                "full_name": getattr(user, "full_name", ""),
            })
        return JsonResponse({"status": False, "error": "Invalid email or password"})
    return render(request, "login.html")


@csrf_exempt
def logout_request(request):
    logout(request)
    return redirect("login")


# ------------------------
# Model file management
# ------------------------
@csrf_exempt
def model_upload(request):
    """Upload a model file into summer/winter folders."""
    if request.method == "POST":
        user_model_file = request.FILES.get("model_path")
        model_selection = request.POST.get("model", "").strip()  # 'summer' | 'winter'
        if not user_model_file or model_selection not in {"summer", "winter"}:
            return JsonResponse({"status": False, "error": "send valid request"})

        base = os.path.join(settings.BASE_DIR, "static", "models")
        dst_dir = os.path.join(base, "germany_summer_ai_model" if model_selection == "summer" else "germany_winter_ai_model")
        os.makedirs(dst_dir, exist_ok=True)
        fs = FileSystemStorage(location=dst_dir)
        fs.save(user_model_file.name, user_model_file)

        return JsonResponse({"status": True, "message": "Model Upload Successfully"})

    # GET: list both model folders
    summer_dir = os.path.join(settings.BASE_DIR, "static", "models", "germany_summer_ai_model")
    winter_dir = os.path.join(settings.BASE_DIR, "static", "models", "germany_winter_ai_model")
    summer_list = os.listdir(summer_dir) if os.path.isdir(summer_dir) else []
    winter_list = os.listdir(winter_dir) if os.path.isdir(winter_dir) else []
    return JsonResponse({"summer_path": summer_list, "winter_path": winter_list})


@csrf_exempt
def model_upload1(request):
    """List model file names for a given season."""
    model = request.GET.get("model", "summer").strip()
    base = os.path.join(settings.BASE_DIR, "static", "models")
    target = os.path.join(base, "germany_summer_ai_model" if model == "summer" else "germany_winter_ai_model")
    data = os.listdir(target) if os.path.isdir(target) else []
    return JsonResponse({"model_path": data})


@csrf_exempt
def delete_file(request):
    """Delete a specific model file by filename from summer/winter folders."""
    if request.method == "POST":
        filename = request.POST.get("filename", "").strip()
        summer_path = os.path.join(settings.BASE_DIR, "static", "models", "germany_summer_ai_model", filename)
        winter_path = os.path.join(settings.BASE_DIR, "static", "models", "germany_winter_ai_model", filename)

        for p in (summer_path, winter_path):
            if os.path.exists(p):
                os.remove(p)
                return JsonResponse({"success": True})
        return JsonResponse({"success": False, "error": "File not found"})
    return JsonResponse({"success": False, "error": "Invalid request"})


# ------------------------
# Main AI flow
# ------------------------
@csrf_exempt
def index(request):
    """
    POST:
      - 'file' (zip of images, possibly nested folders) OR 'tif_file' (single .tif)
      - 'model' ('summer'|'winter'), 'model_name' (optional)
    Produces under /static:
      - input_img/<run>/**  (originals)
      - result/<run>/**     (processed copies)
      - json/output.json
      - zip/<run>.zip
      - tiff_output.geojson  (if/when your pipeline generates it)
    Returns JSON the frontend expects (image lists + download links).
    """
    base_static = os.path.join(settings.BASE_DIR, "static")
    input_root  = os.path.join(base_static, "input_img")
    result_root = os.path.join(base_static, "result")
    centers_root= os.path.join(base_static, "centers")
    location_root = os.path.join(base_static, "location")
    zip_root    = os.path.join(base_static, "zip")
    json_root   = os.path.join(base_static, "json")
    for d in [input_root, result_root, centers_root, location_root, zip_root, json_root]:
        os.makedirs(d, exist_ok=True)

    if request.method == "POST":
        try:
            # (Optional) clean previous runs
            for pat in ["runs/*", "static/input_img/*", "static/result/*", "static/centers/*", "static/location/*"]:
                for f in glob.glob(os.path.join(settings.BASE_DIR, pat)):
                    if os.path.isdir(f):
                        shutil.rmtree(f, ignore_errors=True)
                    elif os.path.isfile(f):
                        try:
                            os.remove(f)
                        except Exception:
                            pass

            folder_name = get_date_time_for_naming()
            folder_path = os.path.join(input_root, folder_name)
            os.makedirs(folder_path, exist_ok=True)

            zip_file = request.FILES.get("file")
            tif_file = request.FILES.get("tif_file")
            model_selection = request.POST.get("model", "summer").strip()
            model_name = request.POST.get("model_name", "").strip()

            # Save zip/tif
            if zip_file:
                fs = FileSystemStorage(location=folder_path)
                fs.save(zip_file.name, zip_file)
                unzip_file(os.path.join(folder_path, zip_file.name), folder_path)

            if tif_file:
                fs = FileSystemStorage(location=folder_path)
                fs.save(tif_file.name, tif_file)

            # Create .jgw for any TIFs in the top level (your earlier behavior)
            tif_to_jgw_for_folder(folder_path)

            # --- Recursively find images (handles nested subfolders in ZIP) ---
            img_exts = (".jpeg", ".jpg", ".png")
            image_abs_paths = []
            for root_dir, _, files in os.walk(folder_path):
                for fn in files:
                    if fn.lower().endswith(img_exts):
                        image_abs_paths.append(os.path.join(root_dir, fn))

            # If you need .jgw presence for each image, you can check here (non-blocking):
            # missing_jgw = []
            # for abs_img in image_abs_paths:
            #     jgw = os.path.splitext(abs_img)[0] + ".jgw"
            #     if not os.path.exists(jgw):
            #         missing_jgw.append(abs_img)

            # Process (or copy) into result folder, preserving subfolder structure
            processed_folder = os.path.join(result_root, folder_name)
            os.makedirs(processed_folder, exist_ok=True)

            input_images_list = []
            output_images_list = []

            # If you actually load YOLO model, do it here
            # model_dir = os.path.join(settings.BASE_DIR, "static", "models",
            #     "germany_summer_ai_model" if model_selection == "summer" else "germany_winter_ai_model")
            # model_path = os.path.join(model_dir, model_name) if model_name else None
            # model = YOLO(model_path) if YOLO and model_path and os.path.exists(model_path) else None

            for abs_img in image_abs_paths:
                # rel path inside the run folder
                rel_inside_run = os.path.relpath(abs_img, folder_path)  # e.g. 'Eichhalde_MA_Robert(1)/output_1.jpeg'
                # copy to result preserving subdirs
                dst_img = os.path.join(processed_folder, rel_inside_run)
                os.makedirs(os.path.dirname(dst_img), exist_ok=True)
                shutil.copyfile(abs_img, dst_img)

                # build URL-ish paths for frontend (under /static)
                input_images_list.append(f"static/input_img/{folder_name}/{rel_inside_run}".replace("\\", "/"))
                output_images_list.append(f"static/result/{folder_name}/{rel_inside_run}".replace("\\", "/"))

            # (Optional) GeoJSON generation using your real functions
            # output_geojson_file = "static/tiff_output.geojson"
            # genrate_json_json(location_root, output_geojson_file, model_selection)
            # try:
            #     process_geojson(output_geojson_file, initial_tolerance=10, static_root="static")
            # except Exception:
            #     pass

            # For compatibility, set a path (update when your pipeline writes it)
            output_geojson_file = "static/tiff_output.geojson"

            # Zip the original run folder so user can download what was processed
            zip_rel = os.path.join("static", "zip", f"{folder_name}.zip")
            zip_folder(folder_path, os.path.join(settings.BASE_DIR, zip_rel))

            # Small JSON summary
            json_rel = os.path.join("static", "json", "output.json")
            with open(os.path.join(settings.BASE_DIR, json_rel), "w") as jf:
                json.dump({"final_result": output_images_list}, jf)

            # --- Normalize for frontend ---
            input_images_list = [_urlify(p) for p in input_images_list]
            output_images_list = [_urlify(p) for p in output_images_list]

            context = {
                "status": True,
                "error": "" if image_abs_paths else "No images found in the uploaded archive.",
                "geojson_path": _urlify(output_geojson_file),
                "zip_path": _urlify(zip_rel),
                "input_image_list": input_images_list,
                "output_image_list": output_images_list,
                "json_path": _urlify(json_rel),
            }
            return JsonResponse(context)

        except Exception as e:
            return JsonResponse({
                "status": False,
                "error": str(e),
                "geojson_path": "",
                "zip_path": "",
                "input_image_list": [],
                "output_image_list": [],
                "json_path": "",
            })

    # GET -> render landing page
    return render(request, "index.html")


# ------------------------
# GeoJSON helper (for Layer page)
# ------------------------
@csrf_exempt
def geo_json_path(request):
    """Return paths + contents of GeoJSON files."""
    try:
        output_geo = os.path.join(settings.BASE_DIR, "static", "output.geojson")
        tiff_geo = os.path.join(settings.BASE_DIR, "static", "tiff_output.geojson")

        geojson_data = {}
        if os.path.exists(output_geo):
            with open(output_geo, "r") as f:
                geojson_data = json.load(f)

        tiff_geojson_data = {}
        if os.path.exists(tiff_geo):
            with open(tiff_geo, "r") as f:
                tiff_geojson_data = json.load(f)

        return JsonResponse({
            "geo_path": "static/output.geojson",
            "geojson_data": geojson_data,
            "tiff_geo_path": "static/tiff_output.geojson",
            "tiff_geojson_data": tiff_geojson_data,
        })
    except Exception as e:
        return JsonResponse({"status": False, "error": str(e)})
