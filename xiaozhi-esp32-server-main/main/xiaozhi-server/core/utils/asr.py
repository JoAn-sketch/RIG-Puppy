import importlib
import logging
import os
import sys
import time
import wave
import uuid
from abc import ABC, abstractmethod
from typing import Optional, Tuple, List
from core.providers.asr.base import ASRProviderBase
from config.logger import setup_logging

TAG = __name__
logger = setup_logging()

def create_instance(class_name: str, *args, **kwargs) -> ASRProviderBase:
    """工厂方法创建ASR实例"""
    if os.path.exists(os.path.join('core', 'providers', 'asr', f'{class_name}.py')):
        lib_name = f'core.providers.asr.{class_name}'
        # Let Python's import machinery serialize concurrent imports.  Assigning
        # the result to sys.modules before importlib finishes exposes a partially
        # initialized module to another connection.
        module = importlib.import_module(lib_name)
        return module.ASRProvider(*args, **kwargs)

    raise ValueError(f"不支持的ASR类型: {class_name}，请检查该配置的type是否设置正确")
