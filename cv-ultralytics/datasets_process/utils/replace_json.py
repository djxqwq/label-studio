import os
import json


def replace_in_json_files(folder_path, old_str, new_str):
    # 遍历文件夹下的所有.json文件
    for filename in os.listdir(folder_path):
        if filename.endswith(".json"):
            file_path = os.path.join(folder_path, filename)

            try:
                print(f"正在处理文件: {file_path}")

                # 以文本模式逐行读取并替换内容
                with open(file_path, 'r', encoding='utf-8') as file:
                    lines = file.readlines()

                # 替换每一行中的旧字符串
                updated_lines = [line.replace(old_str, new_str) for line in lines]

                # 写回原文件
                with open(file_path, 'w', encoding='utf-8') as file:
                    file.writelines(updated_lines)

                print(f"{filename} 处理完成并已保存。")

            except Exception as e:
                print(f"处理文件 {filename} 时发生错误: {e}")


# 使用方法：
folder = "/Users/senga/Downloads/茉莉花识别/2打标数据/tmp"  # 替换为你的文件夹路径
old_char = "wither"  # 指定你想要替换掉的字符
new_char = "other"  # 指定替换成的新字符

replace_in_json_files(folder, old_char, new_char)
# seed
# initiation
# blooming
# bloomed
# wither
