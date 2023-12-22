import subprocess
import logging
import time

def pppoe_dial_up(pppoe_ifname, pppoe_user):
    try:
        logging.info(f"{pppoe_ifname}({pppoe_user}) 开始拨号...")
        command = f"pppoe-connect /etc/sysconfig/network-scripts/ifcfg-{pppoe_ifname} &"
        # 创建子进程
        result = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True, universal_newlines=True)
        # 分离子进程（避免关闭父进程后子进程随之退出）
        success_flag = "succeeded"
        timeout = time.time() + 10
        while time.time() < timeout:
            output = result.stdout.readline()
            if success_flag in output:
                logging.info(f"{pppoe_ifname}({pppoe_user}) 拨号成功！")
                break
        if time.time() >= timeout:
            logging.error(f"{pppoe_ifname}({pppoe_user}) 拨号超时！")
    except subprocess.CalledProcessError as e:
        logging.error(f"{pppoe_ifname} 拨号出错：{e}")

