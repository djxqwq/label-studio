import cv2
import os


def yolo_to_obb(label_path, output_path, img_path):
    image = cv2.imread(img_path)
    if image is None:
        return
    image_height, image_width, _ = image.shape
    yolo_file = open(output_path, 'w')

    # 读取LabelImg标签
    with open(label_path, 'r') as f:
        lines = f.readlines()

    for line in lines:
        line = line.strip().split()

        # 解析LabelImg的标签
        class_index, x_center, y_center, width, height = line
        x_center = float(x_center)
        y_center = float(y_center)
        width = float(width)
        height = float(height)

        x_min = x_center - width / 2
        y_min = y_center - height / 2
        x_max = x_center + width / 2
        y_max = y_center + height / 2

        x1, y1 = x_min, y_min
        x2, y2 = x_max, y_min
        x3, y3 = x_max, y_max
        x4, y4 = x_min, y_max

        # 写入YOLO格式
        yolo_file.write(f"{class_index} {x1:.6f} {y1:.6f} {x2:.6f} {y2:.6f} {x3:.6f} {y3:.6f} {x4:.6f} {y4:.6f}\n")
    yolo_file.close()
    print(f"YOLO格式文件已保存至： {output_path}")


base_path = "/Users/senga/Downloads/tray_detection/origin_images/20240624"
detect_label_path = f"{base_path}/labels"
obb_label_path = f"{base_path}/obb_labels"
image_path = f"{base_path}/images"


for filename in os.listdir(detect_label_path):
    idx = filename.rfind('.')
    image_name = filename[0: idx] + ".jpg"
    image = cv2.imread(image_path + "/" + image_name)
    if image is None:
        image_name = filename[0: idx] + ".jpeg"
    yolo_to_obb(os.path.join(detect_label_path, filename), obb_label_path + "/" + filename, image_path + "/" + image_name)
