import os
import cv2
import sys
from ultralytics import YOLO
from openpyxl import Workbook
from ultralytics.engine.results import OBB

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

    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Prediction Results"
    # titles = ["图片名称", "花籽", "花蕾", "虎爪", "白花", "萎蔫", "虫蚀","树叶"]
    titles = ["图片名称", "数量"]
    sheet.append(titles)

    i = 0
    for image_file in os.listdir(source_dir):
        if image_file.lower().endswith(('.png', '.jpg', '.jpeg')):

            image_path = os.path.join(source_dir, image_file)
            img = cv2.imread(image_path)

            results = model.predict(source=img, conf=conf, agnostic_nms=True, iou=iou, max_det=2000)

            # 获取预测结果
            for r in results:
                boxes = r.obb

                # bloomed, blooming, chewed, initiation, leaf, seed_count, wither = jasmine(boxes)
                # sheet.append([image_file, seed_count, initiation, blooming, bloomed, wither, chewed, leaf])
                count = 0
                for box in boxes:
                    class_id = int(box.cls[0])
                    if class_id == 0:
                        count += 1
                sheet.append([image_file, count])
            i += 1
    print("{}张图片预测打标已完成。".format(i))
    workbook_path = os.path.join(output_folder, "prediction_results.xlsx")
    workbook.save(workbook_path)


def jasmine(boxes: OBB | None) -> tuple[int, int, int, int, int, int, int]:
    seed_count = 0
    initiation = 0
    blooming = 0
    bloomed = 0
    wither = 0
    chewed = 0
    leaf = 0

    for box in boxes:
        class_id = int(box.cls[0])

        if class_id == 5:
            seed_count += 1
        elif class_id == 3:
            initiation += 1
        elif class_id == 1:
            blooming += 1
        elif class_id == 0:
            bloomed += 1
        elif class_id == 6:
            wither += 1
        elif class_id == 2:
            chewed += 1
        elif class_id == 4:
            leaf += 1
    return bloomed, blooming, chewed, initiation, leaf, seed_count, wither


source_dir = "/Users/senga/Desktop/脐橙产量预估/脐橙树冠投影面积/验证集/images"
output_folder = "/Users/senga/Desktop/脐橙产量预估/脐橙树冠投影面积/"
model_path = "/Users/senga/Desktop/脐橙产量预估/脐橙树冠投影面积/模型/0618/best.pt"
predict_obb(source_dir, output_folder, model_path)
