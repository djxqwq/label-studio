import os

import cv2
import numpy as np
from ultralytics import YOLO


def calculate_box_area(x1, y1, x2, y2):
    """
    计算预测框的面积（像素数量）

    Args:
        x1, y1: 预测框左上角坐标
        x2, y2: 预测框右下角坐标

    Returns:
        area: 预测框的面积（像素数量）
    """
    width = abs(x2 - x1)
    height = abs(y2 - y1)
    area = width * height
    return int(area)


def calculate_actual_box_area(det_results, image_shape):
    """
    计算所有预测框的实际覆盖面积（去重后，重叠部分只计算一次）
    支持普通检测框（boxes）和OBB旋转框（obb）
    
    Args:
        det_results: YOLO检测预测结果（detect或obb模型）
        image_shape: 图像尺寸 (height, width)
    
    Returns:
        actual_area: 实际覆盖面积（像素数量，重叠部分只计算一次）
    """
    # 创建与图像相同尺寸的二值图像
    mask_image = np.zeros((image_shape[0], image_shape[1]), dtype=np.uint8)
    
    # 将所有预测框绘制到二值图像上（填充模式）
    for r in det_results:
        # 检查是否是OBB结果
        if r.obb is not None and len(r.obb) > 0:
            # OBB格式：使用四边形填充
            # xyxyxyxy 返回形状为 (N, 4, 2) 的数组，每个框有4个角点
            obb_coords = r.obb.xyxyxyxy.cpu().numpy()
            for obb in obb_coords:
                # obb 是 (4, 2) 的数组，表示四个角点 [(x1,y1), (x2,y2), (x3,y3), (x4,y4)]
                pts = obb.astype(np.int32)
                # 确保坐标在图像范围内
                pts[:, 0] = np.clip(pts[:, 0], 0, image_shape[1] - 1)
                pts[:, 1] = np.clip(pts[:, 1], 0, image_shape[0] - 1)
                # 使用fillPoly填充四边形区域
                cv2.fillPoly(mask_image, [pts], 255)
        elif r.boxes is not None and len(r.boxes) > 0:
            # 普通检测框格式
            boxes = r.boxes
            for box in boxes:
                # 提取坐标
                xyxy = box.xyxy.cpu().numpy()[0]
                x1, y1, x2, y2 = xyxy.astype(int)
                
                # 确保坐标在图像范围内
                x1 = max(0, min(x1, image_shape[1] - 1))
                y1 = max(0, min(y1, image_shape[0] - 1))
                x2 = max(0, min(x2, image_shape[1]))
                y2 = max(0, min(y2, image_shape[0]))
                
                # 填充预测框区域（重叠部分会自动合并）
                if x2 > x1 and y2 > y1:
                    mask_image[y1:y2, x1:x2] = 255
    
    # 统计非零像素数量，这就是实际覆盖面积（重叠部分只计算一次）
    actual_area = np.sum(mask_image > 0)
    return int(actual_area)


def calculate_obb_area(pts):
    """
    使用鞋带公式计算四边形面积
    
    Args:
        pts: 四个角点坐标，形状为 (4, 2)
    
    Returns:
        area: 四边形面积（像素数量）
    """
    n = len(pts)
    area = 0.0
    for i in range(n):
        j = (i + 1) % n
        area += pts[i][0] * pts[j][1]
        area -= pts[j][0] * pts[i][1]
    return abs(area) / 2.0


def calculate_all_box_areas(det_results, verbose=True):
    """
    计算所有预测框面积
    支持普通检测框（boxes）和OBB旋转框（obb）
    
    Args:
        det_results: YOLO检测预测结果（detect或obb模型）
        verbose: 是否打印详细信息

    Returns:
        total_area: 所有预测框的总面积（像素数量）
    """
    total_area = 0
    box_count = 0

    for r in det_results:
        # 检查是否是OBB结果
        if r.obb is not None and len(r.obb) > 0:
            # OBB格式
            obb_coords = r.obb.xyxyxyxy.cpu().numpy()
            for obb in obb_coords:
                # 使用鞋带公式计算四边形面积
                area = calculate_obb_area(obb)
                total_area += area
                box_count += 1
        elif r.boxes is not None and len(r.boxes) > 0:
            # 普通检测框格式
            boxes = r.boxes
            for box_idx, box in enumerate(boxes):
                # 正确提取坐标：xyxy返回tensor，需要转换为numpy并取第一个元素
                xyxy = box.xyxy.cpu().numpy()[0]
                x1, y1, x2, y2 = xyxy

                # 计算预测框面积
                area = calculate_box_area(x1, y1, x2, y2)
                total_area += area
                box_count += 1

    # 输出总面积
    if verbose and box_count > 0:
        print(f"检测到 {box_count} 个预测框, 总面积: {total_area} 像素")

    return int(total_area)


def calculate_all_segmentation_areas(seg_results, image_shape):
    """
    计算所有分割物体面积
    
    Args:
        seg_results: YOLO分割预测结果
        image_shape: 图像尺寸 (height, width)
    
    Returns:
        total_area: 所有分割物体的总面积（像素数量）
    """
    total_area = 0
    
    for result in seg_results:
        if result.masks is not None:
            masks = result.masks.data.cpu().numpy()
            
            for obj_idx in range(len(masks)):
                # 获取mask并调整大小到图像尺寸
                mask = masks[obj_idx]
                if mask.shape != image_shape[:2]:
                    mask = cv2.resize(mask, (image_shape[1], image_shape[0]), interpolation=cv2.INTER_NEAREST)
                
                # 将mask转换为二值化（计算整个mask的面积，而不是只计算预测框区域内的）
                if mask.max() <= 1.0:
                    mask_binary = (mask > 0.5).astype(np.uint8)
                else:
                    mask_binary = (mask > 127).astype(np.uint8)
                
                # 计算非零像素的数量即为面积
                area = np.sum(mask_binary > 0)
                total_area += area
    
    return int(total_area)


def extract_segmented_regions(seg_results, original_image, seg_model):
    """从分割结果中提取所有分割区域"""
    segmented_regions = []
    image_shape = original_image.shape
    
    for result in seg_results:
        if result.masks is None:
            continue
        
        masks = result.masks.data.cpu().numpy()
        boxes = result.boxes.xyxy.cpu().numpy()
        classes = result.boxes.cls.cpu().numpy()
        confs = result.boxes.conf.cpu().numpy()
        
        for obj_idx in range(len(masks)):
            class_id = int(classes[obj_idx])
            class_name = seg_model.names[class_id] if hasattr(seg_model, 'names') else f"class_{class_id}"
            conf = float(confs[obj_idx])
            
            pred_box = boxes[obj_idx]
            pred_bbox_area = int((pred_box[2] - pred_box[0]) * (pred_box[3] - pred_box[1]))
            
            mask = masks[obj_idx]
            if mask.shape != image_shape[:2]:
                mask = cv2.resize(mask, (image_shape[1], image_shape[0]), interpolation=cv2.INTER_NEAREST)
            
            mask_binary = (mask > 0.5).astype(np.uint8) * 255 if mask.max() <= 1.0 else (mask > 127).astype(np.uint8) * 255
            
            mask_area = int(np.sum(mask_binary > 0))
            
            ys_nonzero, xs_nonzero = np.where(mask_binary > 0)
            if len(xs_nonzero) == 0 or len(ys_nonzero) == 0:
                continue
            
            x1, y1 = max(0, int(xs_nonzero.min())), max(0, int(ys_nonzero.min()))
            x2, y2 = min(image_shape[1], int(xs_nonzero.max()) + 1), min(image_shape[0], int(ys_nonzero.max()) + 1)
            
            cropped_mask = mask_binary[y1:y2, x1:x2]
            cropped_image = original_image[y1:y2, x1:x2].copy()
            cropped_image[np.where(cropped_mask == 0)] = 0
            
            if cropped_image.size > 0 and cropped_mask.size > 0:
                segmented_regions.append((cropped_mask, cropped_image, (x1, y1, x2, y2),
                                          class_id, class_name, mask_area, pred_bbox_area, conf))
    
    return segmented_regions


def filter_by_class(regions, class_id):
    """按类别过滤分割区域"""
    return [r for r in regions if r[3] == class_id]


def get_largest_region(regions):
    """获取面积最大的分割区域"""
    return max(regions, key=lambda r: r[5]) if regions else None


def get_highest_conf_region(regions):
    """获取置信度最高的分割区域"""
    return max(regions, key=lambda r: r[7]) if regions else None


def calculate_obb_area_by_class(det_results, image_shape):
    """
    按类别计算OBB检测框的实际覆盖面积
    
    Args:
        det_results: YOLO OBB检测结果
        image_shape: 图像尺寸 (height, width)
    
    Returns:
        class_areas: dict, {class_id: area} 各类别的覆盖面积
    """
    # 创建各类别的mask图像
    class_areas = {}
    
    for r in det_results:
        if r.obb is not None and len(r.obb) > 0:
            obb_coords = r.obb.xyxyxyxy.cpu().numpy()
            classes = r.obb.cls.cpu().numpy()
            
            for obj_idx, obb in enumerate(obb_coords):
                class_id = int(classes[obj_idx])
                
                if class_id not in class_areas:
                    class_areas[class_id] = np.zeros((image_shape[0], image_shape[1]), dtype=np.uint8)
                
                pts = obb.astype(np.int32)
                pts[:, 0] = np.clip(pts[:, 0], 0, image_shape[1] - 1)
                pts[:, 1] = np.clip(pts[:, 1], 0, image_shape[0] - 1)
                cv2.fillPoly(class_areas[class_id], [pts], 255)
    
    # 统计各类别的面积
    result = {}
    for class_id, mask in class_areas.items():
        result[class_id] = int(np.sum(mask > 0))
    
    return result


def draw_obb_by_class(result, output_image, class_colors):
    """
    按类别绘制OBB框
    
    Args:
        det_results: YOLO OBB检测结果
        output_image: 输出图像
        class_colors: dict, {class_id: (B, G, R)} 类别颜色
    
    Returns:
        total_boxes: 总检测框数量
    """
    total_boxes = 0
    
    for r in result:
        if r.obb is not None and len(r.obb) > 0:
            obb_coords = r.obb.xyxyxyxy.cpu().numpy()
            classes = r.obb.cls.cpu().numpy()
            
            for obj_idx, obb in enumerate(obb_coords):
                class_id = int(classes[obj_idx])
                color = class_colors.get(class_id, (0, 0, 255))
                pts = obb.astype(np.int32)
                total_boxes += 1
                cv2.polylines(output_image, [pts], isClosed=True, color=color, thickness=2)
    
    return total_boxes


# OBB模型类别名称（根据实际模型调整）
OBB_CLASS_NAMES = {
    0: "chalk",
    1: "anabrosis", 
    2: "scab"
}

# OBB模型类别颜色 (BGR格式)
OBB_CLASS_COLORS = {
    0: (0, 255, 0),    # 绿色 - 花皮
    1: (0, 0, 255),   # 红色 - 溃疡
    2: (255, 0, 0)    # 蓝色 - 沙皮
}


# 主程序
if __name__ == "__main__":


    seg_model = YOLO("yolo11n-seg.pt")
    obb_model = YOLO("/Users/senga/Desktop/脐橙沙皮溃疡花皮检测/模型/0608/best.pt")
    
    # 预测
    image_dir = "/Users/senga/Desktop/脐橙沙皮溃疡花皮检测/验证集100"
    
    # 创建输出目录保存分割后的图片
    output_dir = "/Users/senga/Desktop/脐橙沙皮溃疡花皮检测/output"
    os.makedirs(output_dir, exist_ok=True)
    
    # 支持的图像文件扩展名
    image_extensions = {'.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.tif', '.webp'}
    
    # 用于存储预测结果的列表
    prediction_results = []
    
    for image_file in os.listdir(image_dir):
        # 检查文件扩展名
        file_ext = os.path.splitext(image_file)[1].lower()
        if file_ext not in image_extensions:
            continue
        
        image_path = os.path.join(image_dir, image_file)
        original_image = cv2.imread(image_path)
        
        # 检查图像是否成功加载
        if original_image is None:
            print(f"警告: 无法读取图像文件 {image_file}，跳过")
            continue
        
        image_shape = original_image.shape

        # 第一步：先进行分割
        seg_results = seg_model(image_path, conf=0.1, verbose=False)
        
        # 第二步：提取分割区域
        regions = extract_segmented_regions(seg_results, original_image, seg_model)
        # 过滤class=49
        regions = filter_by_class(regions, 49)
        
        if not regions:
            print(f"{image_file}: 未检测到橙子，跳过")
            continue
        
        # 过滤class=49后，取面积最大的对象
        chosen = get_largest_region(regions)
        if not chosen:
            print(f"{image_file}: 无法获取最高置信度橙子，跳过")
            continue
        target_mask, target_cropped, target_bbox, target_class_id, target_class_name, total_seg_area, pred_bbox_area, conf = chosen
        print(f"  => 选中: bbox={target_bbox}, mask_area={total_seg_area}, conf={conf:.3f}")
        
        # 获取原始文件名（不含扩展名）
        base_name = os.path.splitext(image_file)[0]
        
        # 直接保存分割结果（不进行OBB检测）
        if target_cropped.size == 0:
            print(f"{image_file}: 目标橙子裁剪图像为空，跳过")
            continue
        
        # 第三步：对目标橙子（最大分割区域）进行OBB检测（支持3类别）
        total_box_area = 0
        total_det_boxes = 0
        
        if target_cropped.size == 0:
            print(f"{image_file}: 目标橙子裁剪图像为空，跳过")
            continue
        
        # 创建用于绘制的图像副本
        output_image = target_cropped.copy()
        
        # 对目标橙子区域进行OBB检测
        det_results = obb_model(target_cropped, verbose=False, conf=0.225, max_det=1000, agnostic_nms=True, iou=0.3)

        # 计算目标橙子区域内各类别检测框的实际覆盖面积（去重，重叠部分只计算一次）
        cropped_shape = target_cropped.shape[:2]
        class_areas = calculate_obb_area_by_class(det_results, cropped_shape)

        # 计算总面积
        total_box_area = sum(class_areas.values())

        # 按类别统计检测框数量
        class_box_counts = {}
        for r in det_results:
            if r.obb is not None and len(r.obb) > 0:
                classes = r.obb.cls.cpu().numpy()
                for cls in classes:
                    class_id = int(cls)
                    class_box_counts[class_id] = class_box_counts.get(class_id, 0) + 1
                    total_det_boxes += 1
            elif r.boxes is not None and len(r.boxes) > 0:
                classes = r.boxes.cls.cpu().numpy()
                for cls in classes:
                    class_id = int(cls)
                    class_box_counts[class_id] = class_box_counts.get(class_id, 0) + 1
                    total_det_boxes += 1

        # 按类别绘制OBB框
        for r in det_results:
            if r.obb is not None and len(r.obb) > 0:
                obb_coords = r.obb.xyxyxyxy.cpu().numpy()
                classes = r.obb.cls.cpu().numpy()
                for obj_idx, obb in enumerate(obb_coords):
                    class_id = int(classes[obj_idx])
                    color = OBB_CLASS_COLORS.get(class_id, (0, 0, 255))
                    pts = obb.astype(np.int32)
                    cv2.polylines(output_image, [pts], isClosed=True, color=color, thickness=2)
            elif r.boxes is not None and len(r.boxes) > 0:
                boxes = r.boxes.xyxy.cpu().numpy()
                classes = r.boxes.cls.cpu().numpy()
                for obj_idx, xyxy in enumerate(boxes):
                    class_id = int(classes[obj_idx])
                    color = OBB_CLASS_COLORS.get(class_id, (0, 0, 255))
                    x1, y1, x2, y2 = xyxy.astype(int)
                    cv2.rectangle(output_image, (x1, y1), (x2, y2), color, 2)

        # 保存绘制后的图片
        output_filename = f"{base_name}_target_orange_class_{target_class_name}_{target_class_id}.png"
        output_path = os.path.join(output_dir, output_filename)
        cv2.imwrite(output_path, output_image)

        # 输出按类别的汇总信息
        print(f"{image_file}: 检测到 {total_det_boxes} 个预测框")
        for class_id in sorted(class_areas.keys()):
            class_name = OBB_CLASS_NAMES.get(class_id, f"class_{class_id}")
            area = class_areas.get(class_id, 0)
            count = class_box_counts.get(class_id, 0)
            ratio = (area / total_seg_area * 100) if total_seg_area > 0 else 0
            print(f"  - {class_name}: {count}个框, 面积={area}像素, 占比={ratio:.2f}%")

        print(f"{image_file}: 目标橙子分割图已保存至 {output_path}")

        # 计算总预测框面积/分割物体面积占比
        if total_seg_area > 0:
            ratio = (total_box_area / total_seg_area) * 100
            print(f"{image_file} 总预测框面积/分割物体面积占比: {ratio:.2f}%")
        else:
            ratio = 0.0
            print(f"{image_file} 未检测到任何分割对象")

        # 记录预测结果到列表（包含3个类别的详细统计）
        prediction_results.append({
            '图片名称': image_file,
            '预测个数': total_det_boxes,
            '占比(%)': round(ratio, 2),
            'chalk个数': class_box_counts.get(0, 0),
            'chalk面积': class_areas.get(0, 0),
            'anabrosis个数': class_box_counts.get(1, 0),
            'anabrosis面积': class_areas.get(1, 0),
            'scab个数': class_box_counts.get(2, 0),
            'scab面积': class_areas.get(2, 0),
        })

    # 将所有预测结果写入CSV文件
    import csv
    csv_output_path = "/Users/senga/Desktop/脐橙沙皮溃疡花皮检测/prediction_results.csv"
    if prediction_results:
        with open(csv_output_path, 'w', newline='', encoding='utf-8-sig') as csvfile:
            fieldnames = ['图片名称', '预测个数', '占比(%)',
                          'chalk个数', 'chalk面积', 'anabrosis个数', 'anabrosis面积',
                          'scab个数', 'scab面积']
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)

            writer.writeheader()
            for result in prediction_results:
                writer.writerow(result)

        print(f"\n预测结果已保存到: {csv_output_path}")
        print(f"共处理 {len(prediction_results)} 张图片")