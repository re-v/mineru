import json
import os
from typing import List, Optional
import aiohttp
import aiohttp
import requests
import logging
from fastapi import FastAPI, HTTPException, BackgroundTasks, UploadFile, File, Form
from pydantic import BaseModel

from magic_pdf_parse_main import PDFParser
from magic_pdf.model.doc_analyze_by_custom_model import ModelSingleton

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
pdf_parser = PDFParser()
app = FastAPI()

MODEL_PATH = "/app/model/glm-4v-9b-4-bits"
CALLBACK_URL = "http://192.168.110.125:7861/api/v2/analysis_callback"
BASEDIR = os.path.abspath(os.path.dirname(__file__))  # 项目目录


# CALLBACK_URL = "http://langchain.wsb360.com:7861/api/v2/analysis_callback"


class FileInfo(BaseModel):
    file_id: str
    content_path: str  # 原路径
    target_path: str  # 目标路径*文件名
    content: str


class FileList(BaseModel):
    file_list: List[FileInfo]
    token: str
    strategy: str = "fast"  # 可能接收的解析模式


class ResponseModel(BaseModel):
    code: int
    msg: str
    data: Optional[dict] = None


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
    try:
        file_list_data = eval(file_list)
        file_list_data.update({"strategy": file_list_data.get("strategy", "fast")})
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
        background_tasks.add_task(process_files_background, file_list_obj, pdf_content)

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
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(None, lambda: open(pdf_path, "wb").write(pdf_content))
    return pdf_path


async def post_pdf_parse_main(file_info, pdf_path):
    """
    获取文件解析内容,写入content返回
    - 遍历images目录 如果存在图片则压缩文件 调用多模态处理
        - 如果不存在图片,则回调langchain
    Args:
        file_info: 文件信息
        pdf_path: 源文件路径

    Returns:

    """
    result = ""
    exist_images = False
    try:
        pdf_parser.parse_pdf(pdf_path) #调用全局的 pdf_parser
        pdf_name = os.path.basename(pdf_path).split(".")[0]
        pdf_path_parent = os.path.dirname(pdf_path)

        output_path = os.path.join(pdf_path_parent, pdf_name)

        output_image_path = os.path.join(output_path, 'images')
        if os.listdir(output_image_path):
            exist_images = True

        md_path = os.path.join(output_path, f"{pdf_name}.md")
        with open(md_path, "r", encoding="utf-8") as f:
            result = f.read()
            print(result)
        # 如果路径中存在图片 则1,向minio传入文件 2,调用多模态服务
    except Exception as e:
        print(f"Error in post_pdf_parse_main: {str(e)}")
    file_info.content = result
    return file_info, exist_images


async def process_files_background(file_list: FileList, pdf_content: bytes):
    callback_data = dict()
    exist_images = False
    try:
        processed_files = []
        for file_info in file_list.file_list:
            pdf_path = await write_pdf_stream_to_file(file_list, pdf_content)
            # pdf_parse_main(pdf_path)  # 同步阻塞
            processed_file, exist_images = await post_pdf_parse_main(file_info, pdf_path)
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
        callback_data = {
            "code": 500,
            "msg": f"Error: {str(e)}",
            "data": {
                "file_list": [file.dict() for file in file_list.file_list],
                "token": file_list.token
            }
        }
    finally:
        if file_list.strategy == "fast":
            # directly_back 如果fast模式 此处不考虑图片描述信息 直接回调langchain
            await send_callback(callback_data)
        else:
            # 判断是否存在图片 - 不存在 -> 直接回调langchain - 存在 -> 调用下游多模态服务
            if not exist_images:
                await send_callback(callback_data)
            # call multi_model
            else:
                pass


async def call_multi_model(file_list: FileList):

    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(url, data=body, files=files) as response:
                if response.status == 200:
                    result = await response.text()
                else:
                    result = ""
        except Exception as e:
            import traceback
            msg = traceback.format_exc()
            logging.error(msg)
    return result

async def send_callback(data: dict) -> None:
    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(CALLBACK_URL, json=data) as response:
                if response.status == 200:
                    print("Callback sent successfully")
                else:
                    print(f"Failed to send callback. Status: {response.status}")
        except Exception as e:
            print(f"Error sending callback: {str(e)}")


def validate_token(token: str) -> bool:
    # 这里应该实现实际的token验证逻辑
    return True  # 暂时总是返回True


if __name__ == "__main__":
    import uvicorn

    model_manager = ModelSingleton()  # 在服务启动时加载模型
    uvicorn.run(app, host="0.0.0.0", port=8000)
