from datasets_process.convert import xlabel2obb
from datasets_process.utils import augment, file_util
import os


# create dir and move image
augment_times = 3
dir_path  = "/Users/senga/Downloads/2_photo_retake/3_valid/labeled_imgs/0303"

# jpeg to jpg
for item in os.listdir(dir_path):
    if item.endswith('.jpeg'):
        new_file_path = item[:-5] + '.jpg'
        os.rename(os.path.join(dir_path, item), os.path.join(dir_path, new_file_path))


file_util.create_dir_and_move_file(dir_path, "images", ".jpg")
file_util.create_dir_and_move_file(dir_path, "jsons", ".json")
file_util.create_dir(dir_path, "labels")

# xanylabeling to yolo_obb
xlabel2obb.convert(dir_path)

# augment
augment.convert(dir_path, augment_times)