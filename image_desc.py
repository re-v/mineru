#!/usr/bin/env python
# -*- coding: UTF-8 -*-
'''
@Project ：MinerU 
@File    ：image_desc.py
@IDE     ：PyCharm 
@Author  ：wgl
@Date    ：2025/3/24 11:12 
'''
import asyncio
import os
import re
import base64
import tarfile
import tempfile
import time
from collections import deque
from typing import List, Optional

import torch
from PIL import Image
from fastapi import FastAPI
from openai import OpenAI
from pydantic import BaseModel

from configs.config import BASEDIR, BAI_LIAN_API_KEY


class FileInfo(BaseModel):
    file_id: str
    content_path: str
    target_path: str
    content: str


class FileList(BaseModel):
    file_list: List[FileInfo]
    token: str
    callback_url: str


class ResponseModel(BaseModel):
    code: int
    msg: str
    data: Optional[dict] = None


class ImageProcessor:
    def __init__(self):
        self.task_prompts = {
            "公式": "提取公式",
            "文字": "提取文字",
            "人物": "描述这个人的着装，以及动作和周围的细节去进行推测这个人在做什么",
            "表格": "先理解表格，再将表格结构合理化提取",
            "实体物体": "详细描述这个图片，并且根据这个图片细节去做推测类型",
        }

    def classify_image(self, image_path):
        try:
            query = "这张图片属于哪种类型？是公式、文字、人物、表格还是实体物体（如器械或动物）？请只回答类型，不要其他描述。"

            result = self.get_image_description(image_path, query)

            result = result.replace('<|endoftext|>', '').strip()

            for key in self.task_prompts.keys():
                if key in result.lower():
                    return key
        except Exception:
            return "未知类型"

    def get_image_description(self, image_path, query):
        try:
            with open(image_path, "rb") as f:
                encoded_image = base64.b64encode(f.read())
            decoded_image_text = encoded_image.decode('utf-8')
            base64_data = f"data:image;base64,{decoded_image_text}"

            client = OpenAI(
                # 若没有配置环境变量，请用百炼API Key将下行替换为：api_key="sk-xxx",
                api_key=BAI_LIAN_API_KEY,
                base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
            )
            completion = client.chat.completions.create(
                model="qwen2.5-vl-7b-instruct",
                # 此处以qwen-vl-plus为例，可按需更换模型名称。模型列表：https://help.aliyun.com/zh/model-studio/getting-started/models
                messages=[
                    {
                        "role": "user", "content":
                        [
                            {"type": "text", "text": query},
                            {"type": "image_url", "image_url": base64_data}
                        ]
                    }
                ]
            )
            return completion.choices[0].message.content
        except Exception as e:
            import traceback
            msg = traceback.format_exc()
            print(f"error :{msg}")

    def process_image(self, image_path, image_type):
        query = self.task_prompts.get(image_type, "详细描述这个图片，并且根据这个图片细节去做推测类型，不需要任何图片信息以外的描述")
        result = self.get_image_description(image_path, query)
        result = result.replace('<|endoftext|>', '').strip()
        return result


async def process_markdown_and_images(md_file_path, image_folder_path, image_processor):
    with open(md_file_path, 'r', encoding='utf-8') as file:
        content = file.read()

    image_pattern = r'!\[(.*?)\]\((.*?)\)'
    images = re.findall(image_pattern, content)

    for alt, img_path in images:
        full_img_path = os.path.join(image_folder_path, os.path.basename(img_path))
        if os.path.exists(full_img_path):
            start_time = time.time()
            image_type = image_processor.classify_image(full_img_path)
            result = image_processor.process_image(full_img_path, image_type)
            processing_time = time.time() - start_time
            img_marker = f'![{alt}]({img_path})'
            replacement = f"Image Type: {image_type}\nResult:\n{result}\n\n{img_marker}\n"
            content = content.replace(img_marker, replacement)

            print(f"Processed {img_path} in {processing_time:.2f} seconds. ")
        else:
            print(f"Warning: Image not found: {full_img_path}")

    return content


async def process_tar_background4local_new(zip_filepath, callback_url, callback_body_template):
    from app import sendfile_callback
    OUTPUT_FOLDER = os.path.join(BASEDIR, "data/output")
    if not os.path.exists(OUTPUT_FOLDER):
        os.makedirs(OUTPUT_FOLDER, exist_ok=True)
    output_md_path = ""
    try:
        with tempfile.TemporaryDirectory() as temp_dir:
            tar_path = os.path.join(temp_dir, "content.tar")
            with open(zip_filepath, "rb") as f:
                zip_bytes = f.read()
            with open(tar_path, "wb") as tar_file:
                tar_file.write(zip_bytes)

            with tarfile.open(tar_path, "r") as tar:
                tar.extractall(path=temp_dir)

            image_processor = ImageProcessor()

            for file in os.listdir(temp_dir):
                if os.path.splitext(file)[-1] == ".md":
                    md_file = file
            md_file_path = os.path.join(temp_dir, md_file)
            image_folder_path = os.path.join(temp_dir, "images")
            if os.path.exists(md_file_path) and os.path.exists(image_folder_path):
                processed_content = await process_markdown_and_images(md_file_path, image_folder_path, image_processor)
            else:
                processed_content = f"Error: File not found"
            output_md_path = os.path.join(OUTPUT_FOLDER, md_file)
            with open(output_md_path, "w") as f:
                f.write(processed_content)
        await sendfile_callback(output_md_path, callback_url, callback_body_template)
    except Exception as e:
        print(f"Error in process_pdf: {str(e)}")
        msg = str(e)
        callback_body_template['procDesc'] = msg
        await sendfile_callback(output_md_path, callback_url, callback_body_template)
