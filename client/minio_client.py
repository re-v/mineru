import asyncio
import os

import aiohttp
from fastapi import UploadFile, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import pydantic
from typing import Any
from minio import Minio

from configs.config import MINIO_CONFIG, FILE_SERVER
from logger import code_log


class BaseResponse(BaseModel):
    code: int = pydantic.Field(200, description="API status code")
    msg: str = pydantic.Field("success", description="API status message")
    data: Any = pydantic.Field(None, description="API data")

    class Config:
        schema_extra = {
            "example": {
                "code": 200,
                "msg": "success",
            }
        }


def __get_real_object_name__(object_name):
    if MINIO_CONFIG['bucket_prefix']:
        return f"{MINIO_CONFIG['bucket_prefix']}/{object_name}"
    else:
        return object_name


class MinioClient:
    def __init__(self):
        if not hasattr(MinioClient, "_first_init"):
            MinioClient._first_init = True
            self.client = Minio(
                endpoint=MINIO_CONFIG['endpoint'],
                access_key=MINIO_CONFIG['access_key'],
                secret_key=MINIO_CONFIG['secret_key'],
                secure=MINIO_CONFIG['secure']
            )
            if not self.client.bucket_exists(MINIO_CONFIG['bucket']):
                self.client.make_bucket(MINIO_CONFIG['bucket'])

    def __new__(cls, *args, **kwargs):
        if not hasattr(MinioClient, "_instance"):
            MinioClient._instance = object.__new__(cls)
        return MinioClient._instance

    @classmethod
    def get_instance(cls, *args, **kwargs):
        return MinioClient()

    def upload_file(self, file: UploadFile, object_name: str):
        return self.client.put_object(MINIO_CONFIG['bucket'], __get_real_object_name__(object_name), file.file,
                                      file.size)

    async def upload_local_file_with_java(self, file_id: None, file_path: str, upload_type: str,
                                          current_token: str = Depends()):
        # 调用java服务上传文件
        asyncio.create_task(MinioClient.get_instance().upload_file_main(file_id, file_path, upload_type, current_token))
        # await MinioClient.get_instance().upload_file_main(file_id, file_path, upload_type, current_token)

    async def upload_file_main(self, file_id: str, file_path: str, upload_type: str, current_token):
        """

        Parameters
        ----------
        file_id
        file_path
        upload_type
        current_token

        Returns
        -------

        """
        server_url = FILE_SERVER["host_port"]
        file_name = os.path.basename(file_path)
        if upload_type == "analysis":
            url = server_url + "/ai/knowledge/file/saveResolveFile"
            try:
                async with aiohttp.ClientSession() as session:
                    with open(file_path, 'rb') as file:
                        form_data = aiohttp.FormData()
                        form_data.add_field('file', file, filename=file_name)
                        form_data.add_field('fileId', file_id)
                        headers = {"Authorization": "Bearer " + current_token.credentials}
                        async with session.post(url, data=form_data, headers=headers) as response:
                            if response.status == 200:
                                code_log.info("请求成功")
                            else:
                                code_log.error(f"请求失败，状态码: {response.status}")
            except Exception as e:
                code_log.error(f"请求过程中出错: {str(e)}")
        elif upload_type == "slice":
            url = server_url + "/ai/knowledge/file/saveFileChunk"
            try:
                async with aiohttp.ClientSession() as session:
                    with open(file_path, 'rb') as file:
                        form_data = aiohttp.FormData()
                        form_data.add_field('file', file, filename=file_name)
                        form_data.add_field('fileId', file_id)

                        headers = {"Authorization": "Bearer " + current_token.credentials}
                        async with session.post(url, data=form_data, headers=headers) as response:
                            if response.status == 200:
                                code_log.info("请求成功")
                            else:
                                code_log.error(f"请求失败，状态码: {response.status}")
            except Exception as e:
                code_log.error(f"请求过程中出错: {str(e)}")
        else:
            # images
            url = server_url + "/ai/knowledge/file/saveResolveImages"
            try:
                async with aiohttp.ClientSession() as session:
                    with open(file_path, 'rb') as file:
                        form_data = aiohttp.FormData()
                        form_data.add_field('images', file, filename=file_name)

                        headers = {"Authorization": "Bearer " + current_token.credentials}
                        async with session.post(url, data=form_data, headers=headers) as response:
                            if response.status == 200:
                                code_log.info("请求成功")
                            else:
                                code_log.error(f"请求失败，状态码: {response.status}")
            except Exception as e:
                code_log.error(f"请求过程中出错: {str(e)}")

    def upload_local_file(self, file_path: str, object_name: str, content_type: str = "application/octet-stream"):
        return self.client.fput_object(MINIO_CONFIG['bucket'], __get_real_object_name__(object_name), file_path,
                                       content_type)

    def download_file(self, object_name):
        minio_response = None
        try:
            minio_response = self.client.get_object(MINIO_CONFIG['bucket'], __get_real_object_name__(object_name))
            response = StreamingResponse(minio_response.stream(32 * 1024),
                                         media_type=minio_response.headers.get("content-type"))
            header_keys = ("Accept-Ranges", "Content-Range", "Content-Length", "Last-Modified", "ETag")
            for key in header_keys:
                response.headers.update({key: minio_response.headers.get(key)})
            return response
        finally:
            minio_response.close()
            minio_response.release_conn()
            return BaseResponse(code=500, msg=f"文件下载失败")

    def download_local_file(self, object_name: str, file_path: str):
        self.client.fget_object(MINIO_CONFIG['bucket'], __get_real_object_name__(object_name), file_path)

    def delete_file(self, object_name):
        self.client.remove_object(MINIO_CONFIG['bucket'], __get_real_object_name__(object_name))
