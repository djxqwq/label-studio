import os
import json
import numpy as np
import math
import cv2


def get_label_value(l):
    if l == 'suliao':
        return 15
    if l == '12L':
        return 16
    if l == '5L':
        return 17
    if l == 'jihua':
        return 18
    if l == '19L':
        return 19
    if l == '19L-4*5':
        return 20


base_path = "/Users/senga/Downloads/tray_detection/origin_images/20240624"
json_path = base_path + "/jsons"
label_path = base_path + "/labels"
image_path = base_path + "/images"
items = os.listdir(json_path)
for item in items:
    file_name = item
    if file_name == '.DS_Store':
        continue
    print(file_name)
    f = open(json_path + "/" + file_name, encoding='utf-8')
    txt = []
    for line in f:
        txt.append(line.strip())
    label = json.loads(" ".join(txt))

    if len(label["shapes"]) == 0:
        file_path = os.path.join(json_path, file_name)
        if os.path.isfile(file_path):
            os.remove(file_path)
            continue

    img_name = file_name.replace("json", "jpg")
    image = cv2.imread(image_path + f'/{img_name}')
    image_height, image_width, _ = image.shape
    lines = []
    for point in label["shapes"]:
        lb = point["label"]
        points = point["points"]
        x1, y1 = points[0]
        x2, y2 = points[1]
        x3, y3 = points[2]
        x4, y4 = points[3]

        minimum_x = min(x1, x2, x3, x4)
        minimum_y = min(y1, y2, y3, y4)

        maximum_x = max(x1, x2, x3, x4)
        maximum_y = max(y1, y2, y3, y4)

        x_center = (minimum_x + maximum_x) / 2
        y_center = (minimum_y + maximum_y) / 2

        width = maximum_x - minimum_x
        height = maximum_y - minimum_y

        temp = [x_center/image_width, y_center/image_height, width/image_width, height/image_height]
        line_data = [round(item, 6) for item in temp]
        line_data.insert(0, get_label_value(lb))
        lines = lines + [" ".join(map(str, line_data))]

    file_name = file_name.replace("json", "txt")
    save_path = label_path + "/" + file_name
    with open(f"{save_path}", "w") as file:
        for line in lines:
            file.write(line + "\n")



