from fastapi import UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import pydantic
from typing import Any
from minio import Minio

MINIO_CONFIG = {
    "endpoint": '39.99.153.50:9000',
    "access_key": 'admin',
    "secret_key": 'AZsx1234Vchat',
    "secure": False,
    "bucket": 'aichat',
    "bucket_prefix": 'MinerU'
}

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
