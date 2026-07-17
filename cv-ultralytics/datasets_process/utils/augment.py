import albumentations as A
import os
import shutil
import numpy as np
from PIL import Image


def convert(base_path, augment_times):
    input_image_dir = base_path + "/images"
    input_label_dir = base_path + "/labels"
    print('开始执行{}倍数据增广...'.format(augment_times))
    augmentation_sequence = A.Compose([
        A.GaussianBlur(blur_limit=(3, 7), p=0.3),
        A.AutoContrast(limit=(0.8, 1.2), p=0.5),
        A.GaussNoise(var_limit=(10.0, 50.0), per_channel=True, p=0.2),
        A.RandomBrightnessContrast(brightness_limit=(-0.5, 0.2), contrast_limit=0, p=0.5),
        # A.Rotate(limit=(180, 180), p=0.3),
    ])
    current_file_path = os.path.abspath(__file__)
    parent_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(current_file_path))), "augment")
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
    # 获取所有图像文件
    image_files = [f for f in os.listdir(input_image_dir) if os.path.isfile(os.path.join(input_image_dir, f))]
    # 对每个图像文件进行增强
    for image_file in image_files:
        # 构建对应的标签文件名
        label_file = image_file.replace(".jpg", ".txt").replace(".png", ".txt")
        label_file = label_file.replace(".jpeg", ".txt")
        label_path = os.path.join(input_label_dir, label_file)

        # 检查标签文件是否存在
        if not os.path.exists(label_path):
            print(f"跳过 {image_file}，因为找不到对应的标签文件 {label_file}")
            continue

        # 读取图像和标签
        image_path = os.path.join(input_image_dir, image_file)
        image = Image.open(image_path)
        image = np.array(image)
        with open(label_path, 'r') as f:
            label_content = f.readlines()

        try:
            # 应用增强
            for i in range(1, augment_times + 1):
                augmented = augmentation_sequence(image=image)
                image_aug = augmented['image']

                # 保存增强后的图像和标签
                res_file_name = image_file.replace(".jpg", "")
                output_image_path = os.path.join(output_image_dir, f"img_{res_file_name}_{i}.jpg")
                output_label_path = os.path.join(output_label_dir, f"img_{res_file_name}_{i}.txt")
                print(output_image_path)
                Image.fromarray(image_aug).save(output_image_path)
                with open(output_label_path, 'w') as f:
                    f.writelines(label_content)
        except Exception as e:
            continue
    print(f"数据增广执行完成，总共生成了 {len(os.listdir(output_image_dir))} 张图片。")


# 输入和输出目录
base_path = "/Users/senga/Downloads/matched_images"
convert(base_path, 3)
