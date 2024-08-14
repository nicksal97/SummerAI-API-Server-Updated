from ultralytics import YOLO
from PIL import Image
from io import BytesIO
import cv2
import numpy as np
# from shapely.geometry import Polygon
from shapely.geometry import Polygon

import matplotlib.pyplot as plt
from shapely.geometry import Polygon,LineString
# from centerline.geometry import Centerline
# from centerline.geometry import Centerline
# import matplotlib.pyplot as plt

import pygeoops
import shapely
import shapely.plotting
from shapely.ops import unary_union
from shapely.ops import unary_union, linemerge
from shapely.geometry import LineString, MultiLineString

from shapely.wkt import loads

# model = YOLO('/Users/psi-square/Documents/all_dwon/mirkhagan-ml_tree_detection-e3ae0fe15c65/tree_project/static/models/weights/last.pt')
#model = YOLO('static/models/germany_summer_ai_model/new_one_last.pt')
#model = YOLO('static/models/400_m_Germany_Winter_Model/weights/best.pt')

def polygon_area(vertices):
    polygon_ = Polygon(vertices)
    area = polygon_.area
    return area


def multiline_to_coordinates(multilinestring):
    coordinates = []
    for linestring in multilinestring:
        for point in linestring.coords:
            coordinates.append((int(point[0]), int(point[1])))
    return coordinates

def merge_lines(lines, tolerance=10):
    merged_lines = []
    while lines:
        base_line = lines.pop(0)
        merged = False
        for i, line in enumerate(lines):
            if base_line.distance(line) < tolerance:
                merged_line = linemerge([base_line, line])
                lines.pop(i)
                lines.insert(0, merged_line)
                merged = True
                break
        if not merged:
            merged_lines.append(base_line)
    return MultiLineString(merged_lines)


one_pixel = 0.15
def prediction(image,ms):
    try:
        if ms == "summer":
            print("Using Summer Model/////////////////////.")
            model = YOLO('static/models/germany_summer_ai_model/new_one_last.pt')
        elif ms == "winter":
            print("Using Winter Model/////////////////////")
            model = YOLO('static/models/400_m_Germany_Winter_Model/weights/best.pt')
        results = model.predict(image,save=False,save_txt=True,save_crop=False,show_labels=False,show_boxes=False)
        font = cv2.FONT_HERSHEY_SIMPLEX
        font_scale = 1
        font_thickness = 2
        font_color = (225, 225, 225)
        text_list = []
        postion_ls = []
        center_ls = []
        box_ls = []


        for r in results:

            boxes = r.boxes
            polygon_point = r.masks.xy
            # print(ploygon_point)

            im_array = r.plot(line_width=4, conf=1)
            im = Image.fromarray(im_array[..., ::-1])
            image_np = np.array(im)
            class_ids = r.boxes.cls.tolist()

            class_counts = {0: 0, 1: 0, 2: 0, 3: 0,4:0,5:0,6:0,7:0,8:0}

            for count in class_ids:
                class_counts[count] += 1

            for class_id, count in class_counts.items():
                class_name = r.names.get(class_id, f'Class {class_id}')
                text = f'{class_name}: {count}'
                text_list.append(text)
                position = (10, 30 + 30 * class_id)  # Adjust the position as needed

                cv2.putText(image_np, text, position, font, font_scale, font_color, font_thickness)
            class_id_count = 1

            for box,cls_id,polygon_value in zip(boxes,class_ids,polygon_point):
                poly_area = polygon_area(polygon_value)
                poly_area_meter = poly_area * (one_pixel ** 2)

                xmin = int(box.data[0][0])
                ymin = int(box.data[0][1])
                xmax = int(box.data[0][2])
                ymax = int(box.data[0][3])
                box_ls.append([xmin, ymin, xmax, ymax])
                #
                center_x = int((xmin + xmax) // 2)
                center_y = int((ymin + ymax) // 2)
                center_point = (center_x, center_y)


                # width = xmax - xmin
                # height = ymax - ymin
                # area = width * height

                # poly_area_meter = area * (one_pixel ** 2)
                clas_id = int(cls_id)
                class_name = r.names.get(clas_id, f'Class {clas_id}')
                class_name = f"{class_name}"
                # class_name = f"{class_name}_{class_id_count}"
                # postion_ls.append({class_name: f"{round(poly_area_meter, 2)} m²"})
                center_ls.append({class_name: center_point})
                class_id_count += 1

                cv2.circle(image_np, center_point, 5, (255, 0, 0), -1)
                # print('center_point: ',center_point)
                if 'path' in class_name:
                    print(class_name)
                    poly = shapely.Polygon(polygon_value
                    )
                    centerline = pygeoops.centerline(poly)
                    line_strings = []
                    # x, y = polygon_value.exterior.xy
                    # cv2.polylines(image_np, [np.array(list(zip(x, y))).astype(int)], isClosed=True, color=(255, 0, 0),
                    #               thickness=2)

                    if hasattr(centerline, 'geoms'):
                        # Extract the individual LineString components and add them to the list
                        for line in centerline.geoms:
                            line_strings.append(line)
                    else:
                        # If it's not a MultiLineString, assume it's a single LineString
                        line_strings.append(centerline)

                    # print('line_strings:',line_strings)

                    line_list = []


                    for line in line_strings:
                        points = [(int(point[0]), int(point[1])) for point in line.coords]


                        for i in range(len(points) - 1):
                            # print(points)

                            cv2.line(image_np, points[i], points[i + 1], color=(0, 0, 255), thickness=2)
                            print(points[i], points[i + 1])
                            line_list.append((points[i], points[i + 1]))
                    postion_ls.append({class_name: f"{round(poly_area_meter, 2)} m²", "line_value": line_list})
                #


                ############### newo code #######


                else:
                    postion_ls.append({class_name: f"{round(poly_area_meter, 2)} m²","line_value":False})






            modified_im = Image.fromarray(image_np)
            return True,modified_im,boxes,text_list,box_ls,postion_ls,center_ls
    except Exception as e:
        print(str(e))
        return False,'','','','','',''


# img = '/Users/psi-square/Documents/all_dwon/mirkhagan-ml_tree_detection-e3ae0fe15c65/tree_project/static/input_img/2024-06-02_17-20-38/output_1.jpeg'
#
#
# prediction(img)
