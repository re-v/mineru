#!/bin/bash
# 容器内加密保证python运行时版本一致
pip install pyarmor -i https://pypi.tuna.tsinghua.edu.cn/simple
# 加密 Python 文件
#pyarmor gen --platform linux.x86_64 -O ../dist -r .
pyarmor gen --exclude "./venv" --platform linux.aarch64 -O ../dist -r .
# 复制非 Python 文件
rsync -a --exclude '*.py' . ../dist/