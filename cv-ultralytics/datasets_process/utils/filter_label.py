import os

def filter_class_id(input_folder, output_folder, target_class_id=17):
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)

    for filename in os.listdir(input_folder):
        if filename.endswith(".txt"):
            input_path = os.path.join(input_folder, filename)
            output_path = os.path.join(output_folder, filename)

            with open(input_path, 'r') as infile, open(output_path, 'w') as outfile:
                for line in infile:
                    parts = line.strip().split()
                    if len(parts) == 9:
                        current_class_id = int(parts[0])
                        if current_class_id == target_class_id:
                            outfile.write(' '.join(parts) + '\n')

if __name__ == "__main__":
    input_folder = "/Users/senga/Downloads/茉莉花识别/only_flower/preprocessx4/labels"     # 替换为你的输入文件夹路径
    output_folder = "/Users/senga/Downloads/茉莉花识别/only_flower/只识别正常花/labels"   # 替换为你的输出文件夹路径

    filter_class_id(input_folder, output_folder)
