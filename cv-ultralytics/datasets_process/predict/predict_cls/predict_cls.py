import os
import cv2
import sys
from ultralytics import YOLO
from datasets_process.common import class_color_dict
project_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(project_path)

model_path = "/Users/wongsenga/Downloads/地图/train2/weights/best.pt"
source_dir = "/Users/wongsenga/Downloads/地图/验证集/不符合"
target_dir = "/Users/wongsenga/Downloads/地图/验证集"


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
        results = model.predict(source=img)
        top1 = results[0].probs.top1
        top1conf = results[0].probs.top1conf
        class_name = model.names[top1]

        print(f"图片: {image_file} → 分类结果: {class_name} (置信度: {top1conf:.2f})")

        output_path = os.path.join(target_dir, class_name, image_file)
        cv2.imwrite(output_path, img)

        i += 1



