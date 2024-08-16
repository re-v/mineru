FROM mineru:v0.0.1

WORKDIR /work/MinerU

ADD requirements.txt .

RUN pip3 install detectron2 --extra-index-url https://wheels.myhloli.com -i https://pypi.tuna.tsinghua.edu.cn/simple
RUN pip3 install magic-pdf[full]==0.6.2b1 -i https://pypi.tuna.tsinghua.edu.cn/simple

EXPOSE 8000
# 设置启动命令
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
