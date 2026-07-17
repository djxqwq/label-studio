import cv2
import numpy as np

img_name = 'non_left (2)'
label_path = "/Users/localadmin/Documents/脐橙挂果数量检测/柑橘目标检测数据集/train/labels"
img_path = "/Users/localadmin/Documents/脐橙挂果数量检测/柑橘目标检测数据集/train/images"
image = cv2.imread(img_path+f'/{img_name}.png')
image_height, image_width, _ = image.shape

with open(label_path+f'/{img_name}.txt', 'r') as file:
    lines = file.readlines()

detect_data = [line.strip().split() for line in lines]
detect_data = [(int(class_index), float(center_x), float(center_y), float(w), float(h)) for class_index, center_x, center_y, w, h in detect_data]

for class_index, center_x, center_y, w, h in detect_data:
    x_min = int((center_x - w / 2) * image_width)
    y_min = int((center_y - h / 2) * image_height)
    x_max = int((center_x + w / 2) * image_width)
    y_max = int((center_y + h / 2) * image_height)
    cv2.rectangle(image, (x_min, y_min), (x_max, y_max), (0, 255, 0), 2)

cv2.imshow('Image with Detects', image)
cv2.waitKey(0)
cv2.destroyAllWindows()