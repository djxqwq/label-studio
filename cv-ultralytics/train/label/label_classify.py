import os
import sys

project_path = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(project_path)

from ultralytics import YOLO
from datetime import datetime

path = "/ultralytics/ultralytics"
project_path += path


def do_train():

    # 加载模型
    model = YOLO(project_path + f"/models/yolov8x-cls.pt")
    # 训练模型
    train_results = model.train(
        data="/home/admin/class_task_yolo",
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
    do_train()