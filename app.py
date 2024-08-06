import json
from typing import List, Optional

import aiohttp
from fastapi import FastAPI, HTTPException, BackgroundTasks, UploadFile, File, Form
from pydantic import BaseModel

from magic_pdf.model.doc_analyze_by_custom_model import ModelSingleton

app = FastAPI()

MODEL_PATH = "/app/model/glm-4v-9b-4-bits"
CALLBACK_URL = "http://192.168.110.125:7861/api/v2/analysis_callback"


# CALLBACK_URL = "http://langchain.wsb360.com:7861/api/v2/analysis_callback"


class FileInfo(BaseModel):
    file_id: str
    content_path: str
    target_path: str
    content: str


class FileList(BaseModel):
    file_list: List[FileInfo]
    token: str


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


async def process_files_background(file_list: FileList, pdf_content: bytes):
    try:
        processed_files = []
        # for file_info in file_list.file_list:
        #     processed_file = pdf_parse_main(pdf_path)
        # processed_file = await process_pdf(file_info, pdf_content)
        # processed_files.append(processed_file)

        callback_data = {
            "code": 200,
            "msg": "success",
            "data": {
                "file_list": [file.dict() for file in processed_files],
                "token": file_list.token
            }
        }

        await send_callback(callback_data)
    except Exception as e:
        print(f"Error in background processing: {str(e)}")
        error_data = {
            "code": 500,
            "msg": f"Error: {str(e)}",
            "data": {
                "file_list": [file.dict() for file in file_list.file_list],
                "token": file_list.token
            }
        }
        await send_callback(error_data)


async def send_callback(data: dict):
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
