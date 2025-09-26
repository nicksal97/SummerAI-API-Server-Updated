from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
from django.core.files.storage import FileSystemStorage
from inference import prediction
import glob
from PIL import Image
import json
import shutil
from datetime import datetime
import rasterio
from pathlib import Path
import os
import zipfile
from ultralytics import YOLO
from django.contrib.auth import authenticate, login, logout
from django.views.decorators.csrf import csrf_exempt
from .forms import SignupForm
from django.shortcuts import redirect
from .models import *
from django.contrib.auth.decorators import login_required
from django.conf import settings

# Define the base directory of the project
BASE_DIR = Path(__file__).resolve().parent.parent
print(BASE_DIR)  # Print the base directory path for debugging

from .Splitting_TIFF_file_Concise import tif_main


@csrf_exempt
def signup_request(request):
    if request.method == 'POST':
        try:
            form = SignupForm(request.POST)
            if form.is_valid():
                username = form.cleaned_data.get('username')
                raw_password = form.cleaned_data.get('password1')
                email = request.POST.get('email')
                full_name = request.POST.get('full_name')
                if CustomUser.objects.filter(username=username).exists():
                    context = {
                        'status': 'failed',
                        'error': 'This username already exist',
                    }
                    return JsonResponse(context)
                if CustomUser.objects.filter(email=email).exists():
                    context = {
                        'status': 'failed',
                        'error': 'This email already exist',
                    }
                    return JsonResponse(context)
                form.save()
                user = authenticate(username=username, password=raw_password)
                if user is not None:
                    user.email = email
                    user.full_name = full_name
                    user.save()
                    context = {
                        'status': True,
                        'message': 'signup successful.',
                        'error': '',
                    }
                    return JsonResponse(context)
                else:
                    error = form.errors
                    try:
                        if "username" in error:
                            a = error["username"]
                            error = a[0]
                        if "password2" in error:
                            a = error["password2"]
                            error = a[0]
                    except:
                        pass
                    context = {
                        'status': False,
                        'message': '',
                        'error': error,
                    }
                    return JsonResponse(context)
            else:
                error = form.errors
                try:
                    if "username" in error:
                        a = error["username"]
                        error = a[0]
                    if "password2" in error:
                        a = error["password2"]
                        error = a[0]
                except:
                    pass
                context = {
                    'status': False,
                    'message': '',
                    'error': error,
                }
                return JsonResponse(context)
        except Exception as e:
            error = e
            try:
                if "username" in error:
                    a = error["username"]
                    error = a[0]
                if "password2" in error:
                    a = error["password2"]
                    error = a[0]
            except:
                pass
            context = {
                'status': False,
                'message': '',
                'error': error,
            }
            return JsonResponse(context)
    else:
        context = {
            'status': False,
            'message': '',
            'error': 'Send Post Request',
        }
        return JsonResponse(context)


# @login_required(login_url='login')
@csrf_exempt
def model_upload1(request):
    model_type = request.GET.get('model')
    summer_path = f"static/models/germany_summer_ai_model/"
    winter_path = f"static/models/germany_winter_ai_model/"
    model_files = ''
    if model_type == 'summer':
        model_files = os.listdir(summer_path)
    elif model_type == 'winter':
        model_files = os.listdir(winter_path)
    context = {
        'model_path': model_files,
    }
    return JsonResponse(context)


# @login_required(login_url='login')
@csrf_exempt
def model_upload(request):
    if request.method == 'POST':
        user_model_path = request.FILES.get('model_path')
        model_selection = request.POST['model']
        model_path = 'static/models/'
        if model_selection == "summer":
            model_path = 'static/models/germany_summer_ai_model/'
        elif model_selection == "winter":
            model_path = 'static/models/germany_winter_ai_model/'
        location = FileSystemStorage(location=model_path)
        location.save(user_model_path.name, user_model_path)
        context = {
            "status": True,
            "message": "Model Upload Successfully"
        }
        return JsonResponse(context)
    summer_path = f"static/models/germany_summer_ai_model/"
    winter_path = f"static/models/germany_winter_ai_model/"
    summer_path = os.listdir(summer_path)
    winter_path = os.listdir(winter_path)
    context = {
        'summer_path': summer_path,
        'winter_path': winter_path
    }
    print(context)
    return JsonResponse(context)
    # return render(request, 'model.html', context)


# @login_required(login_url='login')
@csrf_exempt
def delete_file(request):
    if request.method == 'POST':
        filename = request.POST.get('filename')
        summer_path = os.path.join(settings.BASE_DIR, 'static', 'models', 'germany_summer_ai_model', filename)
        winter_path = os.path.join(settings.BASE_DIR, 'static', 'models', 'germany_winter_ai_model', filename)

        if os.path.exists(summer_path):
            os.remove(summer_path)
            return JsonResponse({'success': True})
        elif os.path.exists(winter_path):
            os.remove(winter_path)
            return JsonResponse({'success': True})
        else:
            return JsonResponse({'success': False, 'error': 'File not found'})

    return JsonResponse({'success': False, 'error': 'Invalid request'})


@csrf_exempt
def login_request(request):
    if request.method == 'POST':
        email = request.POST.get('email')
        password = request.POST.get('password')
        try:
            username = CustomUser.objects.get(email=email)
            user = authenticate(username=username.username, password=password)
            if user is not None:
                login(request, user)
                user_id = request.user.id
                id = CustomUser.objects.get(id=user_id)
                context = {
                    'status': True,
                    'message': 'login successful.',
                    'error': '',
                    "user_id": user_id,
                    "username": id.username,
                    "email": id.email,
                    "full_name": id.full_name,
                }
                return JsonResponse(context)
                # return render(request, 'index.html', context)
            else:
                error = 'Invalid email or password'
                context = {
                    'status': False,
                    'message': '',
                    'error': error,
                }
                return JsonResponse(context)
                # return render(request, 'login.html', context)
        except Exception as e:
            error = 'Invalid email or password'
            context = {
                'status': False,
                'message': '',
                'error': error,
            }
            return JsonResponse(context)

            # return render(request, 'login.html', context)
    else:
        error = 'send valid request'
        context = {
            'status': False,
            'message': '',
            'error': '',
        }
        return JsonResponse(context)

        # return JsonResponse(context)
        # return render(request, 'login.html', context)


@csrf_exempt
def logout_request(request):
    logout(request)
    return redirect('login')


def calculate_center_points(line, output_image_path):
    """Calculate the center points from the bounding box coordinates."""
    parts = line.split()
    class_value_id = parts[0]
    print(class_value_id)
    if class_value_id == '6':
        return False, False

    bounding_coordinates = [float(x) for x in parts[1:]]  # Extract and convert coordinates to float

    x_coordinates = bounding_coordinates[::2]  # Extract X coordinates (even-indexed)
    y_coordinates = bounding_coordinates[1::2]  # Extract Y coordinates (odd-indexed)

    center_x = sum(x_coordinates) / len(x_coordinates)  # Calculate center X coordinate
    center_y = sum(y_coordinates) / len(y_coordinates)  # Calculate center Y coordinate

    return center_x, center_y


def create_center_point(input_directory, output_directory, output_image_path):
    """Create a file with center points for all the objects detected in the input files."""
    for input_filename in os.listdir(input_directory):
        if input_filename.endswith(".txt"):
            input_filepath = os.path.join(input_directory, input_filename)
            output_filepath = os.path.join(output_directory, input_filename)

            with open(input_filepath, "r") as input_file:
                lines = input_file.readlines()

            center_points = []
            for line in lines:
                center_point = calculate_center_points(line, output_image_path)
                print(center_point)
                if center_point:
                    center_points.append(center_point)

            # Write the calculated center points to the output file
            with open(output_filepath, "w") as output_file:
                for center_x, center_y in center_points:
                    output_file.write(f"{center_x} {center_y}\n")


def convert_to_txt(filename):
    """Convert image filename to a corresponding .txt filename."""
    image_extensions = [".png", ".jpg", ".jpeg", ".gif", ".bmp"]
    for ext in image_extensions:
        if filename.endswith(ext):
            return filename[:-len(ext)] + ".txt"
    return filename + ".txt"


def convert_to_json(filename):
    """Convert image filename to a corresponding .json filename."""
    image_extensions = [".png", ".jpg", ".jpeg", ".gif", ".bmp"]
    for ext in image_extensions:
        if filename.endswith(ext):
            return filename[:-len(ext)] + ".json"
    return filename + ".json"


def using_box_find_center_point(boxes, postion_ls, output_directory, input_filename, output_image_path):
    """Calculate the center points from bounding boxes and save them along with polygon area data to a JSON file."""
    center_points = []
    input_filename_txt = convert_to_txt(input_filename)  # Convert image filename to .txt
    input_directory = 'runs/segment/predict/labels'  # Define the input directory for label files
    input_filepath = os.path.join(input_directory, input_filename_txt)

    try:
        with open(input_filepath, "r") as input_file:
            lines = input_file.readlines()

        center_points = []
        for line in lines:
            center_point = calculate_center_points(line, output_image_path)
            print(center_point)
            if False not in center_point:
                print("work")
                center_points.append(center_point)

        # Convert input filename to JSON and write the data to the output file
        input_filename = convert_to_json(input_filename)
        output_filepath = os.path.join(output_directory, input_filename)

        final_dict_list = {
            "xy_point": center_points,
            "polygone_area": postion_ls,
        }

        with open(output_filepath, "w") as json_file:
            json.dump(final_dict_list, json_file)
    except Exception:
        pass  # If any error occurs, pass without breaking the program


def calculate_actual_coordinates(jgw_file_path, txt_file_path):
    """Calculate actual geographic coordinates from pixel coordinates using JGW file information."""
    with open(jgw_file_path, 'r') as jgw_file:
        jgw_lines = jgw_file.readlines()

    # Extract transformation parameters from the JGW file
    x_pixel_size = float(jgw_lines[0])
    x_origin = float(jgw_lines[4])
    y_origin = float(jgw_lines[5])

    with open(txt_file_path, 'r') as file:
        data = json.load(file)

    actual_coordinates = []
    lines = data['xy_point']
    polygone_area_data = data['polygone_area']
    origin_value = x_pixel_size

    # Transform line coordinates into actual geographic coordinates
    for poly in polygone_area_data:
        all_line_value = poly['line_value']
        if all_line_value is not False:
            transformed_coordinates = []
            for value in all_line_value:
                a, b = value
                actual_x1 = (float(a[0]) * origin_value) + x_origin
                actual_y1 = (float(a[1]) * -origin_value) + y_origin
                actual_x2 = (float(b[0]) * origin_value) + x_origin
                actual_y2 = (float(b[1]) * -origin_value) + y_origin
                transformed_coordinates.extend([(actual_x1, actual_y1), (actual_x2, actual_y2)])
            poly['line_value'] = transformed_coordinates

    for line in lines:
        if len(line) >= 2:
            normalized_x, normalized_y = map(float, line)
            actual_x = (normalized_x * 100) + x_origin
            actual_y = (normalized_y * -100) + y_origin
            actual_coordinates.append((actual_x, actual_y))

    return actual_coordinates, data['polygone_area']


def location_point(centers_directory, data_directory, output_directory):
    """Convert label coordinates into geographic locations and save them as JSON."""
    label_files = [f for f in os.listdir(centers_directory) if f.endswith(".json")]

    for label_file in label_files:
        label_file_path = os.path.join(centers_directory, label_file)
        jgw_file_path = os.path.join(data_directory, label_file.replace(".json", ".jgw"))
        actual_coordinates, polygone_area_list = calculate_actual_coordinates(jgw_file_path, label_file_path)

        output_file_path = os.path.join(output_directory, label_file.replace(".json", ".json"))
        final_dict_list = {
            "actual_coordinates": actual_coordinates,
            "polygone_area": polygone_area_list,
        }

        with open(output_file_path, "w") as json_file:
            json.dump(final_dict_list, json_file)


def calculate_center_points_geojson(line, polygone_area, output_filename):
    """Calculate center points and prepare data for GeoJSON creation."""
    detection_point_name = list(polygone_area.keys())[0]
    polygone_area_value = polygone_area[detection_point_name]

    # Extract X and Y coordinates from the line
    x_coordinates = [float(line[i]) for i in range(0, len(line), 2)]
    y_coordinates = [float(line[i]) for i in range(1, len(line), 2)]

    # Check if the detected point is a path or a point
    if 'path' in detection_point_name:
        coordinates = polygone_area['line_value']
    else:
        coordinates = [x_coordinates[0], y_coordinates[0]]

    return output_filename, coordinates, detection_point_name, polygone_area_value


def genrate_json_json(input_directory, output_geojson_file, model_selection):
    """Generate a GeoJSON file from the processed JSON data."""
    feature_collection = {
        "type": "FeatureCollection",
        "name": "single-tree",
        "crs": {
            "type": "name",
            "properties": {
                "name": "urn:ogc:def:crs:EPSG::3857"
            }
        },
        "features": []
    }

    for input_filename in os.listdir(input_directory):
        if input_filename.endswith(".json"):

            input_filepath = os.path.join(input_directory, input_filename)
            output_filename = os.path.splitext(input_filename)[0]
            with open(input_filepath, 'r') as file:
                data = json.load(file)
            id = 0
            if model_selection == "winter":
                for polygon_area in data['polygone_area']:
                    detection_point_name = list(polygon_area.keys())[0]
                    polygone_area_value = polygon_area[detection_point_name]
                    if 'path' in detection_point_name:
                        coordinates = polygon_area['line_value']
                        id += 1
                        feature = {
                            "type": "Feature",
                            "geometry": {
                                "type": "LineString",
                                'coordinates': coordinates
                            },
                            "properties": {
                                "id": id,
                                "name": f"{detection_point_name}",
                                "description": f"{output_filename}.png",
                                "polygon_area": f"{polygone_area_value}",
                            },
                        }
                        feature_collection["features"].append(feature)
            else:

                for index, line in enumerate(data['actual_coordinates']):
                    try:
                        polygon_area = data['polygone_area'][index]
                        detection_point_name = list(polygon_area.keys())[0]
                        polygone_area_value = polygon_area[detection_point_name]
                    except:
                        detection_point_name = 'unhealthy-tree'
                        polygone_area_value = '216.85 m²',
                    if 'path' in detection_point_name:
                        detection_point_name = 'unhealthy-tree'
                    x_coordinates = [float(line[i]) for i in range(0, len(line), 2)]
                    y_coordinates = [float(line[i]) for i in range(1, len(line), 2)]
                    coordinates = [x_coordinates[0], y_coordinates[0]]
                    id += 1
                    feature = {
                        "type": "Feature",
                        "geometry": {
                            "type": 'Point',
                            'coordinates': coordinates
                        },
                        "properties": {
                            "id": id,
                            "name": f"{detection_point_name}",
                            "description": f"{output_filename}.png",
                            "polygon_area": f"{polygone_area_value}",
                        },
                    }
                    feature_collection["features"].append(feature)

                for polygon_area in data['polygone_area']:
                    detection_point_name = list(polygon_area.keys())[0]
                    polygone_area_value = polygon_area[detection_point_name]
                    if 'path' in detection_point_name:
                        coordinates = polygon_area['line_value']
                        id += 1
                        feature = {
                            "type": "Feature",
                            "geometry": {
                                "type": "LineString",
                                'coordinates': coordinates
                            },
                            "properties": {
                                "id": id,
                                "name": f"{detection_point_name}",
                                "description": f"{output_filename}.png",
                                "polygon_area": f"{polygone_area_value}",
                            },
                        }
                        feature_collection["features"].append(feature)

            # for line, polygone_area in zip(data['actual_coordinates'], data['polygone_area']):
            #     output_filename, coordinates, detection_point_name, polygone_area_value = calculate_center_points_geojson(
            #         line, polygone_area, output_filename)
            #     id += 1
            #     print("detection_point_name:",detection_point_name)
            #
            #     # Define geometry type (LineString or Point) based on detection point type
            #     geometry_type = "LineString" if 'path' in detection_point_name else "Point"
            #     geometry_key = 'line_value' if 'path' in detection_point_name else 'coordinates'
            #     # print("geometry_type:",geometry_type)
            #
            #     feature = {
            #         "type": "Feature",
            #         "geometry": {
            #             "type": geometry_type,
            #             'coordinates': coordinates
            #         },
            #         "properties": {
            #             "id": id,
            #             "name": f"{detection_point_name}",
            #             "description": f"{output_filename}.png",
            #             "polygon_area": f"{polygone_area_value}",
            #         },
            #     }
            #     feature_collection["features"].append(feature)

    # Write the feature collection to a GeoJSON file
    with open(output_geojson_file, "w") as output_file:
        json.dump(feature_collection, output_file)


def tif_to_jwg(folder_path):
    """Convert TIFF image georeferencing data to JGW world file."""
    for file_name in os.listdir(folder_path):
        file_path = os.path.join(folder_path, file_name)
        if os.path.isfile(file_path) and file_name.lower().endswith(('.tif', '.tiff')):
            print(file_path)
            file_name = file_name.split('.')[0]
            with rasterio.open(file_path) as src:
                transform = src.transform

            # Write transformation parameters to the JGW file
            with open(f'{folder_path}/{file_name}.jgw', 'w') as jgw_file:
                jgw_file.write(f"{transform.a}\n")  # Pixel width
                jgw_file.write(f"{transform.e}\n")  # Pixel height
                jgw_file.write(f"{transform.c}\n")  # X-coordinate of the upper-left corner
                jgw_file.write(f"{transform.f}\n")  # Y-coordinate of the upper-left corner
                jgw_file.write("0.0\n")  # Ignore rotation or skew parameters
                jgw_file.write("0.0\n")


def unzip_file(zip_path, extract_to):
    """Unzip the contents of a zip file to the specified directory."""
    with zipfile.ZipFile(zip_path, 'r') as zipf:
        zipf.extractall(extract_to)


import geopandas as gpd
import matplotlib.pyplot as plt
from shapely.geometry import LineString, MultiLineString, MultiPolygon, Polygon
from shapely.ops import unary_union, linemerge
import pygeoops
from shapely.validation import explain_validity
import pandas as pd
import os


def process_geojson(geojson_file, initial_tolerance, centerline_geojson_file):
    # Load the GeoDataFrame
    gdf = gpd.read_file(geojson_file)
    other_cat = gdf[gdf['name'].isin(['unhealthy-tree', 'fallen-tree', 'single-tree'])].copy()

    # Buffer each line by the initial tolerance
    # Create a copy to avoid SettingWithCopyWarning
    buffered_gdf = gdf[gdf['name'] == 'path'].copy()
    buffered_gdf['geometry'] = buffered_gdf['geometry'].buffer(initial_tolerance)
    # Combine (merge) intersecting buffered geometries
    merged_buffers = unary_union(buffered_gdf['geometry'])

    # Ensure merged_buffers is a valid geometry
    if not merged_buffers.is_valid:
        print("Invalid geometry detected. Attempting to fix...")
        merged_buffers = merged_buffers.buffer(0)
        if not merged_buffers.is_valid:
            print("Failed to fix geometry.")
            print(explain_validity(merged_buffers))
            # Handle the invalid geometry case
        else:
            print("Geometry fixed.")

    # Proceed if the geometry is valid
    centerlines = []
    if merged_buffers.is_valid:
        # Check if merged_buffers is a MultiPolygon or Polygon
        if isinstance(merged_buffers, (Polygon, MultiPolygon)):
            # Get individual polygons
            polygons = [merged_buffers] if isinstance(merged_buffers, Polygon) else merged_buffers.geoms
            for poly in polygons:
                # Simplify polygon if necessary
                simplified_poly = poly.simplify(tolerance=1.0, preserve_topology=True)
                # Apply centerline operation
                centerline = pygeoops.centerline(simplified_poly)
                if centerline.is_empty:
                    print("Centerline is empty for a polygon.")
                else:
                    # If centerline is a MultiLineString, extract LineStrings
                    if isinstance(centerline, LineString):
                        centerlines.append(centerline)
                    elif isinstance(centerline, MultiLineString):
                        centerlines.extend(centerline.geoms)
                    else:
                        print(f"Unexpected geometry type from centerline: {type(centerline)}")
        else:
            centerline_geom = None
    else:
        centerline_geom = None

    if len(centerlines) > 0:
        # Create a GeoDataFrame for the centerlines with 'path' as the geometry column
        centerline_gdf = gpd.GeoDataFrame({'name': ['path'] * len(centerlines)},
                                          crs=gdf.crs,
                                          geometry=centerlines)
        other_cat = pd.concat([other_cat, centerline_gdf], ignore_index=True)

        # Save the centerline GeoDataFrame as GeoJSON
        other_cat.to_file(os.path.join(centerline_geojson_file, 'output.geojson'),
                          driver="GeoJSON")

        print(f"Centerline saved as GeoJSON at: {centerline_geojson_file}")
    else:
        print("No valid centerline could be generated.")


import os
import zipfile


def remove_tif_file(folder_path):
    """Remove the only .tif file in the given folder."""
    try:
        # List all files in the folder
        files = [f for f in os.listdir(folder_path) if f.endswith('.tif')]
        for file in files:
            file_path = os.path.join(folder_path, file)
            print(file_path)
            os.remove(file_path)
    except Exception as e:
        print(f"Error: {e}")


def zip_folder(folder_path, zip_file_path):
    """Create a ZIP file of the given folder."""
    try:
        # Create a zip file at the specified location
        with zipfile.ZipFile(zip_file_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            # Walk the folder and add all files to the zip file
            for root, dirs, files in os.walk(folder_path):
                for file in files:
                    file_path = os.path.join(root, file)
                    zipf.write(file_path, os.path.relpath(file_path, folder_path))
        print(f"Folder successfully zipped into: {zip_file_path}")
    except Exception as e:
        print(f"Error: {e}")


# @login_required(login_url='login')
@csrf_exempt
def index(request):
    """Handle the main request for the application, including file uploads and processing."""
    folder = 'static/input_img/'

    # Remove previous runs, input images, results, centers, and locations
    try:
        run_remove = glob.glob('runs/*')
        for f in run_remove:
            shutil.rmtree(f)
        run_remove = glob.glob('static/input_img/*')
        for f in run_remove:
            shutil.rmtree(f)
        run_remove = glob.glob('static/result/*')
        for f in run_remove:
            shutil.rmtree(f)
        run_remove = glob.glob('static/centers/*')
        for f in run_remove:
            os.remove(f)
        run_remove = glob.glob('static/zip/*')
        for f in run_remove:
            os.remove(f)
        run_remove = glob.glob('static/location/*')
        for f in run_remove:
            os.remove(f)
        run_remove = glob.glob('static/zip_folder/*')
        for f in run_remove:
            shutil.rmtree(f)
    except:
        pass

    if request.method == "POST":
        print("Working start...")
        main_host = request.get_host()  # Get the host name of the current request
        zip_file = request.FILES.get('file')  # Retrieve the uploaded zip file
        # Retrieve the uploaded zip file
        model_selection = request.POST['model']  # Retrieve the selected model from the form
        model_name = request.POST['model_name']  # Retrieve the selected model from the form
        print("Selected model:", model_selection)

        tif_file = request.FILES.get('tif_file')  # Retrieve the uploaded TIFF file, if any
        folder_name = '12345'
        if tif_file is not None:
            current_datetime = datetime.now()
            folder_name = current_datetime.strftime("%Y-%m-%d_%H-%M-%S")  # Create a folder name based on current time
            folder_path = os.path.join(folder, folder_name)
            location = FileSystemStorage(location=folder_path)
            fn = location.save(tif_file.name, tif_file)
            path = os.path.join(folder_path, fn)
            tif_main(path, folder_path)
            tif_to_jwg(folder_path)  # Convert TIFF file to JGW world file
            output_folder = os.path.join('static/result/', folder_name)
            os.makedirs(output_folder)
            output_images_list = []
            input_images_list = []
            final_list = []
            if model_selection == "summer":
                print("Using Summer Model/////////////////////.")
                model = YOLO(f'static/models/germany_summer_ai_model/{model_name}')
                # model = YOLO(f'static/models/germany_summer_ai_model/new_one_last.pt')
                # model = YOLO(user_model_path)
            elif model_selection == "winter":
                print("Using Winter Model/////////////////////")
                model = YOLO(f'static/models/germany_winter_ai_model/{model_name}')
            for file_name in os.listdir(folder_path):
                file_path = os.path.join(folder_path, file_name)
                if os.path.isfile(file_path) and file_name.lower().endswith(('.jpg', '.jpeg')):
                    image = Image.open(file_path)
                    # Run the prediction model on the image
                    flag, ori_path, boxes, img_count, box_ls, postion_ls, center_ls = prediction(image, model)
                    output_directory = 'static/centers'
                    using_box_find_center_point(boxes, postion_ls, output_directory, file_name, image)
                    output_path = f'{output_folder}/{file_name}'
                    if flag:
                        width, height = image.size
                        final_list.append({
                            file_name: {
                                "img_width": width,
                                "img_height": height,
                                "image_details": img_count,
                                "polygon_area": postion_ls,
                                "center_point": center_ls,
                                "bbox": box_ls
                            }
                        })

                        ori_path.save(output_path)  # Save the processed image
                        input_images_list.append(f'/{file_path}')
                        output_images_list.append(f'/{output_path}')

            centers_directory = 'static/centers'
            data_directory = folder_path
            output_directory = "static/location"

            location_point(centers_directory, data_directory, output_directory)
            output_geojson_file = "static/tiff_output.geojson"
            genrate_json_json(output_directory, output_geojson_file, model_selection)
            initial_tolerance = 10
            try:
                process_geojson(output_geojson_file, initial_tolerance, 'static')
            except:
                pass
            remove_tif_file(folder_path)
           
            zip_path = f'static/zip/{folder_name}.zip'
            zip_folder(folder_path, zip_path)

            final_dict_list = {
                "final_result": final_list
            }
            json_path = 'static/json/output.json'

            with open(json_path, "w") as json_file:
                json.dump(final_dict_list, json_file)

            # context = {
            #     "status": True,
            #     "error": '',
            #     "geojson_path": f'/{output_geojson_file}',
            #     "zip_path": f"/{zip_path}",
            #     "input_image_list": input_images_list,
            #     "output_image_list": output_images_list,
            #     "json_path": f'{main_host}/{json_path}',
            # }
            with open(json_path, "w") as json_file:
                json.dump(final_dict_list, json_file)

            context = {
                "status": True,
                "error": '',
                "geojson_path": f'/{output_geojson_file}',
                "zip_path": f'/{zip_path}',
                "input_image_list": input_images_list,
                "output_image_list": output_images_list,
                "json_path": f'{main_host}/{json_path}',
            }

            return JsonResponse(context)

        current_datetime = datetime.now()
        z_folder = 'static/zip_folder/'
        folder_name = current_datetime.strftime("%Y-%m-%d_%H-%M-%S")
        zip_folder_path = os.path.join(z_folder, folder_name)
        folder_path = os.path.join(folder, folder_name)
        os.makedirs(folder_path)
        os.makedirs(zip_folder_path)
        output_folder = os.path.join('static/result/', folder_name)
        os.makedirs(output_folder)
        output_images_list = []
        input_images_list = []
        final_list = []

        zip_file_name = zip_file.name
        try:
            location = FileSystemStorage(location=zip_folder_path)
            fn = location.save(zip_file.name, zip_file)
            output_zip = os.path.join(zip_folder_path, fn)
            unzip_file(output_zip, folder_path)
            filename_without_extension = os.path.splitext(zip_file_name)[0]

            exclude_folders = {'__MACOSX'}
            for f in os.listdir(folder_path):
                if os.path.isdir(os.path.join(folder_path, f)) and f not in exclude_folders:
                    folder_path = os.path.join(folder_path, f)
                    break

            file_names = os.listdir(folder_path)

            # Ensure all image files have corresponding JGW files
            image_files = [filename for filename in file_names if filename.endswith('.jpeg')]
            for image_file in image_files:
                jgw_file = image_file.replace('.jpeg', '.jgw')
                if jgw_file not in file_names:
                    context = {
                        "status": False,
                        "error": f"No corresponding .jgw file found for {image_file}",
                    }
                    return JsonResponse(context)

            if model_selection == "summer":
                print("Using Summer Model/////////////////////.")
                model = YOLO(f'static/models/germany_summer_ai_model/{model_name}')
                # model = YOLO(f'static/models/germany_summer_ai_model/new_one_last.pt')
                # model = YOLO(user_model_path)
            elif model_selection == "winter":
                print("Using Winter Model/////////////////////")
                model = YOLO(f'static/models/germany_winter_ai_model/{model_name}')
                # model = YOLO('static/models/germany_winter_ai_model/best.pt')
                # model = YOLO(user_model_path)

            for file in os.listdir(folder_path):
                path = os.path.join(folder_path, file)
                file_name = file
                image_extensions = ['.png', '.jpg', '.jpeg', '.gif', '.bmp']
                base_name, extension = os.path.splitext(file_name)

                if extension == ".jgw":
                    print("The file has a .jgw extension.")
                elif path == 'pra/test/.DS_Store':
                    pass
                elif extension in image_extensions:
                    print("file_name:", file_name)
                    image = Image.open(path)
                    # Run the prediction model on the image
                    flag, ori_path, boxes, img_count, box_ls, postion_ls, center_ls = prediction(image, model)
                    output_directory = 'static/centers'
                    using_box_find_center_point(boxes, postion_ls, output_directory, file_name, image)
                    output_path = f'{output_folder}/{file_name}'
                    if flag:
                        width, height = image.size
                        final_list.append({
                            file_name: {
                                "img_width": width,
                                "img_height": height,
                                "image_details": img_count,
                                "polygon_area": postion_ls,
                                "center_point": center_ls,
                                "bbox": box_ls
                            }
                        })

                        ori_path.save(output_path)  # Save the processed image
                        input_images_list.append(f'/{path}')
                        output_images_list.append(f'/{output_path}')

            centers_directory = 'static/centers'
            data_directory = folder_path
            output_directory = "static/location"

            location_point(centers_directory, data_directory, output_directory)
            output_geojson_file = "static/output.geojson"
            genrate_json_json(output_directory, output_geojson_file, model_selection)
            initial_tolerance = 10
            process_geojson(output_geojson_file, initial_tolerance, 'static')
            remove_tif_file(folder_path)
            zip_path = f'static/zip/{folder_name}.zip'
            zip_folder(folder_path, zip_path)

            final_dict_list = {
                "final_result": final_list
            }
            json_path = 'static/json/output.json'

            with open(json_path, "w") as json_file:
                json.dump(final_dict_list, json_file)

            context = {
                "status": True,
                "error": '',
                "geojson_path": f'/{output_geojson_file}',
                "zip_path": f'/{zip_path}',
                "input_image_list": input_images_list,
                "output_image_list": output_images_list,
                "json_path": f'{main_host}/{json_path}',
            }

            return JsonResponse(context)
        except Exception as e:
            context = {
                "status": False,
                "error": str(e),
                "geojson_path": '',
                "zip_path": '',
                "input_image_list": '',
                "output_image_list": '',
                "json_path": '',
            }
            return JsonResponse(context)

    return render(request, 'index.html')


def get_date_time_for_naming():
    """Generate a timestamp string suitable for naming files."""
    (dt, micro) = datetime.utcnow().strftime('%Y%m%d%H%M%S.%f').split('.')
    dt_dateTime = "%s%03d" % (dt, int(micro) / 1000)
    return dt_dateTime



@csrf_exempt
def geo_json_path(request):
    """Handle the main request for the application, including file uploads and processing."""
    folder = 'static/output.geojson'
    geojson_data = {}
    with open(folder, 'r') as geojson_file:
        geojson_data = json.load(geojson_file)
    tiff_geojson_data = {}

    with open('static/tiff_output.geojson', 'r') as geojson_file:
        tiff_geojson_data = json.load(geojson_file)
    dict= {
        "geo_path":folder,
        "geojson_data":geojson_data,
        "tiff_geo_path":'static/tiff_output.geojson',
        "tiff_geojson_data": tiff_geojson_data,
    }
    return JsonResponse(dict)