from ultralytics import YOLO
from PIL import Image
from io import BytesIO
import cv2
import numpy as np
from shapely.geometry import Polygon


model = YOLO('static/models/best_object_detection.pt')

def polygon_area(vertices):
    polygon = Polygon(vertices)
    area = polygon.area
    return area

one_pixel = 0.15
def prediction(image):
    try:
        results = model.predict(image, save=True,save_txt=True,save_crop=True,show_labels=True,show_boxes=False, verbose=False)
        font = cv2.FONT_HERSHEY_SIMPLEX
        font_scale = 1
        font_thickness = 2
        font_color = (225, 225, 225)
        list = []
        postion_ls = []
        center_ls = []
        box_ls = []


        for r in results:

            boxes = r.boxes
            ploygon_point = r.masks.xy

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
                list.append(text)
                position = (10, 30 + 30 * class_id)  # Adjust the position as needed

                cv2.putText(image_np, text, position, font, font_scale, font_color, font_thickness)
            class_id_count = 1
            for box,cls_id,poly_points in zip(boxes,class_ids,ploygon_point):
                poly_area = polygon_area(poly_points)
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
                #
                # poly_area_meter = area * (one_pixel ** 2)
                clas_id = int(cls_id)
                class_name = r.names.get(clas_id, f'Class {clas_id}')
                class_name = f"{class_name}_{class_id_count}"
                postion_ls.append({class_name: f"{round(poly_area_meter, 2)} m²"})
                center_ls.append({class_name: center_point})
                class_id_count += 1

                cv2.circle(image_np, center_point, 5, (255, 0, 0), -1)

            modified_im = Image.fromarray(image_np)
            return True,modified_im,boxes,list,box_ls,postion_ls,center_ls
    except:
        return False,'','','','','',''





