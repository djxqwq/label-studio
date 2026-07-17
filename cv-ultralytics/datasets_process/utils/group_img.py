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

# 定义源数据目录和目标数据目录
current_file_path = os.path.abspath(__file__)
parent_path = os.path.dirname(os.path.dirname(current_file_path))
# src_dir = os.path.join(parent_path, 'augment')
src_dir = '/Users/senga/Downloads/茉莉花_0617'
dst_dir = os.path.join(parent_path, 'data')
log.info("========== 数据集分割开始 ==========")
log.info(f"源数据目录：{src_dir}")
log.info(f"目标数据目录：{dst_dir}")

# 定义数据集的比例
train_ratio = 0.8
valid_ratio = 0.15
test_ratio =  0.05

log.info(f"分割比例 -> 训练集: {train_ratio}  验证集: {valid_ratio}  测试集: {test_ratio}")

# 获取所有图像文件和标签文件的列表
images = [f for f in os.listdir(os.path.join(src_dir, 'images')) if f.endswith('.jpg') or f.endswith('.jpeg') or f.endswith('.png')]
labels = [f for f in os.listdir(os.path.join(src_dir, 'labels')) if f.endswith('.txt')]

log.info("---------- 原始数据统计 ----------")
log.info(f"图像文件总数：{len(images)}")
log.info(f"标签文件总数：{len(labels)}")

# 创建一个字典来存储图像和对应的标签文件
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

log.info(f"成功配对图像-标签数：{len(data_dict)}")
log.info(f"因缺少标签而跳过的图像数：{len(skipped)}")

# 将图像和标签文件配对
data_pairs = list(data_dict.items())

# 随机打乱数据集
random.shuffle(data_pairs)
log.info("数据集已随机打乱")

# 计算每个数据集的大小
total_data = len(data_pairs)
train_size = int(total_data * train_ratio)
valid_size = int(total_data * valid_ratio)
test_size = total_data - train_size - valid_size  # 剩余的数据作为测试集

log.info("---------- 分组统计 ----------")
log.info(f"数据集总量：{total_data}")
log.info(f"训练集数量：{train_size}（{train_size / total_data * 100:.1f}%）")
log.info(f"验证集数量：{valid_size}（{valid_size / total_data * 100:.1f}%）")
log.info(f"测试集数量：{test_size}（{test_size / total_data * 100:.1f}%）")

# 分割数据集
train_data = data_pairs[:train_size]
valid_data = data_pairs[train_size:train_size + valid_size]
test_data = data_pairs[train_size + valid_size:]

# 清空训练目录数据
log.info("---------- 准备目标目录 ----------")
if os.path.exists(dst_dir):
    log.info(f"目标目录已存在，正在清空：{dst_dir}")
    shutil.rmtree(dst_dir)
    os.makedirs(dst_dir)
    log.info(f"目标目录已重建：{dst_dir}")
else:
    log.info(f"目标目录不存在，正在创建：{dst_dir}")
    os.makedirs(dst_dir)

# 创建目标目录
for phase in ['train', 'valid', 'test']:
    img_dir = os.path.join(dst_dir, phase, 'images')
    lbl_dir = os.path.join(dst_dir, phase, 'labels')
    os.makedirs(img_dir, exist_ok=True)
    os.makedirs(lbl_dir, exist_ok=True)
    log.info(f"已创建目录：{img_dir}")
    log.info(f"已创建目录：{lbl_dir}")

# 复制文件到目标目录
log.info("---------- 开始复制文件 ----------")
phase_map = [('train', train_data), ('valid', valid_data), ('test', test_data)]
for phase, data in phase_map:
    log.info(f"[{phase}] 开始复制，共 {len(data)} 条样本")
    for img, label in data:
        img_src = os.path.join(src_dir, 'images', img)
        label_src = os.path.join(src_dir, 'labels', label)
        img_dst = os.path.join(dst_dir, phase, 'images', img)
        label_dst = os.path.join(dst_dir, phase, 'labels', label)
        log.debug(f"  复制图像：{img_src}  ->  {img_dst}")
        log.debug(f"  复制标签：{label_src}  ->  {label_dst}")
        copyfile(img_src, img_dst)
        copyfile(label_src, label_dst)
    log.info(f"[{phase}] 复制完成，图像目录：{os.path.join(dst_dir, phase, 'images')}")

log.info("========== 数据集分割完成 ==========")
log.info("分割结果汇总：训练集={}（{}条），验证集={}（{}条），测试集={}（{}条）".format(
    train_ratio, train_size,
    valid_ratio, valid_size,
    test_ratio, test_size,
))
