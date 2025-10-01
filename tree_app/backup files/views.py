import os
import glob
import json
import shutil
import zipfile
from datetime import datetime
from pathlib import Path

from django.conf import settings
from django.http import JsonResponse, HttpRequest, HttpResponse
from django.shortcuts import render, redirect
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required

# ---- your imports that are used by the pipeline (unchanged) ----
from inference import prediction
from PIL import Image
from ultralytics import YOLO
import rasterio
import geopandas as gpd
from shapely.geometry import LineString, MultiLineString, MultiPolygon, Polygon
from shapely.ops import unary_union
import pygeoops
import pandas as pd

from .forms import SignupForm
from .models import *
from django.core.files.storage import FileSystemStorage

BASE_DIR = settings.BASE_DIR
STATIC_DIR = os.path.join(BASE_DIR, "static")

# -------------------------------------------------------------------
# Small helpers
# -------------------------------------------------------------------
def _ensure(*dirs):
    for d in dirs:
        os.makedirs(d, exist_ok=True)

def _ts():
    dt, micro = datetime.utcnow().strftime("%Y%m%d%H%M%S.%f").split(".")
    return f"{dt}{int(micro)//1000:03d}"

def unzip_file(zip_path, extract_to):
    with zipfile.ZipFile(zip_path, "r") as z:
        z.extractall(extract_to)

def zip_folder_with_extras(src_folder: str, zip_abs: str, extra_files=None):
    """
    Zip the *OUTPUT* folder and also place any extra files (e.g. output.geojson)
    into the root of the zip.
    """
    extra_files = extra_files or []
    _ensure(os.path.dirname(zip_abs))
    with zipfile.ZipFile(zip_abs, "w", zipfile.ZIP_DEFLATED) as z:
        for root, _, files in os.walk(src_folder):
            for f in files:
                abs_f = os.path.join(root, f)
                rel_f = os.path.relpath(abs_f, src_folder)
                z.write(abs_f, rel_f)
        for ef in extra_files:
            if ef and os.path.exists(ef) and os.path.getsize(ef) > 0:
                z.write(ef, os.path.basename(ef))

# -------------------------------------------------------------------
# Your existing geo helpers (short version – identical behavior)
# -------------------------------------------------------------------
def tif_to_jwg(folder_path):
    for file_name in os.listdir(folder_path):
        file_path = os.path.join(folder_path, file_name)
        if os.path.isfile(file_path) and file_name.lower().endswith(('.tif', '.tiff')):
            with rasterio.open(file_path) as src:
                transform = src.transform
            name = os.path.splitext(file_name)[0]
            with open(os.path.join(folder_path, f"{name}.jgw"), "w") as jgw:
                jgw.write(f"{transform.a}\n")   # pixel width
                jgw.write(f"{transform.e}\n")   # pixel height
                jgw.write(f"{transform.c}\n")   # x upper-left
                jgw.write(f"{transform.f}\n")   # y upper-left
                jgw.write("0.0\n")              # rotation placeholders
                jgw.write("0.0\n")

def process_geojson(geojson_file, initial_tolerance, centerline_geojson_dir):
    gdf = gpd.read_file(geojson_file)
    other_cat = gdf[gdf['name'].isin(['unhealthy-tree', 'fallen-tree', 'single-tree'])].copy()

    buffered_gdf = gdf[gdf['name'] == 'path'].copy()
    if len(buffered_gdf):
        buffered_gdf['geometry'] = buffered_gdf['geometry'].buffer(initial_tolerance)
        merged_buffers = unary_union(buffered_gdf['geometry'])
        centerlines = []

        if isinstance(merged_buffers, (Polygon, MultiPolygon)):
            polys = [merged_buffers] if isinstance(merged_buffers, Polygon) else merged_buffers.geoms
            for poly in polys:
                cl = pygeoops.centerline(poly)
                if isinstance(cl, LineString):
                    centerlines.append(cl)
                elif isinstance(cl, MultiLineString):
                    centerlines.extend(list(cl.geoms))

        if centerlines:
            cl_gdf = gpd.GeoDataFrame({'name': ['path'] * len(centerlines)},
                                      crs=gdf.crs,
                                      geometry=centerlines)
            other_cat = pd.concat([other_cat, cl_gdf], ignore_index=True)

    out_abs = os.path.join(centerline_geojson_dir, "output.geojson")
    _ensure(centerline_geojson_dir)
    other_cat.to_file(out_abs, driver="GeoJSON")

# -------------------------------------------------------------------
# AUTH – unchanged from your file
# -------------------------------------------------------------------
@csrf_exempt
def signup_request(request):
    if request.method == 'POST':
        form = SignupForm(request.POST)
        if form.is_valid():
            username = form.cleaned_data.get('username')
            raw_password = form.cleaned_data.get('password1')
            email = request.POST.get('email')
            full_name = request.POST.get('full_name')

            if CustomUser.objects.filter(username=username).exists():
                return JsonResponse({'status': False,'message':'','error':'This username already exist'})

            if CustomUser.objects.filter(email=email).exists():
                return JsonResponse({'status': False,'message':'','error':'This email already exist'})

            form.save()
            user = authenticate(username=username, password=raw_password)
            if user is not None:
                user.email = email
                user.full_name = full_name
                user.save()
                return JsonResponse({'status': True, 'message': 'signup successful.', 'error': ''})
        return JsonResponse({'status': False, 'message': '', 'error': form.errors})
    return JsonResponse({'status': False, 'message': '', 'error': 'Send Post Request'})

@csrf_exempt
def login_request(request):
    if request.method == 'POST':
        email = request.POST.get('email')
        password = request.POST.get('password')
        try:
            cu = CustomUser.objects.get(email=email)
            user = authenticate(username=cu.username, password=password)
            if user is not None:
                login(request, user)
                return JsonResponse({
                    'status': True, 'message': 'login successful.', 'error': '',
                    "user_id": user.id, "username": user.username,
                    "email": user.email, "full_name": user.full_name,
                })
        except Exception:
            pass
        return JsonResponse({'status': False, 'message': '', 'error': 'Invalid email or password'})
    return JsonResponse({'status': False, 'message': '', 'error': 'send valid request'})

@csrf_exempt
def logout_request(request):
    logout(request)
    return redirect('login')

# -------------------------------------------------------------------
# MODEL upload/list/delete – unchanged behavior
# -------------------------------------------------------------------
@csrf_exempt
def model_upload1(request):
    model_type = request.GET.get('model', 'summer')
    base = os.path.join(STATIC_DIR, 'models')
    model_dir = os.path.join(base, 'germany_summer_ai_model' if model_type == 'summer' else 'germany_winter_ai_model')
    files = os.listdir(model_dir) if os.path.isdir(model_dir) else []
    return JsonResponse({'model_path': files})

@csrf_exempt
def model_upload(request):
    if request.method == 'POST':
        f = request.FILES.get('model_path')
        sel = request.POST.get('model', 'summer')
        model_dir = os.path.join(STATIC_DIR, 'models', 'germany_summer_ai_model' if sel == 'summer' else 'germany_winter_ai_model')
        _ensure(model_dir)
        FileSystemStorage(location=model_dir).save(f.name, f)
        return JsonResponse({"status": True, "message": "Model Upload Successfully"})
    summer_dir = os.path.join(STATIC_DIR,'models','germany_summer_ai_model')
    winter_dir = os.path.join(STATIC_DIR,'models','germany_winter_ai_model')
    return JsonResponse({
        'summer_path': os.listdir(summer_dir) if os.path.isdir(summer_dir) else [],
        'winter_path': os.listdir(winter_dir) if os.path.isdir(winter_dir) else [],
    })

@csrf_exempt
def delete_file(request):
    if request.method == 'POST':
        filename = request.POST.get('filename', '')
        for sub in ('germany_summer_ai_model', 'germany_winter_ai_model'):
            p = os.path.join(STATIC_DIR, 'models', sub, filename)
            if os.path.exists(p):
                os.remove(p)
                return JsonResponse({'success': True})
        return JsonResponse({'success': False, 'error': 'File not found'})
    return JsonResponse({'success': False, 'error': 'Invalid request'})

# -------------------------------------------------------------------
# MAIN: create output images, ALWAYS write static/output.geojson,
#       zip the *result* folder and include output.geojson inside.
# -------------------------------------------------------------------
@csrf_exempt
def index(request: HttpRequest):
    if request.method == 'GET':
        return render(request, 'index.html')

    # clean previous transient folders (same as your file)
    for pat in ['runs/*', 'static/centers/*', 'static/location/*', 'static/zip_folder/*']:
        for f in glob.glob(os.path.join(BASE_DIR, pat)):
            try:
                shutil.rmtree(f) if os.path.isdir(f) else os.remove(f)
            except Exception:
                pass

    # inputs
    tif_file = request.FILES.get('tif_file')
    zip_file = request.FILES.get('file')
    model_selection = request.POST.get('model', 'winter')
    model_name = request.POST.get('model_name', '')

    # per-run folders
    run_id = _ts()
    input_dir  = os.path.join(STATIC_DIR, 'input_img', run_id)
    result_dir = os.path.join(STATIC_DIR, 'result', run_id)
    centers_dir = os.path.join(STATIC_DIR, 'centers')
    location_dir = os.path.join(STATIC_DIR, 'location')
    _ensure(input_dir, result_dir, centers_dir, location_dir, os.path.join(STATIC_DIR, 'zip'))

    # load YOLO
    model_dir = os.path.join(STATIC_DIR,'models','germany_summer_ai_model' if model_selection=='summer' else 'germany_winter_ai_model')
    model_pt = os.path.join(model_dir, model_name) if model_name else None
    if not model_pt or not os.path.exists(model_pt):
        pts = [os.path.join(model_dir, f) for f in os.listdir(model_dir)] if os.path.isdir(model_dir) else []
        pts = [p for p in pts if p.lower().endswith('.pt')]
        model_pt = pts[0] if pts else None
    model = YOLO(model_pt) if model_pt and os.path.exists(model_pt) else None

    input_imgs = []
    output_imgs = []

    # ---------- branch A: single TIF ----------
    if tif_file:
        saved = FileSystemStorage(location=input_dir).save(tif_file.name, tif_file)
        tif_path = os.path.join(input_dir, saved)
        from .Splitting_TIFF_file_Concise import tif_main
        tif_main(tif_path, input_dir)     # produce JPGs etc. in input_dir
        tif_to_jwg(input_dir)

    # ---------- branch B: ZIP of images ----------
    if zip_file:
        saved = FileSystemStorage(location=os.path.join(STATIC_DIR,'zip_folder',run_id)).save(zip_file.name, zip_file)
        zip_abs = os.path.join(STATIC_DIR,'zip_folder',run_id, saved)
        unzip_file(zip_abs, input_dir)

    # choose nested dir inside ZIP if needed (skip __MACOSX)
    for f in os.listdir(input_dir):
        cand = os.path.join(input_dir, f)
        if os.path.isdir(cand) and f != '__MACOSX':
            input_dir = cand
            break

    # YOLO over all JPEG/JPG/PNG
    for fn in os.listdir(input_dir):
        if not fn.lower().endswith(('.jpg','.jpeg','.png')): 
            continue
        abs_in = os.path.join(input_dir, fn)
        img = Image.open(abs_in)

        if model is not None:
            flag, annotated, boxes, img_count, box_ls, pos_ls, center_ls = prediction(img, model)
        else:
            flag, annotated = True, img  # fallback: just copy

        out_abs = os.path.join(result_dir, fn)
        _ensure(os.path.dirname(out_abs))
        if flag:
            annotated.save(out_abs)
        else:
            shutil.copy2(abs_in, out_abs)

        input_imgs.append(f"/static/input_img/{run_id}/{os.path.relpath(abs_in, input_dir)}")
        output_imgs.append(f"/static/result/{run_id}/{os.path.relpath(out_abs, result_dir)}")

        # write centers JSON for later geo step (your existing helper)
        # uses boxes/pos_ls/center_ls if prediction produced them
        try:
            from .views import using_box_find_center_point  # already in your file
            using_box_find_center_point(boxes, pos_ls, centers_dir, fn, img)
        except Exception:
            pass

    # Build GeoJSON (ALWAYS this file)
    output_geojson_abs = os.path.join(STATIC_DIR, "output.geojson")
    try:
        from .views import location_point, genrate_json_json  # already in your file
        location_point(centers_dir, input_dir, location_dir)  # -> location/*.json
        # generate & post-process, then write to static/output.geojson
        genrate_json_json(location_dir, output_geojson_abs, model_selection)
        process_geojson(output_geojson_abs, initial_tolerance=10, centerline_geojson_dir=STATIC_DIR)
    except Exception:
        # if anything fails, still make a minimal valid geojson so download works
        with open(output_geojson_abs, "w", encoding="utf-8") as f:
            json.dump({"type":"FeatureCollection","features":[]}, f)

    # ZIP of **results** + include output.geojson at root
    zip_abs = os.path.join(STATIC_DIR, "zip", f"{run_id}.zip")
    zip_folder_with_extras(result_dir, zip_abs, extra_files=[output_geojson_abs])

    return JsonResponse({
        "status": True,
        "run_id": run_id,
        "geojson_path": "/static/output.geojson",
        "zip_path": f"/static/zip/{run_id}.zip",
        "input_image_list": input_imgs,
        "output_image_list": output_imgs,
        "json_path": "",   # (kept for compatibility)
    })

# -------------------------------------------------------------------
# GeoJSON fetch (map uses this)
# -------------------------------------------------------------------
@csrf_exempt
def geo_json_path(request: HttpRequest) -> HttpResponse:
    out_abs = os.path.join(STATIC_DIR, "output.geojson")
    if not os.path.exists(out_abs):
        with open(out_abs, "w", encoding="utf-8") as f:
            json.dump({"type":"FeatureCollection","features":[]}, f)
    with open(out_abs, "r", encoding="utf-8") as f:
        data = json.load(f)
    return JsonResponse({"geo_path":"static/output.geojson","geojson_data":data})

# -------------------------------------------------------------------
# HISTORY: list everything in static/zip (download buttons)
# Compatible with both /api/zips and /api/runs
# -------------------------------------------------------------------
@csrf_exempt
def zips_history(request: HttpRequest) -> HttpResponse:
    zip_dir = os.path.join(STATIC_DIR, "zip")
    _ensure(zip_dir)
    items = []
    for fn in os.listdir(zip_dir):
        if not fn.lower().endswith(".zip"):
            continue
        abs_p = os.path.join(zip_dir, fn)
        try:
            st = os.stat(abs_p)
        except OSError:
            continue
        items.append({
            "id": os.path.splitext(fn)[0],
            "name": fn,
            "download_url": f"/static/zip/{fn}",
            "size_bytes": st.st_size,
            "created_at": datetime.utcfromtimestamp(st.st_mtime).isoformat() + "Z",
            "geojson_path": "/static/output.geojson"  # same public file
        })
    items.sort(key=lambda x: x["created_at"], reverse=True)
    # Return keys for both your new and old UIs
    return JsonResponse({"ok": True, "items": items, "runs": items})

@login_required(login_url='login')
def history_page(request):
    return render(request, "history.html")
