#!/usr/bin/env python
# -*- coding: UTF-8 -*-
'''
@Project ：MinerU 
@File    ：model_service.py
@IDE     ：PyCharm 
@Author  ：wgl
@Date    ：2025/2/18 10:14 
'''
import gc
import time
from multiprocessing import Process

import torch

from magic_pdf.model.doc_analyze_by_custom_model import ModelSingleton


class ModelService:
    def __init__(self):
        self.model_manager = None
        self.custom_model = None

    def load_model(self):
        """Load or reload the model."""
        print("🟢 Loading model...")
        if not self.model_manager:
            self.model_manager = ModelSingleton()
            self.custom_model = self.model_manager.get_model(False, False)
        print("✅ Model loaded successfully!")

    def clean_memory(self):
        """Clean GPU memory and perform garbage collection."""
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
            torch.cuda.ipc_collect()
        gc.collect()

    def restart_model(self):
        """Attempt to reload the model, return success/failure."""
        try:
            self.clean_memory()
            self.load_model()
        except Exception as e:
            print(f"⚠️ Model reload failed: {e}")
            return False
        return True


def model_reload_process(stop_event, input_queue):
    """Child process responsible for model loading and reloading."""
    model_service = ModelService()
    model_service.load_model()   # 初始加载模型
    try:
        while not stop_event.is_set():
            # 处理队列任务
            if not input_queue.empty():
                from app import sync_process_queue
                sync_process_queue(stop_event, input_queue)
            time.sleep(1)  # Sleep to avoid busy-waiting
    except Exception as e:
        pass


def monitor_process(stop_event, input_queue):
    """Monitor process responsible for managing child processes."""
    while True:
        p = Process(target=model_reload_process, args=(stop_event, input_queue))
        p.start()
        p.join()  # Wait for the child process to exit
        print("Child process exited, restarting...")
        time.sleep(2)  # Delay before restarting
