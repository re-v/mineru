# coding=utf-8

"""
程序运行日志记录
"""

import logging
import os
import platform

if str(platform.system()) == "Windows":
    from logging.handlers import RotatingFileHandler as LogHandler
else:
    # base: https://github.com/Preston-Landers/concurrent-log-handler
    from concurrent_log_handler import ConcurrentRotatingFileHandler as LogHandler

_log_file_size = 1 * 1024 * 1024 * 1024  # 1G
# todo 日志与项目目录同级
# _log_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "logs")
# todo 日志与文件同级
_log_path = os.path.join(os.path.dirname(__file__),"logs")
if not os.path.exists(_log_path):
    os.mkdir(_log_path)

# -------------------------------运行日志（代码运行记录）-------------------------------
_code_log_file = os.path.join(_log_path, 'code.log')
_code_log_handler = LogHandler(_code_log_file, "a", _log_file_size, 1000, encoding='utf-8')
_code_log_formatter = logging.Formatter('%(levelname)s %(asctime)s %(pathname)s %(funcName)s '
                                        'line:%(lineno)d %(message)s')
_code_log_handler.setFormatter(_code_log_formatter)


class LogLevelFilter(logging.Filter):
    def __init__(self, name='', level=logging.DEBUG):
        super(LogLevelFilter, self).__init__(name)
        self.level = level

    def filter(self, record):
        return record.levelno >= self.level


# 控制台日志
stream_handler = logging.StreamHandler()
stream_handler.setLevel(logging.DEBUG)
stream_handler.addFilter(LogLevelFilter(level=logging.DEBUG))
stream_handler.setFormatter(_code_log_formatter)

# 此处设置logger名称，否则默认的会和tornado的logger相同而使得下方设置的错误等级被更新为info
code_log = logging.getLogger('code-log')
code_log.setLevel(logging.DEBUG)
code_log.addHandler(_code_log_handler)
code_log.addHandler(stream_handler)

# -------------------------------访问日志（记录访问的url和body）----------------------------------------
_access_log_file = os.path.join(_log_path, 'access.log')
_access_log_handler = LogHandler(_access_log_file, "a", _log_file_size, 1000, encoding='utf-8')
_access_log_formatter = logging.Formatter('%(asctime)s:%(message)s')
_access_log_handler.setFormatter(_access_log_formatter)
_access_log = logging.getLogger('access-log')
_access_log.setLevel(logging.INFO)
_access_log.addHandler(_access_log_handler)
