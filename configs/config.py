#!/usr/bin/env python
# -*- coding: UTF-8 -*-
import os

BASEDIR = os.path.dirname(os.path.abspath(os.path.dirname(__file__)))  # 项目目录

# MULTI_MODEL_SERVER = {
#     "host_port": "http://localhost:8001"
# }
MULTI_MODEL_SERVER = {
    "host_port": "http://fs-doc-analysis:8000"
}
CALLBACK_URL = "http://langchain.wsb360.com:7861/api/v2/analysis_callback"
FILE_SERVER = {
    "host_port": "http://develop.wsb360.com:18889/ai-api"
}
try:
    from local_config import CALLBACK_URL, MULTI_MODEL_SERVER, FILE_SERVER
except Exception as e:
    pass

MINIO_CONFIG = {
    "endpoint": '39.99.153.50:9000',
    "access_key": 'admin',
    "secret_key": 'AZsx1234Vchat',
    "secure": False,
    "bucket": 'aichat',
    "bucket_prefix": 'MinerU'
}