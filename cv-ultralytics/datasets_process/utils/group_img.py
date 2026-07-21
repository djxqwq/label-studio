import os
import sys
import random
import shutil
import logging
from shutil import copyfile

project_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(project_path)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
)
log = logging.getLogger(__name__)

# 与训练服务 build_dataset 保持一致
IMAGE_EXTS = ('.jpg', '.jpeg', '.png', '.bmp', '.webp', '.tif', '.tiff')


def _is_image_file(name: str) -> bool:
    return name.lower().endswith(IMAGE_EXTS)


def split_dataset(src_dir: str, dst_dir: str, train_ratio: float = 0.8, valid_ratio: float = 0.15, test_ratio: float = 0.05):
    """
    划分数据集为 train/valid/test（detect/obb/seg：images + labels）
    """
    log.info("========== 数据集分割开始 ==========")
    log.info(f"源数据目录：{src_dir}")
    log.info(f"目标数据目录：{dst_dir}")
    log.info(f"分割比例 -> 训练集：{train_ratio}  验证集：{valid_ratio}  测试集：{test_ratio}")

    images = [f for f in os.listdir(os.path.join(src_dir, 'images')) if _is_image_file(f)]
    labels = [f for f in os.listdir(os.path.join(src_dir, 'labels')) if f.endswith('.txt')]

    log.info("---------- 原始数据统计 ----------")
    log.info(f"图像文件总数：{len(images)}")
    log.info(f"标签文件总数：{len(labels)}")

    data_dict = {}
    skipped = []
    for img in images:
        base_name = os.path.splitext(img)[0]
        txt_file = base_name + '.txt'
        if txt_file in labels:
            data_dict[img] = txt_file
        else:
            skipped.append(img)
            log.warning(f"跳过无对应标签文件的图像：{img}")

    log.info(f"成功配对图像 - 标签数：{len(data_dict)}")
    log.info(f"因缺少标签而跳过的图像数：{len(skipped)}")

    data_pairs = list(data_dict.items())
    random.shuffle(data_pairs)
    log.info("数据集已随机打乱")

    total_data = len(data_pairs)
    if total_data < 2:
        raise ValueError(f'可配对样本过少（{total_data}），至少需要 2 张')

    train_size = int(total_data * train_ratio)
    valid_size = max(1, int(total_data * valid_ratio))
    test_size = total_data - train_size - valid_size

    if test_size < 0:
        train_size += test_size
        test_size = 0

    log.info("---------- 分组统计 ----------")
    log.info(f"数据集总量：{total_data}")
    log.info(f"训练集数量：{train_size}（{train_size / total_data * 100:.1f}%）")
    log.info(f"验证集数量：{valid_size}（{valid_size / total_data * 100:.1f}%）")
    log.info(f"测试集数量：{test_size}（{test_size / total_data * 100:.1f}%）")

    train_data = data_pairs[:train_size]
    valid_data = data_pairs[train_size:train_size + valid_size]
    test_data = data_pairs[train_size + valid_size:]

    log.info("---------- 准备目标目录 ----------")
    if os.path.exists(dst_dir):
        log.info(f"目标目录已存在，正在清空：{dst_dir}")
        shutil.rmtree(dst_dir)
        os.makedirs(dst_dir)
        log.info(f"目标目录已重建：{dst_dir}")
    else:
        log.info(f"目标目录不存在，正在创建：{dst_dir}")
        os.makedirs(dst_dir)

    for phase in ['train', 'valid', 'test']:
        img_dir = os.path.join(dst_dir, phase, 'images')
        lbl_dir = os.path.join(dst_dir, phase, 'labels')
        os.makedirs(img_dir, exist_ok=True)
        os.makedirs(lbl_dir, exist_ok=True)
        log.info(f"已创建目录：{img_dir}")
        log.info(f"已创建目录：{lbl_dir}")

    log.info("---------- 开始复制文件 ----------")
    phase_map = [('train', train_data), ('valid', valid_data), ('test', test_data)]
    for phase, data in phase_map:
        log.info(f"[{phase}] 开始复制，共 {len(data)} 条样本")
        for img, label in data:
            img_src = os.path.join(src_dir, 'images', img)
            label_src = os.path.join(src_dir, 'labels', label)
            img_dst = os.path.join(dst_dir, phase, 'images', img)
            label_dst = os.path.join(dst_dir, phase, 'labels', label)
            copyfile(img_src, img_dst)
            copyfile(label_src, label_dst)
        log.info(f"[{phase}] 复制完成，图像目录：{os.path.join(dst_dir, phase, 'images')}")

    log.info("========== 数据集分割完成 ==========")
    log.info("分割结果汇总：训练集={}（{}条），验证集={}（{}条），测试集={}（{}条）".format(
        train_ratio, train_size,
        valid_ratio, valid_size,
        test_ratio, test_size,
    ))


def split_cls_dataset(src_dir: str, dst_dir: str, train_ratio: float = 0.8, valid_ratio: float = 0.15, test_ratio: float = 0.05):
    """
    划分分类数据集为 ImageFolder 结构：
      src:  classes/<class_name>/*.jpg
      dst:  train|val|test/<class_name>/*.jpg
    Ultralytics classify 使用 val（不是 valid）。
    """
    classes_root = os.path.join(src_dir, 'classes')
    if not os.path.isdir(classes_root):
        raise FileNotFoundError(f'分类数据缺少 classes 目录：{classes_root}')

    class_names = sorted([d for d in os.listdir(classes_root) if os.path.isdir(os.path.join(classes_root, d))])
    if not class_names:
        raise ValueError('classes 下没有任何类别文件夹')

    samples = []
    for cls_name in class_names:
        cls_dir = os.path.join(classes_root, cls_name)
        for name in os.listdir(cls_dir):
            if _is_image_file(name):
                samples.append((cls_name, os.path.join(cls_dir, name), name))

    if len(samples) < 2:
        raise ValueError(f'分类图片过少（{len(samples)}），至少需要 2 张')

    random.shuffle(samples)
    total = len(samples)
    train_size = int(total * train_ratio)
    valid_size = max(1, int(total * valid_ratio))
    test_size = total - train_size - valid_size
    if test_size < 0:
        train_size += test_size
        test_size = 0

    splits = {
        'train': samples[:train_size],
        'val': samples[train_size:train_size + valid_size],
        'test': samples[train_size + valid_size:],
    }

    if os.path.exists(dst_dir):
        shutil.rmtree(dst_dir)
    for phase, items in splits.items():
        for cls_name, src, name in items:
            out_dir = os.path.join(dst_dir, phase, cls_name)
            os.makedirs(out_dir, exist_ok=True)
            copyfile(src, os.path.join(out_dir, name))

    log.info(
        "分类数据集分割完成：train=%s val=%s test=%s classes=%s",
        len(splits['train']), len(splits['val']), len(splits['test']), class_names,
    )


if __name__ == '__main__':
    current_file_path = os.path.abspath(__file__)
    parent_path = os.path.dirname(os.path.dirname(current_file_path))
    src_dir = '/Users/senga/Downloads/茉莉花_0617'
    dst_dir = os.path.join(parent_path, 'data')
    split_dataset(src_dir, dst_dir)
