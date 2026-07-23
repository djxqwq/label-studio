# cv-ultralytics（Label Studio 训练引擎子集）

本目录仅保留平台训练所需部分：

- `ultralytics/` — Ultralytics YOLO 框架源码（`tasks.py` 通过 `sys.path` 加载）
- `datasets_process/utils/group_img.py` — 数据集 train/valid/test 划分

运行时还会生成（勿提交）：`datasets/`、`runs/`、`trained_models/`，以及权重目录 `ultralytics/ultralytics/models/*.pt`。
