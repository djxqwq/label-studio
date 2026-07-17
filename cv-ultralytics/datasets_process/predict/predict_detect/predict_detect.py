import os
import cv2
import sys
from ultralytics import YOLO
from datasets_process.common import class_color_dict
project_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(project_path)

base_path = "/Users/localadmin/Documents/脐橙挂果数量检测"
model_path = base_path + "/模型/0427.pt"
source_dir = base_path + "/单株挂果远景图片"
target_dir = base_path + "/测试输出"


# 加载模型
model = YOLO(model_path)

# 待检测目录
if not os.path.exists(source_dir):
    os.makedirs(source_dir)
# 输出目录
if not os.path.exists(target_dir):
    os.makedirs(target_dir)


# 遍历文件夹中的所有图片
i = 0
for image_file in os.listdir(source_dir):
    if image_file.lower().endswith(('.png', '.jpg', '.jpeg')):
        image_path = os.path.join(source_dir, image_file)
        img = cv2.imread(image_path)
        results = model.predict(source=img, iou=0.2, conf=0.1)

        for r in results:
            boxes = r.boxes
            for box in boxes:
                x1, y1, x2, y2 = box.xyxy[0]
                class_id = int(box.cls[0])
                class_name = model.names[class_id]
                color = (0, 0, 255)
                cv2.rectangle(img, (int(x1), int(y1)), (int(x2), int(y2)), color, 2)

        output_path = os.path.join(target_dir, image_file)
        cv2.imwrite(output_path, img)
        i += 1


