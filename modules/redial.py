import os
import time
import subprocess
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import modules.data_sync as sync
from modules.logger import logging

"""
这是一个提供客户重拨的接口模块
通过在docker容器内向共享目录中写入需要重启的接口信息，宿主机会实时监听读取该文件，并重启对应的接口，重拨的操作日志同时会记录redial.log中。
redial.info

/opt/tools/redial/redial.info



我想从这个/opt/tools/redial/redial.info文件中读取一些信息，信息格式为ppp+数字，如ppp1或者ppp100，请用Python来实现
"""


def check_path(directory_path="/opt/tools/redial/"):
    file_path = os.path.join(directory_path, "redial.info")

    if not os.path.exists(file_path):
        if not os.path.exists(directory_path):
            try:
                os.makedirs(directory_path)
            except OSError as e:
                logging.error(f"Error creating directory or file: {e}")
        else:
            with open(file_path, 'w') as file:
                file.write("## This is the redial.info file. You can write the ifname you want to redial here.")
    return file_path


class FileChangeHandler(FileSystemEventHandler):
    """处理文件改变的类"""
    def __init__(self, filename):
        self.filename = filename
        self.last_modified = time.time()

    def on_modified(self, event):
        """文件改变时触发"""
        if not event.is_directory and event.src_path == self.filename:
            # 避免多次触发时间，检查时间戳
            now = time.time()
            if now - self.last_modified < 0.1:
                return
            self.last_modified = now
            logging.info(f"File {self.filename} has been modified. Restarting...")
            with open(self.filename, 'r') as f:
                content = f.read()
                import re
                matches = re.findall(r'ppp\d+', content)
                for match in matches:
                    logging.info(f"{match}")
                if matches is None:
                    if content == "all":
                        logging.info("all")
                    else:
                        logging.info("none")

def monitor_file(filename):
    event_handler = FileChangeHandler(filename)
    observer = Observer()
    observer.schedule(event_handler, path=os.path.dirname(filename), recursive=False)
    observer.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()

if __name__ == "__main__":
    file_path = check_path()
    monitor_file(file_path)  # 替换为你要监控的文件路径


# monitor_coustomer_redial_requests


