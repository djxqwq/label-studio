import os


def replace_text_in_files(directory):
    # 遍历指定目录下的所有文件
    for filename in os.listdir(directory):
        if filename.endswith(".txt"):  # 确保处理的是文本文件
            file_path = os.path.join(directory, filename)
            # 读取文件内容
            with open(file_path, 'r', encoding='utf-8') as file:
                content = file.read()

            content = content.replace('None ', '16 ')
            # content = content.replace('17 ', '15 ')

            # 将更新后的内容写回文件
            with open(file_path, 'w', encoding='utf-8') as file:
                file.write(content)
            print(f"Updated content in {filename}")


# 请将下面的路径替换为你想要处理的文件夹路径
your_directory_path = '/Users/senga/Downloads/茉莉花识别/2打标数据/上花/labels'
replace_text_in_files(your_directory_path)
