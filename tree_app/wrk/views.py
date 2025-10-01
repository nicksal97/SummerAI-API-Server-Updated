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

# ======= optional libs used by your pipeline (keep/remove as needed) =======
# Yolov8 (if you actually run inference here)
try:
    from ultralytics import YOLO
except Exception:
    YOLO = None

# Raster IO for world-file writing (JGW) etc.
try:
    import rasterio
except Exception:
    rasterio = None

# If you keep your helper functions in the same app, import them here.
# Make sure the names match your project files (adjust as needed).
# from .Splitting_TIFF_file_Concise import tif_main, tif_to_jwg
# from .inference import prediction
# from .utils import location_point, genrate_json_json, process_geojson, remove_tif_file, zip_folder

User = get_user_model()

# === Added helper to normalize file paths for the frontend (IMPORTANT) ===
def _urlify(p: str) -> str:
    """Ensure a URL-style path with leading '/' for static files."""
    if not p:
        return ""
    p = p.replace("\\", "/")
    return p if p.startswith("/") else f"/{p}"
# === End helper ===


# ------------------------
# Utility helpers (keep)
# ------------------------
def get_date_time_for_naming() -> str:
    """Generate a timestamp string suitable for naming files."""
    dt, micro = datetime.utcnow().strftime("%Y%m%d%H%M%S.%f").split(".")
    return f"{dt}{int(micro)/1000:03.0f}"

def unzip_file(zip_path: str, extract_to: str) -> None:
    """Unzip uploaded .zip into a folder."""
    os.makedirs(extract_to, exist_ok=True)
    with zipfile.ZipFile(zip_path, "r") as z:
        z.extractall(extract_to)

def tif_to_jgw_for_folder(folder_path: str) -> None:
    """Create .jgw files for all .tif/.tiff images in folder (basic version)."""
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
                jgw.write(f"{transform.e}\n")  # pixel height (usually negative)
                jgw.write(f"{transform.c}\n")  # upper-left X
                jgw.write(f"{transform.f}\n")  # upper-left Y
                jgw.write("0.0\n")             # rotation parm
                jgw.write("0.0\n")             # rotation parm

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
        full_name = request.POST.get("full_name", "").strip()  # optional if your model requires

        if not username or not email or not password:
            return JsonResponse({"status": False, "error": "Missing fields"})

        if User.objects.filter(username=username).exists():
            return JsonResponse({"status": False, "error": "This username already exist"})

        if User.objects.filter(email=email).exists():
            return JsonResponse({"status": False, "error": "This email already exist"})

        user = User.objects.create_user(username=username, email=email, password=password)
        # If you require full_name:
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
        user_qs = User.objects.filter(email=email)
        if not user_qs.exists():
            return JsonResponse({"status": False, "error": "Invalid email or password"})
        username = user_qs.first().username
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
    """Upload a model file into the selected summer/winter model folder."""
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
    # Also return listing for both folders for convenience
    summer_dir = os.path.join(settings.BASE_DIR, "static", "models", "germany_summer_ai_model")
    winter_dir = os.path.join(settings.BASE_DIR, "static", "models", "germany_winter_ai_model")
    summer_list = os.listdir(summer_dir) if os.path.isdir(summer_dir) else []
    winter_list = os.listdir(winter_dir) if os.path.isdir(winter_dir) else []
    return JsonResponse({"summer_path": summer_list, "winter_path": winter_list})


@csrf_exempt
def model_upload1(request):
    """List model file names for a given season (used by frontend to populate dropdown)."""
    model = request.GET.get("model", "summer").strip()
    base = os.path.join(settings.BASE_DIR, "static", "models")
    target = os.path.join(base, "germany_summer_ai_model" if model == "summer" else "germany_winter_ai_model")
    data = [f for f in os.listdir(target)] if os.path.isdir(target) else []
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
    Handles the main request for the application (AI pipeline).
    Accepts either:
      - POST with 'file' (zip of JPEGs/TIFs) OR 'tif_file' (single .tif)
      - GET renders the home page
    Produces:
      - static/result/<folder>/... images (processed)
      - static/json/output.json
      - static/output.geojson and static/tiff_output.geojson
      - static/zip/<folder>.zip
    Returns JSON with paths the frontend expects.
    """
    # Base folders under /static
    base_static = os.path.join(settings.BASE_DIR, "static")
    input_root = os.path.join(base_static, "input_img")
    result_root = os.path.join(base_static, "result")
    centers_root = os.path.join(base_static, "centers")
    location_root = os.path.join(base_static, "location")
    zip_root = os.path.join(base_static, "zip")
    json_root = os.path.join(base_static, "json")
    os.makedirs(input_root, exist_ok=True)
    os.makedirs(result_root, exist_ok=True)
    os.makedirs(centers_root, exist_ok=True)
    os.makedirs(location_root, exist_ok=True)
    os.makedirs(zip_root, exist_ok=True)
    os.makedirs(json_root, exist_ok=True)

    if request.method == "POST":
        try:
            # clean previous run folders if your UX expects that
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

            # inputs
            zip_file = request.FILES.get("file")
            tif_file = request.FILES.get("tif_file")
            model_selection = request.POST.get("model", "summer").strip()  # 'summer' | 'winter'
            model_name = request.POST.get("model_name", "").strip()

            # Save zip or tif
            if zip_file:
                fs = FileSystemStorage(location=folder_path)
                fs.save(zip_file.name, zip_file)
                # unzip
                unzip_file(os.path.join(folder_path, zip_file.name), folder_path)

            if tif_file:
                fs = FileSystemStorage(location=folder_path)
                fs.save(tif_file.name, tif_file)

            # Ensure JGW files for TIFs
            tif_to_jgw_for_folder(folder_path)

            # Check that for each .jpeg there is a matching .jgw (your original check)
            file_names = os.listdir(folder_path)
            image_files = [fn for fn in file_names if fn.lower().endswith(".jpeg")]
            for img in image_files:
                jgw_file = img.replace(".jpeg", ".jgw")
                if jgw_file not in file_names:
                    return JsonResponse({
                        "status": False,
                        "error": f"No corresponding .jgw file found for {img}"
                    })

            # ---------------- Run inference (adapt as per your real pipeline) ----------------
            # Example using YOLO if you have it; otherwise, copy/move input images to result.
            processed_folder = os.path.join(result_root, folder_name)
            os.makedirs(processed_folder, exist_ok=True)

            input_images_list = []
            output_images_list = []

            # If you actually have YOLO + models, you can load them:
            # model_dir = os.path.join(settings.BASE_DIR, "static", "models",
            #     "germany_summer_ai_model" if model_selection == "summer" else "germany_winter_ai_model")
            # model_path = os.path.join(model_dir, model_name) if model_name else None
            # model = YOLO(model_path) if YOLO and model_path and os.path.exists(model_path) else None

            for fn in image_files:
                src_img = os.path.join(folder_path, fn)
                # Here you would run your detection, draw boxes, etc., then save to processed_folder.
                # For now, we just copy to simulate a processed output image.
                dst_img = os.path.join(processed_folder, fn)
                shutil.copyfile(src_img, dst_img)

                input_images_list.append(f"static/input_img/{folder_name}/{fn}")
                output_images_list.append(f"static/result/{folder_name}/{fn}")
            # -------------------------------------------------------------------------------

            # Centers/locations & GeoJSON generation:
            # location_point(centers_root, folder_path, location_root)
            # Create a TIFF-based geojson
            output_geojson_file = os.path.join("static", "tiff_output.geojson")
            # genrate_json_json(location_root, output_geojson_file, model_selection)

            # post-process the geojson minimally if needed
            # try:
            #     process_geojson(output_geojson_file, initial_tolerance=10, static_root="static")
            # except Exception:
            #     pass

            # Remove temporary .tif if your flow requires it
            # remove_tif_file(folder_path)

            # Zip results
            zip_path = os.path.join("static", "zip", f"{folder_name}.zip")
            zip_folder(folder_path, os.path.join(settings.BASE_DIR, zip_path))

            # Write a summary JSON file
            final_dict_list = {"final_result": output_images_list}
            json_path = os.path.join("static", "json", "output.json")
            with open(os.path.join(settings.BASE_DIR, json_path), "w") as jf:
                json.dump(final_dict_list, jf)

            # === Normalized success response (added) ===
            # Make URL-safe paths for the frontend
            input_images_list = [_urlify(p) for p in input_images_list]
            output_images_list = [_urlify(p) for p in output_images_list]

            geojson_rel = _urlify(output_geojson_file)
            zip_rel = _urlify(zip_path)
            json_rel = _urlify(json_path)

            context = {
                "status": True,
                "error": "",
                "geojson_path": geojson_rel,
                "zip_path": zip_rel,
                "input_image_list": input_images_list,
                "output_image_list": output_images_list,
                "json_path": json_rel,
            }
            return JsonResponse(context)

        except Exception as e:
            context = {
                "status": False,
                "error": str(e),
                "geojson_path": "",
                "zip_path": "",
                "input_image_list": [],
                "output_image_list": [],
                "json_path": "",
            }
            return JsonResponse(context)

    # GET → render your landing page (or return a small JSON)
    return render(request, "index.html")


# ------------------------
# Helper endpoint to return latest geojson contents
# ------------------------
@csrf_exempt
def geo_json_path(request):
    """Return paths and contents of the main GeoJSON files the frontend expects."""
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
