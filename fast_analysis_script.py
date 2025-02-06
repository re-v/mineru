#!/usr/bin/env python
# -*- coding: UTF-8 -*-
'''
@Project ：MinerU 
@File    ：fast_analysis_script.py
@IDE     ：PyCharm 
@Author  ：wgl
@Date    ：2025/1/24 15:34 
'''
import argparse
import asyncio
import logging
import tarfile

import aiohttp

from configs.config import MULTI_MODEL_SERVER, BASEDIR

"""
直接执行命令 传入文件夹 例如 python fast_analysis_script --folder input_path --target output_path
fast_analysis_script.py 接受文件夹下所有pdf文件(检查文件格式) 并执行解析任务
    - 如果解析结果没有图片,直接写入output_path
    - 如果有图片,调用多模态接口,获取接口返回, 写入output_path
DONE !
"""
from magic_pdf_parse_main import pdf_parse_main
import os
import requests

# 多模态接口的 URL（示例）
MULTIMODAL_API_URL = "https://example.com/multimodal-api"


def is_pdf(file_path):
    """检查文件是否是 PDF 文件"""
    return file_path.lower().endswith('.pdf')


def extract_text_and_images(pdf_path):
    """从 PDF 文件中提取文本和图片"""
    result = pdf_parse_main(pdf_path)

    return result


def call_multimodal_api(image_data):
    """调用多模态接口"""
    try:
        response = requests.post(
            MULTIMODAL_API_URL,
            files={"image": image_data},
            headers={"Content-Type": "application/octet-stream"}
        )
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"调用多模态接口失败: {e}")
        return None


def compress_files(output_path: str, file_name: str) -> str:
    tar_filepath = os.path.join(output_path, f"{file_name}.tar.gz")
    with tarfile.open(tar_filepath, 'w:gz') as tar:
        for root, dirs, files in os.walk(output_path):
            for file in files:
                if file.endswith(".md") or root.endswith("images"):
                    file_path = os.path.join(root, file)
                    tar.add(file_path, arcname=os.path.relpath(file_path, output_path))
    return tar_filepath


async def call_multi_model_4local(pdf_path: str):
    pdf_name = os.path.basename(pdf_path).split(".")[0]
    pdf_path_parent = os.path.dirname(pdf_path)

    output_path = os.path.join(pdf_path_parent, pdf_name)

    # 压缩output_path 路径下的md文件,images图片包 stream传输
    zip_filepath = compress_files(output_path, pdf_name)
    # todo 修改此处local文件生成接口
    url = MULTI_MODEL_SERVER["host_port"] + "/local_md"

    try:
        async with aiohttp.ClientSession() as session:
            with open(zip_filepath, 'rb') as file:
                form_data = aiohttp.FormData()
                form_data.add_field('file', file, filename=pdf_name, content_type='application/pdf')

                async with session.post(url, data=form_data) as response:
                    if response.status == 200:
                        logging.info("请求成功")
                    else:
                        logging.error(f"请求失败，状态码: {response.status}")
    except Exception as e:
        logging.error(f"请求过程中出错: {str(e)}")


def process_pdf(pdf_path, target):
    """处理单个 PDF 文件"""
    print(pdf_path)
    extract_text_and_images(pdf_path)
    # pdf 检查解析结果有无图片
    try:
        pdf_name = os.path.basename(pdf_path).split(".")[0]
        pdf_path_parent = os.path.dirname(pdf_path)

        output_path = os.path.join(pdf_path_parent, pdf_name)

        output_image_path = os.path.join(output_path, 'images')
        output_md_path = os.path.join(output_path, f"{pdf_name}.md")
        md_path = os.path.join(target, f"{pdf_name}.md")
        # with open(output_md_path, "r", encoding="utf-8") as f:
        #     result = f.read()
        # with open(md_path, "w") as f:
        #     f.write(result)
        if not os.path.exists(output_image_path):
            with open(output_md_path, "r", encoding="utf-8") as f:
                result = f.read()
            with open(md_path, "w") as f:
                f.write(result)
            print(f"images不包含图片")
        else:
            # 先验图片存在 则直接去多模态服务获取output_file
            exist_images = True
            if exist_images:
                # 调用muitimodel获取图片解析内容
                asyncio.run(call_multi_model_4local(pdf_path))
                print("调用多模态")
    except Exception as e:
        print(f"Error in process_pdf: {str(e)}")


def main(input_path, target):
    """主函数：处理文件夹中的所有 PDF 文件"""
    folder = os.path.join(BASEDIR, input_path)
    if not os.path.exists(target):
        os.makedirs(target)

    for file_name in os.listdir(folder):
        file_path = os.path.join(folder, file_name)
        if is_pdf(file_path):
            print(f"正在处理文件: {file_path}")
            process_pdf(file_path, target)
        else:
            print(f"跳过非 PDF 文件: {file_path}")


if __name__ == '__main__':
    # 解析命令行参数
    parser = argparse.ArgumentParser(description="快速分析 PDF 文件")
    parser.add_argument('--folder', required=True, help="输入文件夹路径")
    parser.add_argument('--target', required=True, help="输出文件夹路径")
    args = parser.parse_args()

    # 执行主函数
    main(args.folder, args.target)
    # doc: python3 fast_analysis_script.py --folder input_path --target output_path
    # main("input_path", "output_path")
