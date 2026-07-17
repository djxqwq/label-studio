from datasets_process.utils import  file_util
from datasets_process.convert import seed2obb



dir_path = "/Users/senga/Downloads/茉莉花识别/2打标数据/重新标注（花籽seed、即将开放blooming、已经开放bloomed、枯萎wither）"
file_util.create_dir_and_move_file(dir_path, "images", ".jpg")
file_util.create_dir_and_move_file(dir_path, "jsons", ".json")
file_util.create_dir(dir_path, "labels")

seed2obb.convert(dir_path)