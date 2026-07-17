import os
import cv2
import numpy as np
import random
from datasets_process.common import jasmine_dict,single_class_color_dict
img_source_dir = "/Users/senga/Downloads/茉莉花_0617/delete_images"
label_source_dir = "/Users/senga/Downloads/茉莉花_0617/delete_labels"
output_dir = "/Users/senga/Downloads/茉莉花_0617/delete_predictions"

num_images = 500



def get_color_by_class(class_id):
    return jasmine_dict.get(class_id, single_class_color_dict.get(class_id))


def visualize_labels():
    if not os.path.exists(img_source_dir):
        raise Exception(f"图片文件夹不存在: {img_source_dir}")
    if not os.path.exists(label_source_dir):
        raise Exception(f"标签文件夹不存在: {label_source_dir}")
    
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    valid_extensions = ('.jpg', '.jpeg', '.png')
    all_images = [f for f in os.listdir(img_source_dir) 
                  if f.lower().endswith(valid_extensions)]
    
    if len(all_images) == 0:
        raise Exception(f"图片文件夹为空: {img_source_dir}")
    
    if len(all_images) <= num_images:
        selected_images = all_images
        print(f"图片数量不足{num_images}张，使用全部{len(all_images)}张")
    else:
        selected_images = random.sample(all_images, num_images)
        print(f"从{len(all_images)}张图片中随机选取了{num_images}张")
    
    for img_name in selected_images:
        base_name = os.path.splitext(img_name)[0]
        img_path = os.path.join(img_source_dir, img_name)
        label_path = os.path.join(label_source_dir, f"{base_name}.txt")
        
        image = cv2.imread(img_path)
        if image is None:
            print(f"读取图片失败: {img_path}")
            continue
        
        if not os.path.exists(label_path):
            print(f"标签文件不存在: {label_path}")
            continue
        
        image_height, image_width, _ = image.shape
        
        with open(label_path, 'r') as f:
            lines = f.readlines()
        
        for line in lines:
            parts = line.strip().split()
            if len(parts) < 9:
                continue
            
            class_index = int(parts[0])
            coords = [float(x) for x in parts[1:9]]
            x1, y1, x2, y2, x3, y3, x4, y4 = coords
            
            points = np.array([
                [int(x1 * image_width), int(y1 * image_height)],
                [int(x2 * image_width), int(y2 * image_height)],
                [int(x3 * image_width), int(y3 * image_height)],
                [int(x4 * image_width), int(y4 * image_height)]
            ], dtype=np.int32)
            
            color = get_color_by_class(class_index)
            cv2.polylines(image, [points], True, color, 2)
            
            label = str(class_index)
            text_x = int(min(x1, x2, x3, x4) * image_width)
            text_y = int(min(y1, y2, y3, y4) * image_height) - 10
            if text_y < 20:
                text_y = int(max(y1, y2, y3, y4) * image_height) + 20
            
            cv2.putText(image, label, (text_x, text_y),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1, cv2.LINE_AA)
        
        output_path = os.path.join(output_dir, img_name)
        cv2.imwrite(output_path, image)
        print(f"已保存: {output_path}")
    
    print(f"\n完成! 共处理{len(selected_images)}张，结果保存至: {output_dir}")


if __name__ == "__main__":
    visualize_labels()