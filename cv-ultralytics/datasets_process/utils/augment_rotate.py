import os
import shutil
import cv2


def rotate_obb_label_line(line, image_shape, angle):
    """
    输入一行YOLO OBB label数据，返回旋转后的label行
    line: str, like "0 0.1 0.2 0.3 0.4 0.5 0.6 0.7 0.8"
    image_shape: (height, width)
    angle: int, rotation in degrees (e.g., 90, 180, 270)
    return: str
    """
    h, w = image_shape
    data = list(map(float, line.strip().split()))
    class_id = int(data[0])
    coords = [(data[i], data[i + 1]) for i in range(1, len(data), 2)]

    rotated_coords = []

    for x_norm, y_norm in coords:
        x_pixel, y_pixel = x_norm * w, y_norm * h

        if angle == 90:  # 顺时针旋转90度
            new_x = h - y_pixel
            new_y = x_pixel
            new_w, new_h = h, w

        elif angle == 180:  # 顺时针旋转180度
            new_x = w - x_pixel
            new_y = h - y_pixel
            new_w, new_h = w, h

        elif angle == 270:  # 顺时针旋转270度 = 逆时针90度
            new_x = y_pixel
            new_y = w - x_pixel
            new_w, new_h = h, w

        else:
            raise ValueError(f"Unsupported rotation angle: {angle}")

        # 归一化到新尺寸
        x_new_norm = round(new_x / new_w, 6)
        y_new_norm = round(new_y / new_h, 6)

        rotated_coords.extend([x_new_norm, y_new_norm])

    new_line = f"{class_id} " + " ".join(map(str, rotated_coords))
    return new_line


def do_rotate(image, base_name, angle, lines, output_image_dir, output_label_dir):
    h, w = image.shape[:2]

    if angle == 90:
        image_aug = cv2.rotate(image, cv2.ROTATE_90_CLOCKWISE)
        new_w, new_h = h, w
    elif angle == 180:
        image_aug = cv2.rotate(image, cv2.ROTATE_180)
        new_w, new_h = w, h
    elif angle == 270:
        image_aug = cv2.rotate(image, cv2.ROTATE_90_COUNTERCLOCKWISE)
        new_w, new_h = h, w
    else:
        raise ValueError(f"Unsupported rotation angle: {angle}")

    output_image_path = os.path.join(output_image_dir, f"rotate_{angle}_{base_name}.jpg")
    cv2.imwrite(output_image_path, image_aug)

    rotated_lines = [rotate_obb_label_line(line, (new_h, new_w), angle) for line in lines]
    output_label_path = os.path.join(output_label_dir, f"rotate_{angle}_{base_name}.txt")
    with open(output_label_path, 'w') as f_out:
        f_out.write("\n".join(rotated_lines) + "\n")

    print(f"保存增强图像和标签: {output_image_path}, {output_label_path}")


def augment_and_rotate_labels(input_image_dir, input_label_dir):
    print('开始执行旋转数据增广...')

    current_file_path = os.path.abspath(__file__)
    parent_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(current_file_path))), "rotate_augment")
    output_image_dir = os.path.join(parent_path, "images")
    output_label_dir = os.path.join(parent_path, "labels")
    # 创建输出目录
    if os.path.exists(parent_path):
        # 删除目录及其所有内容
        shutil.rmtree(parent_path)
        # 重新创建目录
        os.makedirs(parent_path)
    else:
        print(f"目录 '{parent_path}' 不存在。")
    if not os.path.exists(output_image_dir):
        os.makedirs(output_image_dir)
    if not os.path.exists(output_label_dir):
        os.makedirs(output_label_dir)

    image_files = [f for f in os.listdir(input_image_dir) if os.path.isfile(os.path.join(input_image_dir, f))]

    for image_file in image_files:
        if image_file == '.DS_Store':
            continue

        base_name = os.path.splitext(image_file)[0]
        label_file = base_name + '.txt'
        label_path = os.path.join(input_label_dir, label_file)

        if not os.path.exists(label_path):
            print(f"未找到对应标签文件: {label_file}")
            continue

        with open(label_path, 'r') as file:
            lines = file.readlines()

        image_path = os.path.join(input_image_dir, image_file)
        image = cv2.imread(image_path)

        # 顺时针旋转角度
        angles = [90, 180, 270]
        for angle in angles:
            do_rotate(image, base_name, angle, lines, output_image_dir, output_label_dir)

        output_image_path = os.path.join(output_image_dir, f"{base_name}.jpg")
        shutil.copy(image_path, output_image_path)

        output_label_path = os.path.join(output_label_dir, label_file)
        shutil.copy(label_path, output_label_path)

    print("数据增广完成.")


if __name__ == "__main__":

    base_path = "/Users/senga/Downloads/茉莉花识别/2打标数据/上花打标数据"
    input_image_dir = base_path + "/images"
    input_label_dir = base_path + "/labels"
    augment_and_rotate_labels(input_image_dir, input_label_dir)