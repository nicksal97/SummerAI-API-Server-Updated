from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
from django.core.files.storage import FileSystemStorage
from infrince import prediction
import glob
from PIL import Image
import json
import shutil
from datetime import datetime
import rasterio
from pathlib import Path
import os

BASE_DIR = Path(__file__).resolve().parent.parent
import cv2
from .Splitting_TIFF_file_Concise import tif_main
import numpy


def calculate_center_points(line, output_image_path):
    parts = line.split()
    bounding_coordinates = [float(x) for x in parts[1:]]

    # Divide the coordinates into pairs of X and Y
    x_coordinates = bounding_coordinates[::2]  # Extract even-indexed elements
    y_coordinates = bounding_coordinates[1::2]  # Extract odd-indexed elements

    # Calculate the center point
    center_x = sum(x_coordinates) / len(x_coordinates)
    center_y = sum(y_coordinates) / len(y_coordinates)

    image_height, image_width, _ = output_image_path.shape
    center_x1 = int(center_x * image_width)
    center_y1 = int(center_y * image_height)
    center_point = (center_x1, center_y1)

    cv2.circle(output_image_path, center_point, 5, (255, 0, 0), -1)

    return center_x, center_y
    # return None


def create_center_point(input_directory, output_directory, output_image_path):
    input_directory = '/Users/psi-square/Documents/all_dwon/mirkhagan-ml_tree_detection-e3ae0fe15c65/tree_project/runs/detect/predict/labels'
    for input_filename in os.listdir(input_directory):
        if input_filename.endswith(".txt"):
            input_filepath = os.path.join(input_directory, input_filename)
            output_filepath = os.path.join(output_directory, input_filename)
            print(input_filename)

            with open(input_filepath, "r") as input_file:
                lines = input_file.readlines()

            center_points = []

            for line in lines:
                center_point = calculate_center_points(line, output_image_path)
                if center_point:
                    center_points.append(center_point)

            with open(output_filepath, "w") as output_file:
                for center_x, center_y in center_points:
                    output_file.write(f"{center_x} {center_y}\n")


def convert_to_txt(filename):
    # Check if the filename ends with a known image file extension
    image_extensions = [".png", ".jpg", ".jpeg", ".gif", ".bmp"]
    for ext in image_extensions:
        if filename.endswith(ext):
            # Remove the extension and add ".txt"
            return filename[:-len(ext)] + ".txt"
    # If the filename doesn't end with any known image file extension, just add ".txt"
    return filename + ".txt"


def using_box_find_center_point(boxes, output_directory, input_filename):
    center_points = []
    input_filename = convert_to_txt(input_filename)
    for box in boxes:
        xmin = float(box.data[0][0])
        ymin = float(box.data[0][1])
        xmax = float(box.data[0][2])
        ymax = float(box.data[0][3])
        #
        center_x = float((xmin + xmax) / 2)
        center_y = float((ymin + ymax) / 2)
        center_point = (center_x, center_y)
        center_points.append(center_point)
    output_filepath = os.path.join(output_directory, input_filename)
    with open(output_filepath, "w") as output_file:
        for center_x, center_y in center_points:
            output_file.write(f"{center_x} {center_y}\n")


def calculate_actual_coordinates(jgw_file_path, txt_file_path):
    # Read the JGW file

    with open(jgw_file_path, 'r') as jgw_file:
        jgw_lines = jgw_file.readlines()

    x_pixel_size = float(jgw_lines[0])
    y_rotation = float(jgw_lines[1])
    x_rotation = float(jgw_lines[2])
    y_pixel_size = float(jgw_lines[3])
    x_origin = float(jgw_lines[4])
    y_origin = float(jgw_lines[5])

    # Read normalized coordinates from the txt file
    with open(txt_file_path, 'r') as txt_file:
        lines = txt_file.readlines()

    # Initialize a list to store the actual coordinates
    actual_coordinates = []

    # Iterate through the lines in the text file
    for line in lines:
        parts = line.split()
        if len(parts) >= 2:
            normalized_x = float(parts[0])  # Get the first value as normalized X
            normalized_y = float(parts[1])  # Get the second value as normalized Y

            # Calculate actual coordinates, taking into account the negative y-pixel size
            actual_x = (normalized_x * 0.150) + x_origin
            actual_y = (normalized_y * -0.150) + y_origin

            actual_coordinates.append((actual_x, actual_y))

    return actual_coordinates


def location_point(centers_directory, data_directory, output_directory):
    label_files = [f for f in os.listdir(centers_directory) if f.endswith(".txt")]

    # Iterate through the list of label files and process them
    for label_file in label_files:
        label_file_path = os.path.join(centers_directory, label_file)

        # Create the corresponding jgw file path
        jgw_file_path = os.path.join(data_directory, label_file.replace(".txt", ".jgw"))

        # Calculate the actual coordinates
        actual_coordinates = calculate_actual_coordinates(jgw_file_path, label_file_path)

        # Now, actual_coordinates contains the actual geographic coordinates for the label file.
        # You can process or save these coordinates as needed.
        output_file_path = os.path.join(output_directory, label_file.replace(".txt", ".txt"))
        with open(output_file_path, 'w') as output_file:
            for i, (actual_x, actual_y) in enumerate(actual_coordinates, start=1):
                output_file.write(f'{actual_x} {actual_y}\n')


point_count = {}
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


def calculate_center_points_geojson(line, output_filename):
    parts = line.split()
    num_points = len(parts) // 2
    x_coordinates = [float(parts[i]) for i in range(0, len(parts), 2)]
    y_coordinates = [float(parts[i]) for i in range(1, len(parts), 2)]

    if output_filename not in point_count:
        point_count[output_filename] = 0

    # Create a new point for each X, Y pair
    for j, (x, y) in enumerate(zip(x_coordinates, y_coordinates), start=1):
        point_count[output_filename] += 1
        feature = {
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [x, y]
            },
            "properties": {
                "name": f"Point {point_count[output_filename]}",
                "description": f"This is from the image: {output_filename}.png"
            }
        }
        feature_collection["features"].append(feature)


def genrate_json_json(input_directory, output_geojson_file):
    for input_filename in os.listdir(input_directory):
        if input_filename.endswith(".txt"):
            input_filepath = os.path.join(input_directory, input_filename)
            output_filename = os.path.splitext(input_filename)[0]

            with open(input_filepath, "r") as input_file:
                lines = input_file.readlines()

            for line in lines:
                calculate_center_points_geojson(line, output_filename)

    with open(output_geojson_file, "w") as output_file:
        json.dump(feature_collection, output_file)


def tif_to_jwg(folder_path):
    for file_name in os.listdir(folder_path):
        file_path = os.path.join(folder_path, file_name)
        if os.path.isfile(file_path):
            if file_name.lower().endswith(('.tif', '.tiff')):
                print(file_path)
                file_name = file_name.split('.')[0]
                with rasterio.open(file_path) as src:
                    # Read georeferencing information
                    transform = src.transform  # Affine transformation matrix

                # Write georeferencing information to JGW file
                print('start')
                print(transform)
                print('end')

                with open(f'{folder_path}/{file_name}.jgw', 'w') as jgw_file:
                    # Write the transformation parameters in the correct order
                    jgw_file.write(f"{transform.a}\n")  # Pixel width
                    jgw_file.write(f"{transform.e}\n")  # Pixel height (negative in case of North-up)
                    jgw_file.write(f"{transform.c}\n")  # X-coordinate of the upper-left corner
                    jgw_file.write(f"{transform.f}\n")  # Y-coordinate of the upper-left corner
                    jgw_file.write("0.0\n")  # Ignore rotation or skew parameters
                    jgw_file.write("0.0\n")


@csrf_exempt
def index(request):
    global encodeimg, polygon_points, res_img, ori_path
    folder = 'static/input_img/'
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
    run_remove = glob.glob('static/location/*')
    for f in run_remove:
        os.remove(f)
    if request.method == "POST":
        main_host = request.get_host()
        files = request.FILES.getlist('file')

        tif_file = request.FILES.get('tif_file')
        if tif_file is not None:
            current_datetime = datetime.now()
            folder_name = current_datetime.strftime("%Y-%m-%d_%H-%M-%S")
            folder_path = os.path.join(folder, folder_name)
            location = FileSystemStorage(location=folder_path)
            fn = location.save(tif_file.name, tif_file)
            path = os.path.join(folder_path, fn)
            tif_main(path, folder_path)
            tif_to_jwg(folder_path)
            output_folder = os.path.join('static/result/', folder_name)
            os.makedirs(output_folder)
            output_images_list = []
            input_images_list = []
            final_list = []
            for file_name in os.listdir(folder_path):
                file_path = os.path.join(folder_path, file_name)
                if os.path.isfile(file_path):
                    if file_name.lower().endswith(('.jpg', '.jpeg')):
                        image = Image.open(file_path)
                        print(file_path)
                        flag, ori_path, boxes, img_count, box_ls, postion_ls, center_ls = prediction(image)
                        output_directory = 'static/centers'
                        using_box_find_center_point(boxes, output_directory, file_name)
                        output_path = f'{output_folder}/{file_name}'
                        if flag == True:
                            # image = Image.open(output_path)
                            width, height = image.size
                            final_list.append(
                                {file_name: {"img_width": width, "img_height": height, "image_details": img_count,
                                             "polygon_area": postion_ls, "center_point": center_ls,
                                             "bbox": box_ls}})

                            ori_path.save(output_path)
                            input_image_path = f'{main_host}/{path}'
                            output_image_path = f'{main_host}/{output_path}'
                            input_images_list.append(input_image_path)
                            output_images_list.append(output_image_path)

            centers_directory = 'static/centers'
            data_directory = folder_path

            output_directory = "static/location"

            location_point(centers_directory, data_directory, output_directory)

            output_geojson_file = "static/output.geojson"

            genrate_json_json(output_directory, output_geojson_file)

            final_dict_list = {
                "final_result": final_list
            }
            json_path = f'static/json/output.json'

            with open(json_path, "w") as json_file:
                json.dump(final_dict_list, json_file)

            context = {
                "status": True,
                "geojson_path": f'{main_host}/{output_geojson_file}',
                "input_image_list": input_images_list,
                "output_image_list": output_images_list,
                "json_path": f'{main_host}/{json_path}'
            }

            return JsonResponse(context)

        file_names = [file.name for file in files]

        image_files = [filename for filename in file_names if filename.endswith('.jpeg')]

        for image_file in image_files:
            jgw_file = image_file.replace('.jpeg', '.jgw')
            if jgw_file not in file_names:
                context = {
                    "status": False,
                    "error": f"No corresponding .jgw file found for {image_file}",
                }
                print(f"No corresponding .jgw file found for {image_file}")
                return JsonResponse(context)

        current_datetime = datetime.now()
        folder_name = current_datetime.strftime("%Y-%m-%d_%H-%M-%S")
        folder_path = os.path.join(folder, folder_name)
        os.makedirs(folder_path)
        output_folder = os.path.join('static/result/', folder_name)
        os.makedirs(output_folder)
        output_images_list = []
        input_images_list = []
        final_list = []

        for file in files:
            location = FileSystemStorage(location=folder_path)
            fn = location.save(file.name, file)
            path = os.path.join(folder_path, fn)
            base_name, extension = os.path.splitext(file.name)

            if extension == ".jgw":
                print("The file has a .jgw extension.")
            else:
                image = Image.open(path)
                flag, ori_path, boxes, img_count, box_ls, postion_ls, center_ls = prediction(image)
                output_directory = 'static/centers'
                using_box_find_center_point(boxes, output_directory, file.name)
                output_path = f'{output_folder}/{file.name}'
                if flag == True:
                    # image = Image.open(output_path)
                    width, height = image.size
                    final_list.append({file.name: {"img_width": width, "img_height": height, "image_details": img_count,
                                                   "polygon_area": postion_ls, "center_point": center_ls,
                                                   "bbox": box_ls}})

                    ori_path.save(output_path)
                    input_image_path = f'{main_host}/{path}'
                    output_image_path = f'{main_host}/{output_path}'
                    input_images_list.append(input_image_path)
                    output_images_list.append(output_image_path)

        centers_directory = 'static/centers'
        data_directory = folder_path

        output_directory = "static/location"

        location_point(centers_directory, data_directory, output_directory)

        output_geojson_file = "static/output.geojson"

        genrate_json_json(output_directory, output_geojson_file)

        final_dict_list = {
            "final_result": final_list
        }
        json_path = f'static/json/output.json'

        with open(json_path, "w") as json_file:
            json.dump(final_dict_list, json_file)

        context = {
            "status": True,
            "geojson_path": f'{main_host}/{output_geojson_file}',
            "input_image_list": input_images_list,
            "output_image_list": output_images_list,
            "json_path": f'{main_host}/{json_path}',
        }

        return JsonResponse(context)
    return render(request, 'index.html')


def get_date_time_for_naming():
    (dt, micro) = datetime.utcnow().strftime('%Y%m%d%H%M%S.%f').split('.')
    dt_dateTime = "%s%03d" % (dt, int(micro) / 1000)
    return dt_dateTime



