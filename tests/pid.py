import os
import signal
import subprocess
import sys
import time
import logging



def write_pid():
    pid_file = "/run/AutoPCDN.pid"
    pid = os.getpid()
    with open(pid_file, "w") as f:
        f.write(str(pid))

def handle_signal(signum, frame):
    print(f"Received signal {signum}. Shutting down gracefully.")
    sys.exit(0)

signal.signal(signal.SIGTERM, handle_signal)
signal.signal(signal.SIGINT, handle_signal)

def pppoe_dial_up(pppoe_ifname, pppoe_user):
    try:
        logging.info(f"{pppoe_ifname}({pppoe_user}) 开始拨号...")
        command = f"pppoe-connect /etc/sysconfig/network-scripts/ifcfg-{pppoe_ifname} &"
        # 创建子进程
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True, universal_newlines=True)
        # 分离子进程（避免关闭父进程后子进程随之退出）
        process.detach()
        success_flag = "succeeded"
        timeout = time.time() + 10
        while time.time() < timeout:
            output = process.stdout.readline()
            if success_flag in output:
                logging.info(f"{pppoe_ifname}({pppoe_user}) 拨号成功！")
                break
        if time.time() >= timeout:
            logging.error(f"{pppoe_ifname}({pppoe_user}) 拨号超时！")
    except subprocess.CalledProcessError as e:
        logging.error(f"{pppoe_ifname} 拨号出错：{e}")

def main():
    write_pid()

    # 启动子进程
    pppoe_dial_up("your_pppoe_ifname", "your_pppoe_user")

    try:
        while True:
            # 主程序循环，可以根据需要执行其他操作
            time.sleep(1)
    except KeyboardInterrupt:
        handle_signal(signal.SIGINT, None)

if __name__ == "__main__":
    main()
