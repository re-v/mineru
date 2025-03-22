# 华为910b 
## 通过Dockerfile构建后,将项目目录下的magic-pdf.template.json 替换为以下内容
```
{
    "bucket_info":{
        "bucket-name-1":["ak", "sk", "endpoint"],
        "bucket-name-2":["ak", "sk", "endpoint"]
    },
    "models-dir":"/root/.cache/modelscope/hub/models/opendatalab/PDF-Extract-Kit-1___0/models",
    "layoutreader-model-dir":"/root/.cache/modelscope/hub/models/ppaanngggg/layoutreader",
    "device-mode":"npu",
    "layout-config": {
        "model": "doclayout_yolo"
    },
    "formula-config": {
        "mfd_model": "yolo_v8_mfd",
        "mfr_model": "unimernet_small",
        "enable": true
    },
    "table-config": {
        "model": "rapid_table",
        "sub_model": "slanet_plus",
        "enable": true,
        "max_time": 400
    },
    "llm-aided-config": {
        "formula_aided": {
            "api_key": "your_api_key",
            "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
            "model": "qwen2.5-7b-instruct",
            "enable": false
        },
        "text_aided": {
            "api_key": "your_api_key",
            "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
            "model": "qwen2.5-7b-instruct",
            "enable": false
        },
        "title_aided": {
            "api_key": "your_api_key",
            "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
            "model": "qwen2.5-32b-instruct",
            "enable": false
        }
    },
    "config_version": "1.1.1"
}
```

#### 启动验证
```
docker run -d \
  --name mineru \
  --privileged \
  --network flyshare \
  --ip 192.19.0.22 \
  --device=/dev/davinci0 \
  --device=/dev/davinci1 \
  --device=/dev/davinci2 \
  --device=/dev/davinci3 \
  --device=/dev/davinci_manager \
  --device=/dev/devmm_svm \
  --device=/dev/hisi_hdc \
  -v /usr/local/Ascend:/usr/local/Ascend \
  -v /usr/local/dcmi:/usr/local/dcmi \
  -v /usr/local/bin/npu-smi:/usr/local/bin/npu-smi \
  -v /usr/local/Ascend/driver/lib64/common:/usr/local/Ascend/driver/lib64/common \
  -v /usr/local/Ascend/driver/lib64/driver:/usr/local/Ascend/driver/lib64/driver \
  -v /etc/ascend_install.info:/etc/ascend_install.info \
  -v /usr/local/Ascend/driver/version.info:/usr/local/Ascend/driver/version.info \
  -e TZ=Asia/Shanghai \
  -e PYTHONDONTWRITEBYTECODE=1 \
  -e PYTHONUNBUFFERED=1 \
  -e DOCKER=True \
  -e PATH=/root/miniforge3/bin:/root/miniforge3/condabin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:/usr/games:/usr/local/games:/snap/bin:$PATH \
  -e LD_LIBRARY_PATH=/usr/local/Ascend/driver/lib64:/usr/local/Ascend/driver/lib64/common:/usr/local/Ascend/driver/lib64/driver:$LD_LIBRARY_PATH \
  -p 8002:8000 \
  -v /home/data/flyshare/AI/models/minerU_model/paddleocr:/root/.paddleocr \
  -v /home/ds/mineru-v1.2:/work/MinerU \
  -v /home/ds/mineru-v1.2/magic-pdf.template.json:/root/magic-pdf.json \
  mineru:v0.0.1 \
  /bin/sh -c "sleep infinity"
  

启动后进入容器 
cd demo
python demo.py
```

# 华为 310P3
## 同上 暂时无法使用NPU加速 cpu耗时严重