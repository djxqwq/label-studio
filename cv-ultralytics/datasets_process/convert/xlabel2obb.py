import os
import json
import numpy as np
import math
import cv2


def get_label_value(l):
    # if l == '店头' or l == 'storesign':
    #     return 0
    if l == "suliao":
        return 15
    elif l == "12L":
        return 16
    elif l == "5L":
        return 17
    elif l == "jihua":
        return 18
    elif l == "19L":
        return 19
    elif l == "19L-4*5":
        return 20
    elif l == "6L":
        return 21


def normalize_point(point, img_width, img_height):
    tmp_w = point[0] / img_width
    tmp_h = point[1] / img_height
    return tmp_w if tmp_w < 1 else 1, tmp_h if tmp_h < 1 else 1


def rotate_to_yolov8_obb(data, img_width, img_height):
    shapes = data['shapes']
    obb_format_data = []

    for shape in shapes:
        label = shape['label']
        points = shape['points']

        # Ensure the points are in a consistent order (clockwise or counter-clockwise)
        if len(points) != 4:
            print("Error: The shape does not have 4 points")
            continue

        # Normalize points
        normalized_points = [normalize_point(p, img_width, img_height) for p in points]

        class_index = get_label_value(label)
        obb_format_data.append(f"{class_index} " + " ".join(f"{x:.6f} {y:.6f}" for x, y in normalized_points))
    return obb_format_data


def convert(base_path):

    img_path = base_path + "/images"
    path = base_path + "/jsons"
    new_path = base_path + "/labels"
    items = os.listdir(path)
    for item in items:
        file_name = item
        img_name = file_name.replace(".json", ".jpg")
        if file_name == '.DS_Store':
            continue
        print(file_name)
        f = open(path + "/" + file_name, encoding='utf-8')
        txt = []
        for line in f:
            txt.append(line.strip())
        data = json.loads(" ".join(txt))

        if len(data["shapes"]) == 0:
            file_path = os.path.join(path, file_name)
            if os.path.isfile(file_path):
                os.remove(file_path)
                continue

        # 加载图像
        image = cv2.imread(img_path + f'/{img_name}')
        if image is None or image.shape is None:
            continue
        image_height, image_width, _ = image.shape

        obb_data = rotate_to_yolov8_obb(data, image_width, image_height)

        file_name = file_name.replace("json", "txt")
        save_path = new_path + "/" + file_name

        with open(f"{save_path}", "w") as file:
            for line in obb_data:
                file.write(line + '\n')

# base_path = "/Users/senga/Downloads/tray_detection/images_labels/obb/1012/"
# convert(base_path)

