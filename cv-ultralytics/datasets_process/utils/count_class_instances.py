#!/usr/bin/env python3
"""统计YOLO训练数据中每个class的实例数量"""

from pathlib import Path
from collections import defaultdict

def count_class_instances(data_root: str = "datasets_process/data") -> dict:
    """统计所有数据集中每个类别的实例数量
    
    Args:
        data_root: 数据根目录路径
        
    Returns:
        字典，key为class_id，value为实例数量
    """
    data_path = Path(data_root)
    class_counts = defaultdict(int)
    
    # 遍历三个子文件夹 (train, valid, test)
    for sub_dir in ['train', 'valid', 'test']:
        labels_dir = data_path / sub_dir / "labels"
        
        if not labels_dir.exists():
            print(f"警告: {labels_dir} 不存在，跳过")
            continue
            
        print(f"正在处理: {sub_dir}")
        
        # 遍历labels目录下所有txt文件
        for txt_file in labels_dir.glob("*.txt"):
            try:
                with open(txt_file, 'r', encoding='utf-8') as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        
                        # 用空格分割，取第一个数字作为class_id
                        parts = line.split()
                        if parts:
                            class_id = int(parts[0])
                            class_counts[class_id] += 1
                            
            except Exception as e:
                print(f"错误: 读取 {txt_file} 时出错: {e}")
    
    return dict(class_counts)


def main():
    print("=" * 50)
    print("YOLO数据集类别实例统计")
    print("=" * 50)
    
    # 统计
    counts = count_class_instances("/Users/senga/PycharmProjects/cv-ultralytics/datasets_process/data")
    
    # 输出结果
    print("\n" + "=" * 50)
    print("统计结果:")
    print("=" * 50)
    
    if not counts:
        print("未找到任何标注文件")
        return
    
    # 按class_id排序输出
    total = 0
    for class_id in sorted(counts.keys()):
        count = counts[class_id]
        total += count
        print(f"Class {class_id}: {count} 个实例")
    
    print("-" * 50)
    print(f"总计: {total} 个实例")


if __name__ == "__main__":
    main()