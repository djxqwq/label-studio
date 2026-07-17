import os
import sys

project_path = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(project_path)

from train import train_single_task

train_single_task.do_train("yolov8x-obb", "yolov8x-obb", "tray-obb")
