"""
高级解析上游任务 解析策略模式穷举["normal","fast","hi_res"]
    - fast -> MinerU 服务直接回调langchain
        - 图片带表格处理(image_table)
            - 方法一: RapidTable RapidOCR 获取非公式、数学符号类表格
                - 通过json 校验图片类型
                - 速度快 单张/cpu 1s
                - 无法处理表格内的公式、数学符号
            - 方法二: 内置模型 StructEqTable
                - latex表格格式 速度慢 单张/cpu 100s
                    - 可尝试 Tensorrt-LLM加速
                - 可处理表格内的公式、数学符号
                - 在某些用例下 表格结构 优于多模态表格提取
    - hi_res -> 调用下游多模态任务
        - 输入 md + images => tar
        - 表格类图片
            - 多模态解析表格内容放置md图片标志之前
            - 其他类型图片都按照上述方式处理
"""
import asyncio
import json
import logging
import os
import tarfile
import time
from collections import deque
from typing import List, Optional

import aiohttp
import requests
from fastapi import FastAPI, HTTPException, BackgroundTasks, UploadFile, File, Form, Depends
from pydantic import BaseModel

from client.minio_client import MinioClient
from configs.config import BASEDIR, MULTI_MODEL_SERVER, CALLBACK_URL, ORACLE_CALLBACK_URL
from get_image_md5 import img_replace_into_md5
from magic_pdf.model.doc_analyze_by_custom_model import ModelSingleton
from magic_pdf_parse_main import pdf_parse_main

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
app = FastAPI()

task_queue = deque()  # 启用任务型异步队列
lock = asyncio.Lock()  # 启用异步队列锁


class FileInfo(BaseModel):
    file_id: str
    content_path: str  # 原路径
    target_path: str  # 目标路径*文件名
    content: str


class FileList(BaseModel):
    file_list: List[FileInfo]
    token: str
    strategy: str = "fast"  # 可能接收的解析模式
    callback_url: str  # 解析适配oracle_langchain环境回调


class ResponseModel(BaseModel):
    code: int
    msg: str
    data: Optional[dict] = None


async def process_queue():
    while True:
        async with lock:
            if task_queue:
                task = task_queue.popleft()
                await process_files_background(task['file_list_obj'], task['pdf_content'])
        await asyncio.sleep(1)  # 控制任务处理频率


@app.on_event("startup")
async def startup_event():
    # 在应用启动时，启动任务处理队列的协程
    asyncio.create_task(process_queue())


# @app.post("/pre_process_pdf", response_model=ResponseModel)
# async def analysis(
#         background_tasks: BackgroundTasks,
#         file: UploadFile = File(...),
#         file_list: str = Form(...)
# ):
#     file_list_data = eval(file_list)
#     file_list_data.update({"strategy": file_list_data.get("strategy", "fast")})
#     file_list_obj = FileList(**file_list_data)
#
#     if not validate_token(file_list_obj.token):
#         raise HTTPException(status_code=401, detail="Invalid token")
#
#     initial_response = ResponseModel(
#         code=200,
#         msg="success",
#         data={
#             "file_list": [{"status": "已接受文件，正在处理中........"}],
#             "token": file_list_obj.token
#         }
#     )
#
#     pdf_content = await file.read()
#     print(f"received: {file_list_obj.file_list[0].target_path}")
#
#     # async with lock:
#     task_queue.append({'file_list_obj': file_list_obj, 'pdf_content': pdf_content})
#
#     return initial_response

@app.post("/pre_process_pdf", response_model=ResponseModel)
async def analysis(
        background_tasks: BackgroundTasks,
        file: UploadFile = File(...),
        file_list: str = Form(...)
):
    """
    MinerU上游任务

    1, 获取待解析文件,解析得到md和images图片包
        - 存在图片,上传图片到minio
        - 不存在图片,直接返回md - 停止链路 - 异步回调langchain服务
    2, 存在图片,将md文件和images文件压缩传输到下游多模态服务 - suc - minerU流程停止 - 交由下游多模态服务回调
    Args:
        background_tasks:
        file:
        file_list:

    Returns:

    """
    # if lock.locked():
    #     raise HTTPException(status_code=400, detail="Server is busy, please try again later")
    try:
        file_list_data = json.loads(file_list)
        file_list_data.update({"strategy": file_list_data.get("strategy", "fast")})
        print(f"params:{file_list_data}")
        file_list_obj = FileList(**file_list_data)

        if not validate_token(file_list_obj.token):
            raise HTTPException(status_code=401, detail="Invalid token")

        initial_response = ResponseModel(
            code=200,
            msg="success",
            data={
                "file_list": [{"status": "已接受文件，正在处理中........"}],
                "token": file_list_obj.token
            }
        )

        pdf_content = await file.read()
        print(f"received: {file_list_obj.file_list[0].target_path}")
        # background_tasks.add_task(process_files_background, file_list_obj, pdf_content)
        # 添加至任务队列
        task_queue.append({'file_list_obj': file_list_obj, 'pdf_content': pdf_content})

        return initial_response
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON in file_list")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


async def write_pdf_stream_to_file(file_list: FileList, pdf_content: bytes):
    file_dir = os.path.join(BASEDIR, "data")
    if not os.path.exists(file_dir):
        os.makedirs(file_dir)
    file_name = os.path.basename(file_list.file_list[0].target_path)
    pdf_path = os.path.join(file_dir, file_name)
    with open(pdf_path, "wb") as f:
        f.write(pdf_content)
    return pdf_path


async def post_pdf_parse_main(file_info, pdf_path, token):
    """
    获取文件解析内容,写入content返回

    - 遍历images目录 如果存在图片则压缩文件 调用多模态处理
        - 如果不存在图片,则回调langchain
    Args:
        file_info: 文件信息
        pdf_path: 源文件路径
        token: token

    Returns:

    """
    result = ""
    exist_images = False
    current_token = Depends()
    current_token.credentials = token
    try:
        pdf_name = os.path.basename(pdf_path).split(".")[0]
        pdf_path_parent = os.path.dirname(pdf_path)

        output_path = os.path.join(pdf_path_parent, pdf_name)

        output_image_path = os.path.join(output_path, 'images')

        md_path = os.path.join(output_path, f"{pdf_name}.md")

        with open(md_path, "r", encoding="utf-8") as f:
            result = f.read()
        if not os.path.exists(output_image_path):
            print(f"images不包含图片")
        else:
            # 先验图片存在
            exist_images = True
            if exist_images:
                result = img_replace_into_md5(md_path, output_image_path)
                with open(md_path, "w", encoding="utf-8") as f:
                    f.write(result)
            # 将output_image_path 所有图片传入minio
            try:
                for image in os.listdir(output_image_path):
                    image_local_path = os.path.join(output_image_path, image)
                    image_full_path = os.path.join(pdf_name, 'images', image)
                    # MinioClient.get_instance().upload_local_file(image_local_path, image_full_path)
                    # await MinioClient.get_instance().upload_file_main(file_info.file_id, image_local_path,
                    #                                                   "images", current_token)
                    await MinioClient.get_instance().upload_local_file_with_java(file_info.file_id, image_local_path,
                                                                                 "images", current_token)

                    logging.info(f"minio 文件写入成功:{image_full_path}")

            except Exception as e:
                logging.error(f"minio 文件写入失败:{str(e)}")

    except Exception as e:
        print(f"Error in post_pdf_parse_main: {str(e)}")
    file_info.content = result
    return file_info, exist_images


async def process_files_background(file_list: FileList, pdf_content: bytes):
    callback_data = dict()
    exist_images = False
    pdf_path = ""
    try:
        processed_files = []
        for file_info in file_list.file_list:
            print(f"process: {file_info.target_path}")
            pdf_path = await write_pdf_stream_to_file(file_list, pdf_content)
            # pdf_parse_main(pdf_path)  # 同步阻塞
            # time.sleep(2)
            # 同步阻塞开销线程执行
            await asyncio.to_thread(pdf_parse_main, pdf_path)
            # await asyncio.to_thread(time.sleep, 3)
            print(f"finish process: {file_info.target_path}")
            processed_file, exist_images = await post_pdf_parse_main(file_info, pdf_path, file_list.token)
            processed_files.append(processed_file)
        callback_data = {
            "code": 200,
            "msg": "success",
            "data": {
                "file_list": [file.dict() for file in processed_files],
                "token": file_list.token
            }
        }
    except Exception as e:
        print(f"Error in background processing: {str(e)}")
        error_params = {
            "file_list": [file.dict() for file in file_list.file_list],
            "token": file_list.token
        }
        print(f"错误回调参数:{error_params}")
        callback_data = {
            "code": 500,
            "msg": f"Error: {str(e)}",
            "data": {
                "file_list": [file.dict() for file in file_list.file_list],
                "token": file_list.token
            }
        }
    finally:
        callback_data.update({"callback_url": file_list.callback_url})
        if file_list.strategy == "fast":
            # directly_back 如果fast模式 此处不考虑图片描述信息 直接回调langchain
            await send_callback(callback_data)
        else:
            # 判断是否存在图片 - 不存在 -> 直接回调langchain - 存在 -> 调用下游多模态服务
            if not exist_images:
                await send_callback(callback_data)
            # call multi_model
            else:
                await call_multi_model(file_list, pdf_path)


def compress_files(output_path: str, file_name: str) -> str:
    tar_filepath = os.path.join(output_path, f"{file_name}.tar.gz")
    with tarfile.open(tar_filepath, 'w:gz') as tar:
        for root, dirs, files in os.walk(output_path):
            for file in files:
                if file.endswith(".md") or root.endswith("images"):
                    file_path = os.path.join(root, file)
                    tar.add(file_path, arcname=os.path.relpath(file_path, output_path))
    return tar_filepath


async def call_multi_model(file_list: FileList, pdf_path: str):
    pdf_name = os.path.basename(pdf_path).split(".")[0]
    pdf_path_parent = os.path.dirname(pdf_path)

    output_path = os.path.join(pdf_path_parent, pdf_name)

    # 压缩output_path 路径下的md文件,images图片包 stream传输
    zip_filepath = compress_files(output_path, pdf_name)

    url = MULTI_MODEL_SERVER["host_port"] + "/image2md"
    payload = {"file_list": [file.dict() for file in file_list.file_list], "token": file_list.token,
               "callback_url": file_list.callback_url}

    try:
        async with aiohttp.ClientSession() as session:
            with open(zip_filepath, 'rb') as file:
                form_data = aiohttp.FormData()
                form_data.add_field('file', file, filename=pdf_name, content_type='application/pdf')
                form_data.add_field('file_list', json.dumps(payload))

                async with session.post(url, data=form_data) as response:
                    if response.status == 200:
                        logging.info("请求成功")
                    else:
                        logging.error(f"请求失败，状态码: {response.status}")
    except Exception as e:
        logging.error(f"请求过程中出错: {str(e)}")


async def sync_call_multi_model(file_list: FileList, pdf_path: str):
    pdf_name = os.path.basename(pdf_path).split(".")[0]
    pdf_path_parent = os.path.dirname(pdf_path)

    output_path = os.path.join(pdf_path_parent, pdf_name)

    # 压缩output_path 路径下的md文件,images图片包 stream传输
    zip_filepath = compress_files(output_path, pdf_name)

    url = MULTI_MODEL_SERVER["host_port"] + "/image2md"
    payload = {"file_list": [file.dict() for file in file_list.file_list], "token": file_list.token}
    import json
    body = {"file_list": json.dumps(payload)}

    try:
        with open(zip_filepath, 'rb') as file:
            files = {
                'file': (pdf_name, file, 'application/pdf'),
            }
            response = requests.request("POST", url, data=body, files=files)
    except Exception as e:
        import traceback
        msg = traceback.format_exc()
        logging.error(msg)


async def send_callback(data: dict) -> None:
    callback_url = data.pop("callback_url")
    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(callback_url, json=data) as response:
                if response.status == 200:
                    print("Callback sent successfully")
                else:
                    print(f"Failed to send callback. Status: {response.status}")
        except Exception as e:
            print(f"Error sending callback: {str(e)}")


def validate_token(token: str) -> bool:
    # 这里应该实现实际的token验证逻辑
    return True  # 暂时总是返回True


model_manager = ModelSingleton()  # 在服务启动时加载模型
custom_model = model_manager.get_model(False, False)

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
