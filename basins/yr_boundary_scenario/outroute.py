import os
import re

def process_settings_files():
    # 获取当前目录下所有以"settings"开头的txt文件
    for filename in os.listdir('.'):
        if filename.startswith('settings') and filename.endswith('.txt'):
            # 提取文件名中最后一个'_'之后、'.txt'之前的部分
            prefix = filename.split('_')[-1].split('.')[0]
            
            # 读取文件内容
            with open(filename, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            
            # 查找并修改第一个以"PathOut = ./"开头的行
            modified = False
            for i, line in enumerate(lines):
                if line.startswith('PathOut = ./'):
                    lines[i] = f"PathOut = ./{prefix}\n"
                    modified = True
                    break
            
            # 如果有修改，则写回文件
            if modified:
                with open(filename, 'w', encoding='utf-8') as f:
                    f.writelines(lines)
                print(f"已处理文件: {filename} -> PathOut = ./{prefix}")
            else:
                print(f"文件 {filename} 中未找到'PathOut = ./'开头的行")

if __name__ == '__main__':
    process_settings_files()
    print("处理完成！")