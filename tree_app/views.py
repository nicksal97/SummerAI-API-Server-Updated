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
import zipfile

BASE_DIR = Path(__file__).resolve().parent.parent

# from .Splitting_TIFF_file_Concise import tif_main



def calculate_center_points(line, output_image_path):
    parts = line.split()
    bounding_coordinates = [float(x) for x in parts[1:]]

    # Divide the coordinates into pairs of X and Y
    x_coordinates = bounding_coordinates[::2]  # Extract even-indexed elements
    y_coordinates = bounding_coordinates[1::2]  # Extract odd-indexed elements

    # Calculate the center point
    center_x = sum(x_coordinates) / len(x_coordinates)
    center_y = sum(y_coordinates) / len(y_coordinates)

    # image_height, image_width = output_image_path.shape
    # center_x1 = int(center_x * image_width)
    # center_y1 = int(center_y * image_height)
    # center_point = (center_x1, center_y1)
    #
    # cv2.circle(output_image_path, center_point, 5, (255, 0, 0), -1)

    return center_x, center_y
    # return None


def create_center_point(input_directory, output_directory, output_image_path):
    # input_directory = '/Users/psi-square/Documents/all_dwon/mirkhagan-ml_tree_detection-e3ae0fe15c65/tree_project/runs/detect/predict/labels'
    for input_filename in os.listdir(input_directory):
        if input_filename.endswith(".txt"):
            input_filepath = os.path.join(input_directory, input_filename)
            output_filepath = os.path.join(output_directory, input_filename)


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

def convert_to_json(filename):
    # Check if the filename ends with a known image file extension
    image_extensions = [".png", ".jpg", ".jpeg", ".gif", ".bmp"]
    for ext in image_extensions:
        if filename.endswith(ext):
            # Remove the extension and add ".txt"
            return filename[:-len(ext)] + ".json"
    # If the filename doesn't end with any known image file extension, just add ".txt"
    return filename + ".json"


def using_box_find_center_point(boxes,postion_ls, output_directory, input_filename,output_image_path):
    center_points = []
    input_filename_txt = convert_to_txt(input_filename)
    # for box in boxes:
    #     xmin = float(box.data[0][0])
    #     ymin = float(box.data[0][1])
    #     xmax = float(box.data[0][2])
    #     ymax = float(box.data[0][3])
    #     #
    #     center_x = float((xmin + xmax) / 2)
    #     center_y = float((ymin + ymax) / 2)
    #     center_point = (center_x, center_y)
    #     center_points.append(center_point)
    # input_directory = '/Users/psi-square/Desktop/code/API-Germany-SummerAI-main/runs/segment/predict/labels'
    #input_directory = '/var/opt/API-Germany-SummerAI-main/runs/segment/predict/labels'
    input_directory = 'C:/Users/ACER/Downloads/CodeAI/API-Germany-SummerAI-main/runs/segment/predict/labels'

    input_filepath = os.path.join(input_directory, input_filename_txt)
    # output_filepath = os.path.join(output_directory, input_filename)
    # print(input_filename)
    try:

        with open(input_filepath, "r") as input_file:
            lines = input_file.readlines()

        center_points = []

        for line in lines:
            center_point = calculate_center_points(line, output_image_path)
            if center_point:
                center_points.append(center_point)

        input_filename = convert_to_json(input_filename)
        output_filepath = os.path.join(output_directory, input_filename)

        final_dict_list = {
            "xy_point": center_points,
            "polygone_area":postion_ls,
        }
        # print(final_dict_list)

        with open(output_filepath, "w") as json_file:
            json.dump(final_dict_list, json_file)
    except:
        pass


    # with open(output_filepath, "w") as output_file:
    #     for center_x, center_y in center_points:
    #         output_file.write(f"{center_x} {center_y}\n")


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
    # with open(txt_file_path, 'r') as txt_file:
    #     lines = txt_file.readlines()
    with open(txt_file_path, 'r') as file:
        data = json.load(file)
    actual_coordinates = []
    lines = data['xy_point']
    polygone_area_data = data['polygone_area']
    origin_value = x_pixel_size
    for poly in polygone_area_data:
        all_line_value = poly['line_value']

        if all_line_value is not False:
            transformed_coordinates = []
            for value in all_line_value:
                a = value[0]
                b = value[1]
                actual_x1 = (float(a[0]) * origin_value) + x_origin
                actual_y1 = (float(a[1]) * -origin_value) + y_origin

                actual_x2 = (float(b[0]) * origin_value) + x_origin
                actual_y2 = (float(b[1]) * -origin_value) + y_origin

                #
                transformed_coordinates.append((actual_x1, actual_y1))
                transformed_coordinates.append((actual_x2, actual_y2))

                # transformed_coordinates.append([actual_x1,actual_x2])
                # transformed_coordinates.append([actual_y1, actual_y2])



            poly['line_value'] = transformed_coordinates



    for line in lines:
        parts = line
        if len(parts) >= 2:
            normalized_x = float(parts[0])  # Get the first value as normalized X
            normalized_y = float(parts[1])  # Get the second value as normalized Y

            # Calculate actual coordinates, taking into account the negative y-pixel size
            actual_x = (normalized_x * 100) + x_origin
            actual_y = (normalized_y * -100) + y_origin

            actual_coordinates.append((actual_x, actual_y))


    return actual_coordinates,data['polygone_area']


def location_point(centers_directory, data_directory, output_directory):
    label_files = [f for f in os.listdir(centers_directory) if f.endswith(".json")]

    # Iterate through the list of label files and process them
    for label_file in label_files:
        label_file_path = os.path.join(centers_directory, label_file)

        # Create the corresponding jgw file path
        jgw_file_path = os.path.join(data_directory, label_file.replace(".json", ".jgw"))

        # Calculate the actual coordinates
        actual_coordinates,polygone_area_list = calculate_actual_coordinates(jgw_file_path, label_file_path)

        # Now, actual_coordinates contains the actual geographic coordinates for the label file.
        # You can process or save these coordinates as needed.
        output_file_path = os.path.join(output_directory, label_file.replace(".json", ".json"))

        final_dict_list = {
            "actual_coordinates": actual_coordinates,
            "polygone_area": polygone_area_list,
        }

        with open(output_file_path, "w") as json_file:
            json.dump(final_dict_list, json_file)


        # output_file_path = os.path.join(output_directory, label_file.replace(".txt", ".txt"))
        # with open(output_file_path, 'w') as output_file:
        #     for i, (actual_x, actual_y) in enumerate(actual_coordinates, start=1):
        #         output_file.write(f'{actual_x} {actual_y}\n')


# point_count = {}
# feature_collection = {
#     "type": "FeatureCollection",
#     "name": "single-tree",
#     "crs": {
#         "type": "name",
#         "properties": {
#             "name": "urn:ogc:def:crs:EPSG::3857"
#         }
#     },
#     "features": []
# }


def calculate_center_points_geojson(line,polygone_area, output_filename):
    detection_point_name = list(polygone_area.keys())[0]
    polygone_area_value = polygone_area[detection_point_name]
    # print(polygone_area['line_value'])
    # if detection_point_name == 'building' or detection_point_name == 'tree' or detection_point_name == 'under-construction':
    parts = line

    # num_points = len(parts) // 2
    x_coordinates = [float(parts[i]) for i in range(0, len(parts), 2)]
    y_coordinates = [float(parts[i]) for i in range(1, len(parts), 2)]

    # if output_filename not in point_count:
    #     point_count[output_filename] = 0




    # for key, value in polygone_area.items():
    #     detectet_point_name

    # Create a new point for each X, Y pair
    # id_value = point_count[output_filename] += 1


    if 'path' in detection_point_name:
        coordinates = polygone_area['line_value']
    else:
        coordinates = [x_coordinates[0], y_coordinates[0]]
    return output_filename,coordinates,detection_point_name,polygone_area_value


    # for j, (x, y) in enumerate(zip(x_coordinates, y_coordinates), start=1):
    #     point_count[output_filename] += 1
    #     if 'path' in detection_point_name:
    #         feature = {
    #             "type": "Feature",
    #             "geometry": {
    #                 "type": "LineString",
    #                 "coordinates": polygone_area['line_value']
    #             },
    #             "properties": {
    #                 "id": point_count[output_filename],
    #                 "name": f"{detection_point_name}",
    #                 "description": f"{output_filename}.png",
    #                 "polygon_area": f"{polygone_area_value}",
    #                 # "LineString": polygone_area['line_value'],
    #             },
    #
    #         }
    #     else:
    #         feature = {
    #             "type": "Feature",
    #             "geometry": {
    #                 "type": "Point",
    #                 "coordinates": [x, y]
    #             },
    #             "properties": {
    #                 "id": point_count[output_filename],
    #                 "name": f"{detection_point_name}",
    #                 "description": f"{output_filename}.png",
    #                 "polygon_area": f"{polygone_area_value}",
    #             },
    #
    #         }
    #     feature_collection["features"].append(feature)


def genrate_json_json(input_directory, output_geojson_file):
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

    for input_filename in os.listdir(input_directory):
        if input_filename.endswith(".json"):
            input_filepath = os.path.join(input_directory, input_filename)
            output_filename = os.path.splitext(input_filename)[0]

            # with open(input_filepath, "r") as input_file:
            #     lines = input_file.readlines()
            with open(input_filepath, 'r') as file:
                data = json.load(file)
            id = 0



            for line,polygone_area in zip(data['actual_coordinates'],data['polygone_area']):
                output_filename,coordinates,detection_point_name,polygone_area_value = calculate_center_points_geojson(line,polygone_area, output_filename)
                id += 1

                if 'path' in detection_point_name:
                    feature = {
                        "type": "Feature",
                        "geometry": {
                            "type": "LineString",
                            "coordinates": polygone_area['line_value']
                        },
                        "properties": {
                            "id": id,
                            "name": f"{detection_point_name}",
                            "description": f"{output_filename}.png",
                            "polygon_area": f"{polygone_area_value}",
                            # "LineString": polygone_area['line_value'],
                        },

                    }
                else:
                    feature = {
                        "type": "Feature",
                        "geometry": {
                            "type": "Point",
                            "coordinates": coordinates
                        },
                        "properties": {
                            "id": id,
                            "name": f"{detection_point_name}",
                            "description": f"{output_filename}.png",
                            "polygon_area": f"{polygone_area_value}",
                        },

                    }
                feature_collection["features"].append(feature)

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


                with open(f'{folder_path}/{file_name}.jgw', 'w') as jgw_file:
                    # Write the transformation parameters in the correct order
                    jgw_file.write(f"{transform.a}\n")  # Pixel width
                    jgw_file.write(f"{transform.e}\n")  # Pixel height (negative in case of North-up)
                    jgw_file.write(f"{transform.c}\n")  # X-coordinate of the upper-left corner
                    jgw_file.write(f"{transform.f}\n")  # Y-coordinate of the upper-left corner
                    jgw_file.write("0.0\n")  # Ignore rotation or skew parameters
                    jgw_file.write("0.0\n")


def unzip_file(zip_path, extract_to):
    with zipfile.ZipFile(zip_path, 'r') as zipf:
        zipf.extractall(extract_to)



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
    run_remove = glob.glob('static/zip_folder/*')
    for f in run_remove:
        shutil.rmtree(f)
    if request.method == "POST":
        # output_geojson_file = "static/output.geojson"
        # with open(output_geojson_file, "w") as output_file:
        #     json.dump(feature_collection, output_file)
        main_host = request.get_host()
        # files = request.FILES.getlist('files')
        zip_file = request.FILES.get('file')
        model_selection = request.POST['model']
        print("selected model:",model_selection)


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
                        flag, ori_path, boxes, img_count, box_ls, postion_ls, center_ls = prediction(image,model_selection)
                        output_directory = 'static/centers'
                        using_box_find_center_point(boxes, output_directory, file_name,image)
                        output_path = f'{output_folder}/{file_name}'
                        if flag == True:
                            # image = Image.open(output_path)
                            width, height = image.size
                            final_list.append(
                                {file_name: {"img_width": width, "img_height": height, "image_details": img_count,
                                             "polygon_area": postion_ls, "center_point": center_ls,
                                             "bbox": box_ls}})

                            ori_path.save(output_path)
                            input_image_path = f'/{path}'
                            output_image_path = f'/{output_path}'
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

        # file_names = [file.name for file in files]
        #
        # image_files = [filename for filename in file_names if filename.endswith('.jpeg')]
        #
        # for image_file in image_files:
        #     jgw_file = image_file.replace('.jpeg', '.jgw')
        #     if jgw_file not in file_names:
        #         context = {
        #             "status": False,
        #             "error": f"No corresponding .jgw file found for {image_file}",
        #         }
        #         print(f"No corresponding .jgw file found for {image_file}")
        #         return JsonResponse(context)

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
            # zip_folder(folder_path, output_zip)
            unzip_file(output_zip, folder_path)
            filename_without_extension = os.path.splitext(zip_file_name)[0]
            # folder_path = f'{folder_path}/{filename_without_extension}'
            # folder_path = f'{folder_path}/{filename_without_extension}'

            exclude_folders = {'__MACOSX'}
            for f in os.listdir(folder_path):
                if os.path.isdir(os.path.join(folder_path, f)) and f not in exclude_folders:
                    folder_path = f'{folder_path}/{f}'
                    break

            file_names = os.listdir(folder_path)

            # Filter out .jpeg files
            image_files = [filename for filename in file_names if filename.endswith('.jpeg')]

            # Check for corresponding .jgw files
            for image_file in image_files:
                jgw_file = image_file.replace('.jpeg', '.jgw')
                if jgw_file not in file_names:
                    context = {
                        "status": False,
                        "error": f"No corresponding .jgw file found for {image_file}",
                    }
                    return JsonResponse(context)







            for file in os.listdir(folder_path):
                path = os.path.join(folder_path, file)
                file_name =file
                # location = FileSystemStorage(location=folder_path)
                # fn = location.save(file.name, file)
                image_extensions = ['.png', '.jpg', '.jpeg', '.gif', '.bmp']
                base_name, extension = os.path.splitext(file_name)

                if extension == ".jgw":
                    print("The file has a .jgw extension.")
                elif path == 'pra/test/.DS_Store':
                    pass
                elif extension in image_extensions:
                    # count += 1
                    image = Image.open(path)
                    flag, ori_path, boxes, img_count, box_ls, postion_ls, center_ls = prediction(image,model_selection)
                    output_directory = 'static/centers'
                    using_box_find_center_point(boxes,postion_ls, output_directory, file_name,image)
                    output_path = f'{output_folder}/{file_name}'
                    if flag == True:
                        # image = Image.open(output_path)
                        width, height = image.size
                        final_list.append({file_name: {"img_width": width, "img_height": height, "image_details": img_count,
                                                       "polygon_area": postion_ls, "center_point": center_ls,
                                                       "bbox": box_ls}})

                        ori_path.save(output_path)
                        input_image_path = f'/{path}'
                        output_image_path = f'/{output_path}'
                        input_images_list.append(input_image_path)
                        output_images_list.append(output_image_path)

            centers_directory = 'static/centers'
            data_directory = folder_path

            output_directory = "static/location"

            location_point(centers_directory, data_directory, output_directory)

            output_geojson_file = f"static/output.geojson"

            genrate_json_json(output_directory, output_geojson_file)

            final_dict_list = {
                "final_result": final_list
            }
            json_path = f'static/json/output.json'

            with open(json_path, "w") as json_file:
                json.dump(final_dict_list, json_file)

            context = {
                "status": True,
                "error": '',
                "geojson_path": f'/{output_geojson_file}',
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
                "input_image_list": '',
                "output_image_list": '',
                "json_path": '',
            }
            return JsonResponse(context)

    return render(request, 'index.html')


def get_date_time_for_naming():
    (dt, micro) = datetime.utcnow().strftime('%Y%m%d%H%M%S.%f').split('.')
    dt_dateTime = "%s%03d" % (dt, int(micro) / 1000)
    return dt_dateTime



