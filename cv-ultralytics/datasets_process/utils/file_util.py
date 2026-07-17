import os


def create_dir_and_move_file(dir_path, file_name, suffix):

    file_path = create_dir(dir_path, file_name)

    # 移动所有文件到新目录
    for filename in os.listdir(dir_path):
        if filename.endswith(suffix):
            os.rename(os.path.join(dir_path, filename), f'{file_path}/{filename}')


def create_dir(dir_path, file_name):
    file_path = os.path.join(dir_path, file_name)
    if not os.path.exists(file_path):
        os.mkdir(file_path)
    return file_path
