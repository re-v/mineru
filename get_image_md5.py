import hashlib
import os
import shutil


def get_md5(file_path):
    # 创建一个 md5 对象
    md5_hash = hashlib.md5()

    # 打开文件并以二进制模式读取
    with open(file_path, "rb") as f:
        # 分块读取文件数据，避免大文件占用大量内存
        for chunk in iter(lambda: f.read(4096), b""):
            md5_hash.update(chunk)

    # 返回计算出的 MD5 值
    return md5_hash.hexdigest()


def img_replace_into_md5(md_path, output_image_path):
    result = ""
    with open(md_path, "r", encoding="utf-8") as f:
        result = f.read()

    for img_path in os.listdir(output_image_path):
        origin_content = img_path
        full_path = os.path.join(output_image_path, img_path)
        suffix = os.path.splitext(img_path)[-1]
        md5_value = get_md5(full_path)
        shutil.move(full_path, os.path.join(output_image_path, md5_value + suffix))
        result = result.replace(origin_content, md5_value + suffix)
    return result
