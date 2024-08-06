FROM nvidia/cuda:12.1.1-cudnn8-devel-ubuntu22.04

# 设置字符集
ENV LANG en_US.UTF-8
# 时区设置
RUN ln -sf /usr/share/zoneinfo/Asia/Shanghai /etc/localtime && echo 'Asia/Shanghai' >/etc/timezone
#RUN tail -f /etc/apt/sources.list
# 设置源
RUN sed -i "s/archive.ubuntu.com/mirrors.tuna.tsinghua.edu.cn/g" /etc/apt/sources.list
RUN sed -i "s/security.ubuntu.com/mirrors.tuna.tsinghua.edu.cn/g" /etc/apt/sources.list
WORKDIR /work/MinerU
# 添加文件
ADD requirements.txt .

# 安装系统依赖
RUN apt-get update
RUN apt-get install -y --no-install-recommends \
    python3.11 \
    python3-pip \
    curl \
    libgl1 \
    libglib2.0-0 \
    jq \
    build-essential \
    libjpeg-dev \
    zlib1g-dev \
    git \
    libcairo2 \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libgdk-pixbuf2.0-0 \
    libffi-dev \
    shared-mime-info && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/* && \
    rm -f /usr/bin/python3 && \
    ln -s /usr/bin/python3.11 /usr/bin/python3

# 安装python依赖
RUN pip3 install --upgrade pip -i https://pypi.tuna.tsinghua.edu.cn/simple
RUN pip3 install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

EXPOSE 8000
# 设置启动命令
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
