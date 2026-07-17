import os
import sys

project_path = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(project_path)

from ultralytics import YOLO
from datetime import datetime

path = "/cv-ultralytics/ultralytics/ultralytics"
project_path += path


def do_train(model_pt):
    """
    训练模型
    :param model_yaml: 模型配置文件
    :param model_pt: 预训练模型
    :param data_yaml: 数据集配置文件
    :return:
    """
    # 加载模型
    model = YOLO(project_path + f"/models/{model_pt}.pt")
    # 训练模型
    train_results = model.train(
        data="/home/admin/cv-ultralytics/datasets/scab",
        # 训练的总轮数
        epochs=1000,
        # 每个训练批次中包含的图像数量
        batch=16,
        # 早停条件
        patience=200,
        device=0,
        pretrained=True,
        plots=True
    )

    # 评估模型
    val_results = model.val()

    # 创建一个以版本号为名称的文件夹
    version = datetime.now().strftime('%Y%m%d%H%M%S')
    save_path = f"trained_models/model_v{version}"
    os.makedirs(save_path, exist_ok=True)

    # 保存模型
    model.save(f"{save_path}/model.pt")

if __name__ == '__main__':
    do_train("yolov8x-cls")