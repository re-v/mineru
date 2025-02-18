#!/usr/bin/env python
# -*- coding: UTF-8 -*-
'''
@Project ：MinerU 
@File    ：model_service.py
@IDE     ：PyCharm 
@Author  ：wgl
@Date    ：2025/2/18 10:14 
'''
import asyncio
import gc
import signal
import torch

from magic_pdf.model.doc_analyze_by_custom_model import ModelSingleton


class ModelService:
    """管理模型的生命周期，包括初始化和重新加载"""

    def __init__(self):
        self.model_manager = None
        self.custom_model = None
        self.load_model()  # 在服务启动时加载模型

    def load_model(self):
        """加载或重新加载模型"""
        print("🟢 加载模型...")
        if self.model_manager:
            # del self.model_manager  # 删除旧模型
            self.clean_memory()
            # gc.collect()
            # torch.cuda.empty_cache()  # 释放显存
            # torch.cuda.synchronize()
            self.model_manager.reload_model(False, False)
        else:
            self.model_manager = ModelSingleton()
            self.custom_model = self.model_manager.get_model(False, False)
        print("✅ 模型加载完成！")

    async def listen_for_reload(self):
        """监听信号，收到信号后重新加载模型"""
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGUSR1, signal.SIGTERM):
            loop.add_signal_handler(sig, lambda: asyncio.create_task(self.handle_reload()))

    async def handle_reload(self):
        """处理模型重启信号"""
        print("⚠️  收到重启信号，正在重新加载模型...")
        self.load_model()
        print("🔄 模型重新加载成功！")

    def clean_memory(self):
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
            torch.cuda.ipc_collect()
        gc.collect()

