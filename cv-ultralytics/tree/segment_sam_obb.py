#!/usr/bin/env python3
"""
使用 YOLO OBB 模型检测对象，然后用 SAM 模型进行精细分割。
结合 OBB 检测的准确性和 SAM 分割的精细度。
输出前景保留原色、背景透明的 PNG 图片。
"""

import os
import sys
import cv2
import numpy as np
import torch
import argparse
from pathlib import Path
from typing import List, Tuple, Optional
from ultralytics import YOLO
from segment_anything import SamPredictor, sam_model_registry


def load_sam_predictor(checkpoint_path: str) -> SamPredictor:
    checkpoint_name = Path(checkpoint_path).name
    if "vit_h" in checkpoint_name:
        model_type = "vit_h"
    elif "vit_l" in checkpoint_name:
        model_type = "vit_l"
    else:
        model_type = "vit_b"

    device = "cuda" if torch.cuda.is_available() else "cpu"
    sam = sam_model_registry[model_type](checkpoint=checkpoint_path)
    sam.to(device=device)
    predictor = SamPredictor(sam)
    return predictor


def resize_keep_ratio(image: np.ndarray, max_side: int = 1024) -> np.ndarray:
    h, w = image.shape[:2]
    long_side = max(h, w)
    if long_side <= max_side:
        return image
    scale = max_side / long_side
    new_w, new_h = int(w * scale), int(h * scale)
    return cv2.resize(image, (new_w, new_h), interpolation=cv2.INTER_AREA)


def get_aabb_from_obb(obb_points: np.ndarray) -> Tuple[int, int, int, int]:
    x_coords = obb_points[:, 0]
    y_coords = obb_points[:, 1]
    x1, x2 = int(np.min(x_coords)), int(np.max(x_coords))
    y1, y2 = int(np.min(y_coords)), int(np.max(y_coords))
    return x1, y1, x2, y2


def segment_with_obb_detection(
    yolo_model: YOLO,
    sam_predictor: SamPredictor,
    image_path: str,
    output_dir: str,
    conf: float = 0.5,
    iou: float = 0.5,
    max_side: int = 1024,
) -> int:
    """
    使用 YOLO OBB 检测对象，然后用 SAM 进行精细分割

    Args:
        yolo_model: YOLO OBB 模型
        sam_predictor: SAM 预测器
        image_path: 输入图片路径
        output_dir: 输出目录
        conf: 置信度阈值
        iou: IOU 阈值
        max_side: 图片最大边长限制

    Returns:
        成功分割的对象数量
    """
    img_bgr = cv2.imread(image_path)
    if img_bgr is None:
        print(f"无法读取图片: {image_path}")
        return 0

    img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
    original_h, original_w = img_rgb.shape[:2]

    img_rgb_resized = resize_keep_ratio(img_rgb, max_side=max_side)
    img_bgr_resized = resize_keep_ratio(img_bgr, max_side=max_side)

    sam_predictor.set_image(img_rgb_resized)

    results = yolo_model.predict(source=img_bgr_resized, conf=conf, iou=iou)

    stem = Path(image_path).stem
    success_count = 0

    for r in results:
        boxes = r.obb
        if boxes is None:
            continue

        for idx in range(len(boxes)):
            confidence = float(boxes.conf[idx])

            (x1, y1), (x2, y2), (x3, y3), (x4, y4) = boxes.xyxyxyxy[idx]
            obb_points = np.array([
                [int(x1), int(y1)],
                [int(x2), int(y2)],
                [int(x3), int(y3)],
                [int(x4), int(y4)],
            ], dtype=np.int32)

            x1_aabb, y1_aabb, x2_aabb, y2_aabb = get_aabb_from_obb(obb_points)

            h_resized, w_resized = img_rgb_resized.shape[:2]
            x1_aabb = max(0, min(x1_aabb, w_resized))
            y1_aabb = max(0, min(y1_aabb, h_resized))
            x2_aabb = max(0, min(x2_aabb, w_resized))
            y2_aabb = max(0, min(y2_aabb, h_resized))

            if x2_aabb <= x1_aabb or y2_aabb <= y1_aabb:
                continue

            input_box = np.array([x1_aabb, y1_aabb, x2_aabb, y2_aabb], dtype=np.float32)

            masks, scores, _ = sam_predictor.predict(
                box=input_box,
                multimask_output=True,
            )

            if len(masks) == 0:
                continue

            best_idx = int(np.argmax(scores))
            mask = masks[best_idx]

            img_bgra = cv2.cvtColor(img_bgr_resized, cv2.COLOR_BGR2BGRA)
            mask_np = np.asarray(mask, dtype=np.uint8)
            img_bgra[:, :, 3] = mask_np * 255

            output_name = f"{stem}_obj{idx}_conf{confidence:.2f}.png"
            output_path = os.path.join(output_dir, output_name)

            cv2.imwrite(output_path, img_bgra)
            success_count += 1
            print(f"✓ 分割对象 {idx}: conf={confidence:.2f}, box=[{x1_aabb},{y1_aabb},{x2_aabb},{y2_aabb}]")

    print(f"✓ {Path(image_path).name}: 成功分割 {success_count} 个对象")
    return success_count


def process_folder(
    source_dir: str,
    output_dir: str,
    yolo_model_path: str,
    sam_checkpoint_path: str,
    conf: float = 0.5,
    iou: float = 0.5,
    max_side: int = 1024,
) -> int:
    """处理整个文件夹的图片"""
    source = Path(source_dir)
    if not source.exists():
        raise FileNotFoundError(f"输入路径不存在: {source_dir}")

    if not Path(yolo_model_path).exists():
        raise FileNotFoundError(f"YOLO 模型文件不存在: {yolo_model_path}")

    if not Path(sam_checkpoint_path).exists():
        raise FileNotFoundError(f"SAM 权重文件不存在: {sam_checkpoint_path}")

    os.makedirs(output_dir, exist_ok=True)

    print(f"加载 YOLO OBB 模型: {yolo_model_path}")
    yolo_model = YOLO(yolo_model_path)

    print(f"加载 SAM 模型: {sam_checkpoint_path}")
    sam_predictor = load_sam_predictor(sam_checkpoint_path)

    if source.is_file():
        image_files = [source]
    else:
        image_files = sorted([
            f for f in source.iterdir()
            if f.suffix.lower() in ('.png', '.jpg', '.jpeg', '.bmp', '.tif', '.tiff')
        ])

    if not image_files:
        print(f"未找到图片文件: {source_dir}")
        return 0

    total_objects = 0
    for image_file in image_files:
        count = segment_with_obb_detection(
            yolo_model=yolo_model,
            sam_predictor=sam_predictor,
            image_path=str(image_file),
            output_dir=output_dir,
            conf=conf,
            iou=iou,
            max_side=max_side,
        )
        total_objects += count

    print(f"\n完成！共成功分割 {total_objects} 个对象，保存到: {output_dir}")
    return total_objects


def main():
#     parser = argparse.ArgumentParser(
#         description="使用 YOLO OBB 检测对象，然后用 SAM 进行精细分割",
#         formatter_class=argparse.RawDescriptionHelpFormatter,
#         epilog="""
# 使用示例:
#   # 处理单张图片
#   python segment_sam_obb.py -i input.jpg -o output_dir -y yolo_obb.pt -c sam_vit_l.pth
#
#   # 处理整个文件夹
#   python segment_sam_obb.py -i input_dir -o output_dir -y yolo_obb.pt -c sam_vit_l.pth
#
#   # 调整置信度阈值
#   python segment_sam_obb.py -i input.jpg -o output_dir -y yolo_obb.pt -c sam_vit_l.pth --conf 0.3
#
#   # 指定最大边长
#   python segment_sam_obb.py -i input.jpg -o output_dir -y yolo_obb.pt -c sam_vit_l.pth --max-side 2048
#         """
#     )
#
#     parser.add_argument(
#         "-i", "--input",
#         required=True,
#         help="输入图片路径或图片文件夹路径"
#     )
#
#     parser.add_argument(
#         "-o", "--output",
#         required=True,
#         help="输出文件夹路径"
#     )
#
#     parser.add_argument(
#         "-y", "--yolo-model",
#         required=True,
#         help="YOLO OBB 模型文件路径 (.pt)"
#     )
#
#     parser.add_argument(
#         "-c", "--sam-checkpoint",
#         required=True,
#         help="SAM 模型权重文件路径 (.pth)"
#     )
#
#     parser.add_argument(
#         "--conf",
#         type=float,
#         default=0.5,
#         help="置信度阈值（默认: 0.5）"
#     )
#
#     parser.add_argument(
#         "--iou",
#         type=float,
#         default=0.5,
#         help="IOU 阈值（默认: 0.5）"
#     )
#
#     parser.add_argument(
#         "--max-side",
#         type=int,
#         default=1024,
#         help="图片最大边长限制（默认: 1024）"
#     )
#
#     args = parser.parse_args()

    # if not os.path.exists(args.input):
    #     print(f"错误: 输入路径不存在: {args.input}")
    #     sys.exit(1)
    #
    # if not os.path.exists(args.yolo_model):
    #     print(f"错误: YOLO 模型文件不存在: {args.yolo_model}")
    #     sys.exit(1)
    #
    # if not os.path.exists(args.sam_checkpoint):
    #     print(f"错误: SAM 权重文件不存在: {args.sam_checkpoint}")
    #     sys.exit(1)

    try:
        process_folder(
            source_dir="/Users/senga/Downloads/工作资料/cv-脐橙/3 树冠投影面积/测试结果/单张图片的结果/信丰航拍图-原图.jpg",
            output_dir="/Users/senga/Downloads/tmp",
            yolo_model_path="/Users/senga/Downloads/工作资料/cv-脐橙/3 树冠投影面积/train2/best.pt",
            sam_checkpoint_path="/Users/senga/Downloads/工作资料/cv-脐橙/3 树冠投影面积/orange-tree-area-sam（宇昂的demo）/sam_vit_l_0b3195.pth",
            )
    except Exception as e:
        print(f"错误: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
