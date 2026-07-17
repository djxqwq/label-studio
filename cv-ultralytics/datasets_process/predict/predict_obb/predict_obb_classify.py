import os
import cv2
import sys
import numpy as np
from ultralytics import YOLO
from datasets_process.common import jasmine_dict,single_class_color_dict
project_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(project_path)


conf = 0.5
iou = 0.5

font = cv2.FONT_HERSHEY_SIMPLEX  # 字体样式
font_scale = 0.5  # 字体大小
thickness = 1  # 字体粗细
def predict_obb(source_dir, output_folder, model_path):
    """
    预测&打标
    Args:
        source_dir:
        output_folder:
        model_path:
    """

    if not os.path.exists(source_dir):
        raise Exception("预测图片不存在")
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)

    model = YOLO(model_path)

    i = 0
    for image_file in os.listdir(source_dir):
        if image_file.lower().endswith(('.png', '.jpg', '.jpeg')):

            image_path = os.path.join(source_dir, image_file)
            img = cv2.imread(image_path)

            results = model.predict(source=img, conf=conf, agnostic_nms=True, iou=iou, max_det=2000)

            # 获取预测结果
            for r in results:
                boxes = r.obb
                for box in boxes:
                    class_id = int(box.cls[0])
                    confidence = float(box.conf[0])

                    (x1, y1), (x2, y2), (x3, y3), (x4, y4) = box.xyxyxyxy[0]
                    points = np.array([[int(x1), int(y1)],
                                       [int(x2), int(y2)],
                                       [int(x3), int(y3)],
                                       [int(x4), int(y4)]],
                                      dtype=np.int32)
                    cv2.polylines(img, [points], True, single_class_color_dict.get(class_id), 2)

                    text = f"{class_id}: {confidence:.2f}"
                    text_size = cv2.getTextSize(text, font, font_scale, thickness)[0]
                    text_x = min(points[:, 0])
                    text_y = min(points[:, 1]) - 10
                    if text_y < text_size[1]:
                        text_y = max(points[:, 1]) + text_size[1] + 10
                    cv2.putText(img, text, (text_x, text_y), font, font_scale,
                                single_class_color_dict.get(class_id, (255, 255, 255)), thickness, lineType=cv2.LINE_AA)


            # 保存标注后的图片
            output_path = os.path.join(output_folder, image_file)
            cv2.imwrite(output_path, img)
            i += 1
    print("{}张图片预测打标已完成。".format(i))


source_dir = "/Users/senga/Desktop/脐橙产量预估/脐橙树冠投影面积/验证集/images"
output_folder = "/Users/senga/Desktop/脐橙产量预估/脐橙树冠投影面积/output"
model_path = "/Users/senga/Desktop/脐橙产量预估/脐橙树冠投影面积/模型/0618/best.pt"
predict_obb(source_dir, output_folder, model_path)
