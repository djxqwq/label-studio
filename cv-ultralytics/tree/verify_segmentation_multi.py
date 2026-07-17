#!/usr/bin/env python3
"""
验证分割结果 - 支持多对象叠加
将多个分割结果 (original_obj0.png, original_obj1.png...) 叠加到原图上
使用不同颜色区分不同对象
"""

import os
import cv2
import numpy as np
import argparse
from pathlib import Path
from typing import List, Tuple


def generate_distinct_colors(n: int) -> List[Tuple[int, int, int]]:
    colors = []
    for i in range(n):
        hue = int(360 * i / n)
        hsv = np.array([[[hue, 180, 255]]], dtype=np.uint8)
        bgr = cv2.cvtColor(hsv, cv2.COLOR_HSV2BGR)[0][0]
        colors.append(tuple(int(c) for c in bgr))
    return colors


def overlay_single_mask(
    original_image: np.ndarray,
    mask_image: np.ndarray,
    color: Tuple[int, int, int],
    alpha: float = 0.5,
) -> Tuple[np.ndarray, np.ndarray]:
    if original_image.shape[:2] != mask_image.shape[:2]:
        mask_image = cv2.resize(mask_image, (original_image.shape[1], original_image.shape[0]))

    if mask_image.shape[2] == 4:
        mask = mask_image[:, :, 3]
        mask_binary = (mask > 128).astype(np.uint8)
    else:
        mask_binary = np.ones((original_image.shape[0], original_image.shape[1]), dtype=np.uint8)

    overlay = original_image.copy()
    overlay[mask_binary == 1] = color

    result = cv2.addWeighted(original_image, 1 - alpha, overlay, alpha, 0)
    return result, mask_binary


def draw_label_on_mask(
    image: np.ndarray,
    mask_binary: np.ndarray,
    label: str,
    color: Tuple[int, int, int],
) -> np.ndarray:
    coords = cv2.findNonZero(mask_binary)
    if coords is not None:
        x, y, w, h = cv2.boundingRect(coords)
        center_x, center_y = x + w // 2, y + h // 2

        font = cv2.FONT_HERSHEY_SIMPLEX
        font_scale = 0.8
        thickness = 2
        (text_w, text_h), _ = cv2.getTextSize(label, font, font_scale, thickness)

        cv2.rectangle(
            image,
            (center_x - text_w // 2 - 4, center_y - text_h - 4),
            (center_x + text_w // 2 + 4, center_y + 4),
            (255, 255, 255),
            cv2.FILLED,
        )

        cv2.putText(
            image,
            label,
            (center_x - text_w // 2, center_y),
            font,
            font_scale,
            color,
            thickness,
            cv2.LINE_AA,
        )

    return image


def extract_obj_number(filename: str) -> int:
    import re
    match = re.search(r'_obj(\d+)', filename)
    return int(match.group(1)) if match else 0


def verify_multiple_objects(
    original_path: str,
    segmentation_dir: str,
    output_path: str,
    alpha: float = 0.5,
    show_labels: bool = True,
) -> bool:
    original = cv2.imread(original_path)
    if original is None:
        print(f"无法读取原图：{original_path}")
        return False

    original_stem = Path(original_path).stem

    seg_dir = Path(segmentation_dir)
    candidates = sorted(
        seg_dir.glob(f"{original_stem}_obj*.png"),
        key=lambda x: extract_obj_number(x.name)
    )

    if not candidates:
        candidates = sorted(
            seg_dir.glob("obj*.png"),
            key=lambda x: extract_obj_number(x.name)
        )

    if not candidates:
        print(f"⚠ 未找到分割对象文件：{segmentation_dir}")
        return False

    print(f"找到 {len(candidates)} 个分割对象")

    colors = generate_distinct_colors(len(candidates))

    result = original.copy()

    for idx, seg_file in enumerate(candidates):
        mask_img = cv2.imread(str(seg_file), cv2.IMREAD_UNCHANGED)
        if mask_img is None:
            print(f"  ⚠ 无法读取：{seg_file.name}")
            continue

        result, mask_binary = overlay_single_mask(
            result, mask_img, colors[idx], alpha=alpha
        )

        if show_labels:
            result = draw_label_on_mask(
                result, mask_binary, str(idx), colors[idx]
            )

        print(f"  ✓ {seg_file.name} (对象 {idx})")

    cv2.imwrite(output_path, result)
    print(f"✓ 验证完成：{output_path}")
    return True


def main():
    parser = argparse.ArgumentParser(
        description="验证分割结果 - 多对象叠加",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用示例:
  # 验证单张原图的多个分割对象
  python verify_segmentation_multi.py -i original.jpg -s seg_dir -o verify.png

  # 调整透明度
  python verify_segmentation_multi.py -i original.jpg -s seg_dir -o verify.png --alpha 0.3

  # 不显示编号标签
  python verify_segmentation_multi.py -i original.jpg -s seg_dir -o verify.png --no-labels

  # 验证整个文件夹
  python verify_segmentation_multi.py -i img_dir -s seg_dir -o output_dir
        """
    )

    parser.add_argument("-i", "--input", required=True, help="原图路径或文件夹")
    parser.add_argument("-s", "--segmentation", required=True, help="分割结果文件夹")
    parser.add_argument("-o", "--output", required=True, help="输出路径或文件夹")
    parser.add_argument("--alpha", type=float, default=0.5, help="透明度 (0-1)")
    parser.add_argument("--no-labels", action="store_true", help="不显示对象编号")

    args = parser.parse_args()

    if not os.path.exists(args.input):
        print(f"错误: 输入路径不存在: {args.input}")
        return

    if not os.path.exists(args.segmentation):
        print(f"错误: 分割图片路径不存在: {args.segmentation}")
        return

    if args.alpha < 0 or args.alpha > 1:
        print(f"错误: 透明度必须在 0-1 之间，得到: {args.alpha}")
        return

    if os.path.isfile(args.input):
        verify_multiple_objects(
            args.input,
            args.segmentation,
            args.output,
            alpha=args.alpha,
            show_labels=not args.no_labels,
        )
    else:
        os.makedirs(args.output, exist_ok=True)
        for img_file in Path(args.input).glob("*.jpg"):
            output_file = Path(args.output) / f"{img_file.stem}_verify.png"
            verify_multiple_objects(
                str(img_file),
                args.segmentation,
                str(output_file),
                alpha=args.alpha,
                show_labels=not args.no_labels,
            )

    print("\n验证完成！")


if __name__ == "__main__":
    main()
#
# python verify_segmentation_multi.py \                                                                                                                                              ──(Wed,Apr22)─┘
#   -i "/Users/senga/Downloads/工作资料/cv-脐橙/3 树冠投影面积/测试结果/单张图片的结果/信丰航拍图-原图.jpg" \
#   -s "/Users/senga/Downloads/工作资料/cv-脐橙/3 树冠投影面积/seg_result" \
#   -o "/Users/senga/Downloads/工作资料/cv-脐橙/3 树冠投影面积/verify/verify_result.png"
