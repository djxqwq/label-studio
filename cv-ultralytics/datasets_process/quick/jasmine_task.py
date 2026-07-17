from datasets_process.utils import  file_util
from datasets_process.convert import jasmine2obb



dir_path = "/Users/senga/Downloads/茉莉花识别/2打标数据/tmp"
file_util.create_dir_and_move_file(dir_path, "images", ".jpg")
file_util.create_dir_and_move_file(dir_path, "jsons", ".json")
file_util.create_dir(dir_path, "labels")

jasmine2obb.convert(dir_path)