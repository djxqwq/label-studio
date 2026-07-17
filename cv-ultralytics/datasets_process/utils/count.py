import cv2
from ultralytics import YOLO
import numpy as np
import os
import shutil
from datasets_process.utils.calculate import get_label_median
import math
import pandas as pd

current_file_path = os.path.abspath(__file__)

def filter_none_cls(label_path):
    with open(label_path, 'r', encoding='utf-8') as file:
        lines = file.readlines()
        for line in lines:
            if line.startswith("None"):
                return True, 0
    return False, len(lines)

base_path = os.path.dirname(os.path.dirname(current_file_path))
image_path = base_path + "/predict/datasets"
answer_csv_path = base_path + "/csv/栈板数量统计.csv"
output_base_path = "/Users/senga/Downloads/tray_detection/count_num/predict_output"
output_images_path = output_base_path + "/images/"
output_csv_path = output_base_path + "/数据统计数据.csv"

# 更换模型
model_path = base_path + "/predict/predict_obb/models/0918_classify.pt"
model = YOLO(model_path)

if os.path.exists(output_base_path):
    shutil.rmtree(output_base_path)
    os.makedirs(output_base_path)
    (pd.DataFrame(columns=["图片名称", "人工打标", "模型预测", "偏差数量（人工打标-模型预测）"])
     .to_csv(output_csv_path,index=False,encoding='utf-8-sig'))
    if not os.path.exists(output_images_path):
        os.makedirs(output_images_path)

df_answer = pd.read_csv(answer_csv_path)
for index, row in df_answer.iterrows():
    img = cv2.imread(image_path + "/" + row["图片名称"])
    if img is None:
        print(row["图片名称"])
        continue
    results = model.predict(source=img, conf=0.3, iou=0.2)

    m_w, m_h = get_label_median(results)

    model_num = results[0].obb.shape[0]
    for r in results:
        boxes = r.obb

        for box in boxes:
            if box.xywhr[0][2] / m_w < 0.7 or box.xywhr[0][3] / m_h < 0.5:
                model_num -= 1
                continue

            # 获取标注信息和概率
            (x1, y1), (x2, y2), (x3, y3), (x4, y4) = box.xyxyxyxy[0]
            # 在图片上标注矩形框
            points = np.array([[int(x1), int(y1)],
                               [int(x2), int(y2)],
                               [int(x3), int(y3)],
                               [int(x4), int(y4)]],
                              dtype=np.int32)
            cv2.polylines(img, [points], True, (240, 176, 0), 2)

    sub = math.fabs(row["总数"] - model_num)
    if sub != 0:
        cv2.imwrite(output_images_path + row["图片名称"], img)

    df_output = pd.DataFrame({
        '图片名称': row["图片名称"],
        '人工打标': row["总数"],
        '模型预测': model_num,
        '偏差数量（人工打标-模型预测）': row["总数"] - model_num
    }, index=[0])
    df_output.to_csv(output_csv_path, index=False, encoding='utf-8-sig', mode="a", header=False)
