# import os
# import logging
# from logging.handlers import TimedRotatingFileHandler
#
# # 配置日志以方便维护
# log_directory = 'log'
# if not os.path.exists(log_directory):
#     os.makedirs(log_directory)
# log_file_path = os.path.join(log_directory, '../log/auto_pcdn.log')
# logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
# file_handler = TimedRotatingFileHandler(filename=log_file_path, when='midnight', interval=1, backupCount=30)  # 日志文件按天滚动，保留时长为30天
# file_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
# logging.getLogger().addHandler(file_handler)  # 将Handler添加到Logger中


import os
import logging
from logging.handlers import TimedRotatingFileHandler
from colorlog import ColoredFormatter  # 导入ColoredFormatter

log_directory = 'log'
if not os.path.exists(log_directory):
    os.makedirs(log_directory)
log_file_path = os.path.join(log_directory, '../log/auto_pcdn.log')

# 配置控制台输出的日志格式和颜色
console_formatter = ColoredFormatter(
    "%(log_color)s%(asctime)s - %(levelname)s - %(message)s",
    datefmt='%Y-%m-%d %H:%M:%S',
    log_colors={
        'INFO': 'green',
        'ERROR': 'red',
        'WARNING': 'yellow',
        'CRITICAL': 'bold_red',
    }
)

# 配置文件输出的日志格式
file_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')

# 创建并配置日志记录器
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# 创建并配置控制台处理程序
console_handler = logging.StreamHandler()
console_handler.setFormatter(console_formatter)
logger.addHandler(console_handler)

# 创建并配置文件处理程序
file_handler = TimedRotatingFileHandler(filename=log_file_path, when='midnight', interval=1, backupCount=30)
file_handler.setFormatter(file_formatter)
logger.addHandler(file_handler)
