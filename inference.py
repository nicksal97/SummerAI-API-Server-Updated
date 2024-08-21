
from PIL import Image
from io import BytesIO
import cv2
import numpy as np
from shapely.geometry import Polygon, MultiLineString
import pygeoops
from shapely.ops import linemerge


def polygon_area(vertices):
    """Calculate the area of a polygon given its vertices."""
    polygon_ = Polygon(vertices)  # Create a polygon object from the given vertices
    area = polygon_.area  # Calculate the area of the polygon
    return area


def multiline_to_coordinates(multilinestring):
    """Convert a MultiLineString to a list of coordinates."""
    coordinates = []
    for linestring in multilinestring:
        for point in linestring.coords:
            coordinates.append((int(point[0]), int(point[1])))  # Convert the coordinates to integers and append
    return coordinates


def merge_lines(lines, tolerance=10):
    """Merge lines within a specified tolerance."""
    merged_lines = []
    while lines:
        base_line = lines.pop(0)  # Take the first line as the base
        merged = False
        for i, line in enumerate(lines):
            if base_line.distance(line) < tolerance:  # Check if the lines are close enough to merge
                merged_line = linemerge([base_line, line])  # Merge the lines
                lines.pop(i)
                lines.insert(0, merged_line)  # Insert the merged line at the beginning
                merged = True
                break
        if not merged:
            merged_lines.append(base_line)  # Add the base line to merged_lines if no merge occurred
    return MultiLineString(merged_lines)  # Return the merged lines as a MultiLineString


def prediction(image, model):
    """Predict and annotate image using a YOLO model based on the season."""
    one_pixel = 0.15  # Conversion factor from pixels to meters (or other units)
    try:
        # Load the appropriate YOLO model based on the season


        # Perform prediction using the YOLO model
        results = model.predict(image, save=False, save_txt=True, save_crop=False, show_labels=False, show_boxes=False)
        font = cv2.FONT_HERSHEY_SIMPLEX
        font_scale = 1
        font_thickness = 2
        font_color = (225, 225, 225)

        # Initialize lists to store various information
        text_list = []
        postion_ls = []
        center_ls = []
        box_ls = []

        for r in results:
            boxes = r.boxes  # Bounding boxes for detected objects
            im_array = r.plot(line_width=4, conf=1)  # Generate an image with annotated results
            im = Image.fromarray(im_array[..., ::-1])  # Convert image to PIL format
            image_np = np.array(im)  # Convert image to NumPy array
            class_ids = r.boxes.cls.tolist()  # Get the list of class IDs for detected objects

            # Initialize a dictionary to count occurrences of each class
            try:
                polygon_point = r.masks.xy
                class_counts = {0: 0, 1: 0, 2: 0, 3: 0, 4: 0, 5: 0, 6: 0, 7: 0, 8: 0}

                # Count the occurrences of each class ID
                for count in class_ids:
                    class_counts[count] += 1

                # Annotate the image with class names and counts
                for class_id, count in class_counts.items():
                    class_name = r.names.get(class_id, f'Class {class_id}')
                    text = f'{class_name}: {count}'
                    text_list.append(text)
                    position = (10, 30 + 30 * class_id)  # Adjust the position for each class
                    cv2.putText(image_np, text, position, font, font_scale, font_color, font_thickness)

                class_id_count = 1

                # Process each detected object
                for box, cls_id, polygon_value in zip(boxes, class_ids, polygon_point):
                    poly_area = polygon_area(polygon_value)  # Calculate the area of the polygon
                    poly_area_meter = poly_area * (one_pixel ** 2)  # Convert area to square meters

                    # Extract bounding box coordinates
                    xmin = int(box.data[0][0])
                    ymin = int(box.data[0][1])
                    xmax = int(box.data[0][2])
                    ymax = int(box.data[0][3])
                    box_ls.append([xmin, ymin, xmax, ymax])  # Add bounding box to list

                    # Calculate the center point of the bounding box
                    center_x = int((xmin + xmax) // 2)
                    center_y = int((ymin + ymax) // 2)
                    center_point = (center_x, center_y)

                    # Get the class name and append the center point to the list
                    clas_id = int(cls_id)
                    class_name = r.names.get(clas_id, f'Class {clas_id}')
                    center_ls.append({class_name: center_point})
                    class_id_count += 1

                    # Draw a circle at the center point
                    cv2.circle(image_np, center_point, 5, (255, 0, 0), -1)

                    # If the detected object is a "path", calculate the centerline
                    if 'path' in class_name:
                        print(class_name)
                        poly = Polygon(polygon_value)  # Create a polygon object from the vertices
                        centerline = pygeoops.centerline(poly)  # Calculate the centerline of the polygon
                        line_strings = []

                        # Extract line strings from the centerline geometry
                        if hasattr(centerline, 'geoms'):
                            for line in centerline.geoms:
                                line_strings.append(line)
                        else:
                            line_strings.append(centerline)

                        line_list = []

                        # Draw the centerline on the image
                        for line in line_strings:
                            points = [(int(point[0]), int(point[1])) for point in line.coords]

                            for i in range(len(points) - 1):
                                cv2.line(image_np, points[i], points[i + 1], color=(0, 0, 255), thickness=2)
                                print(points[i], points[i + 1])
                                line_list.append((points[i], points[i + 1]))

                        postion_ls.append({class_name: f"{round(poly_area_meter, 2)} m²", "line_value": line_list})
                    else:
                        postion_ls.append({class_name: f"{round(poly_area_meter, 2)} m²", "line_value": False})

                # Convert the modified image back to PIL format and return the results
            except:
                pass
            modified_im = Image.fromarray(image_np)
            return True, modified_im, boxes, text_list, box_ls, postion_ls, center_ls

    except Exception as e:
        # Handle any exceptions that occur during processing
        print(str(e))
        return False, '', '', '', '', '', ''