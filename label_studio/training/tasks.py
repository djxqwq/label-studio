"""Django 训练后台任务 —— 直接调 cv-ultralytics 现有脚本"""
import os
import sys
import subprocess
import threading


# cv-ultralytics 路径：label-studio/cv-ultralytics/
_BASE = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
_CV_ULTRA = os.path.join(_BASE, 'cv-ultralytics')
if _CV_ULTRA not in sys.path:
    sys.path.insert(0, _CV_ULTRA)


def build_dataset(export_dir: str, dataset_name: str, task_type: str = 'obb'):
    """
    调 group_img.py 把导出数据按 train/valid/test 划分到 datasets/{name}/{type}/
    """
    dst = os.path.join(_CV_ULTRA, 'datasets', dataset_name, task_type)
    os.makedirs(dst, exist_ok=True)

    # 把导出数据（images/ + labels/）复制到目标，再跑 group_img.py
    import shutil
    for phase in ['train', 'valid', 'test']:
        for sub in ['images', 'labels']:
            os.makedirs(os.path.join(dst, phase, sub), exist_ok=True)

    src_img = os.path.join(export_dir, 'images')
    src_lbl = os.path.join(export_dir, 'labels')
    if not os.path.exists(src_img) or not os.path.exists(src_lbl):
        raise FileNotFoundError(f'导出数据不完整: images={os.path.exists(src_img)}, labels={os.path.exists(src_lbl)}')

    # 直接调 group_img.py 的逻辑（它在 datasets_process/utils/ 下，硬编码了 src_dir/dst_dir）
    # 这里用子进程方式跑
    group_img = os.path.join(_CV_ULTRA, 'datasets_process', 'utils', 'group_img.py')
    result = subprocess.run(
        [sys.executable, group_img],
        cwd=_CV_ULTRA,
        capture_output=True, text=True,
        env={**os.environ, 'EXPORT_DIR': export_dir, 'DATASET_NAME': dataset_name, 'TASK_TYPE': task_type},
    )
    print(result.stdout)
    if result.returncode != 0:
        print(result.stderr)
    return result.returncode == 0


# ---- 模型配置表（前端下拉选项，新增模型只改这里） ----
MODEL_CONFIGS = {
    "tree-obb":          ("yolov8x-obb", "yolov8x-obb", "tree-obb"),
    "jasmine-blooming-obb": ("yolov8x-obb", "yolov8x-obb", "jasmine-blooming-obb"),
    "jasmine-seed-obb":  ("yolov8x-obb", "yolov8x-obb", "jasmine-seed-obb"),
    "jasmine-wither-obb":("yolov8x-obb", "yolov8x-obb", "jasmine-wither-obb"),
    "jasmine-obb":       ("yolov8x-obb", "yolov8x-obb", "jasmine-obb"),
    "orange-obb":        ("yolov8x-obb", "yolov8x-obb", "orange-obb"),
    "orange-detect":     ("yolov8x",     "yolov8x-oiv7",   "orange-detect"),
    "tray-obb":          ("yolov8x-obb", "yolov8x-obb",    "tray-obb"),
    "tray-detect":       ("yolov8x",     "yolov8x-oiv7",   "tray-detect"),
    "tray-obb-single":   ("yolov8x-obb", "yolov8x-obb",    "tray-obb"),
    "scab-obb":          ("yolov8x-obb", "yolov8x-obb",    "scab-obb"),
    "scab-detect":       ("yolov8x",     "yolov8x-oiv7",   "scab-detect"),
    "zebrafish-obb":     ("yolov8x-obb", "yolov8x-obb",    "zebrafish-obb"),
    "uniform-obb":       ("yolov8x-obb", "yolov8x-obb",    "uniform-obb"),
    "flavor-injection-obb": ("yolov8x-obb", "yolov8x-obb", "flavor-injection-obb"),
    "diantou-obb":       ("yolov8x-obb", "yolov8x-obb",    "diantou"),
}
# 格式: name -> (model_yaml, model_pt, data_yaml)


def run_training(model_yaml: str, model_pt: str, data_yaml: str, **params):
    """直接调 YOLO model.train()，不修改 train_task.py"""
    from ultralytics import YOLO
    from datetime import datetime

    proj_root = os.path.join(_CV_ULTRA, 'ultralytics', 'ultralytics')
    model = YOLO(os.path.join(proj_root, 'cfg', 'models', 'v8', f'{model_yaml}.yaml')).load(
        os.path.join(proj_root, 'models', f'{model_pt}.pt'))

    model.train(
        data=os.path.join(proj_root, 'cfg', 'datasets', f'{data_yaml}.yaml'),
        epochs=params.get('epochs', 1000),
        batch=params.get('batch', 16),
        patience=params.get('patience', 200),
        imgsz=params.get('imgsz', 640),
        device=params.get('device', 0),
        pretrained=True,
        plots=True,
    )

    model.val()
    version = datetime.now().strftime('%Y%m%d%H%M%S')
    save_path = os.path.join(_CV_ULTRA, 'trained_models', f'model_v{version}')
    os.makedirs(save_path, exist_ok=True)
    model.save(os.path.join(save_path, 'model.pt'))
    print(f'训练完成，模型已保存至: {save_path}')
    return save_path


def run_training_async(project_id: int, config_name: str, export_dir: str, **params):
    """异步训练（threading）"""
    yaml, pt, data = MODEL_CONFIGS[config_name]

    def _run():
        try:
            # 步骤1：划分数据集
            build_dataset(export_dir, data, 'obb' if 'obb' in yaml else 'detect')
            # 步骤2：训练
            run_training(yaml, pt, data)
        except Exception as e:
            print(f"训练失败: {e}")

    t = threading.Thread(target=_run, daemon=True)
    t.start()
    return t
