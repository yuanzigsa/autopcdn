# Time : 2023/12/08
# Author : yuanzi
import re
import os
import sys
import json
import time
import fcntl
import shlex
import struct
import socket
import logging
import requests
import datetime
import threading
import subprocess
import concurrent.futures
from pysnmp.hlapi import *
from datetime import datetime
from collections import Counter
from logging.handlers import TimedRotatingFileHandler

# 控制节点基础信息获取与推送的API接口
get_pppoe_basicinfo_api_url = "http://122.191.108.42:9119/orion/expose-api/machine-info/get-config"
update_pppline_api_url = "http://122.191.108.42:9119/orion/expose-api/machine-info/update-pppline"
update_dial_connect_api_url = "http://122.191.108.42:9119/orion/expose-api/machine-info/update-dial-connect"
update_pppline_monitor_info_api_url = "http://122.191.108.42:9119/orion/expose-api/machine-monitor/upload-pppline-monitor-info"
question_headers = {"O-Login-Token": "accessToken", "accessToken": "ops_access"}
script_path = "/opt/auto_pppoe"
machineTag = open(os.path.join(script_path, 'machineTag.info'), 'r').read().replace('\n', '')

# 配置日志以方便维护
# logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
# file_handler = logging.FileHandler('auto_pppoe.log')
# file_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
# logging.getLogger().addHandler(file_handler)

# 配置日志以方便维护
log_directory = '/opt/auto_pppoe/log'
if not os.path.exists(log_directory):
    os.makedirs(log_directory)
log_file_path = os.path.join(log_directory, 'auto_pppoe.log')
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
file_handler = TimedRotatingFileHandler(filename=log_file_path, when='midnight', interval=1,
                                        backupCount=30)  # 日志文件按天滚动，保留时长为30天
file_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
logging.getLogger().addHandler(file_handler)  # 将Handler添加到Logger中

logo = """开始启动Auto_PPPoE脚本程序...\n
     ██               ██                  ███████  ███████  ███████           ████████                 ██      ████ 
    ████             ░██                 ░██░░░░██░██░░░░██░██░░░░██         ░██░░░░░                 ███     █░░░██
   ██░░██   ██   ██ ██████  ██████       ░██   ░██░██   ░██░██   ░██  ██████ ░██             ██    ██░░██    ░█  █░█
  ██  ░░██ ░██  ░██░░░██░  ██░░░░██      ░███████ ░███████ ░███████  ██░░░░██░███████       ░██   ░██ ░██    ░█ █ ░█
 ██████████░██  ░██  ░██  ░██   ░██      ░██░░░░  ░██░░░░  ░██░░░░  ░██   ░██░██░░░░        ░░██ ░██  ░██    ░██  ░█
░██░░░░░░██░██  ░██  ░██  ░██   ░██      ░██      ░██      ░██      ░██   ░██░██             ░░████   ░██  ██░█   ░█
░██     ░██░░██████  ░░██ ░░██████  █████░██      ░██      ░██      ░░██████ ░████████ █████  ░░██    ████░██░ ████ 
░░      ░░  ░░░░░░    ░░   ░░░░░░  ░░░░░ ░░       ░░       ░░        ░░░░░░  ░░░░░░░░ ░░░░░    ░░    ░░░░ ░░  ░░░░  
"""

success = """初始化部署完成！\n
     ________  ___  ___  ________  ________  _______   ________   ________      
    |\\   ____\\|\\  \\|\\  \\|\\   ____\\|\\   ____\\|\\  ___ \\ |\\   ____\\ |\\   ____\\     
    \\ \\  \\___|\\ \\  \\\\\\  \\ \\  \\___|\\ \\  \\___|\\ \\   __/|\\ \\  \\___|_\\ \\  \\___|_    
     \\ \\_____  \\ \\  \\\\\\  \\ \\  \\    \\ \\  \\    \\ \\  \\_|/_\\ \\_____  \\\\ \\_____  \\   
      \\|____|\\  \\ \\  \\\\\\  \\ \\  \\____\\ \\  \\____\\ \\  \\_|\\ \\|____|\\  \\|____|\\  \\  
        ____\\_\\  \\ \\_______\\ \\_______\\ \\_______\\ \\_______\\____\\_\\  \\ ____\\_\\  \\ 
       |\\_________\\|_______|\\|_______|\\|_______|\\|_______|\\_________\\\\_________\\
       \\|_________|                                       \\|_________|\\|_________|
"""


def get_pppoe_basicinfo_from_control_node():
    params = {
        "machineTag": f"{machineTag}"
    }
    try:
        response = requests.get(get_pppoe_basicinfo_api_url, headers=question_headers, params=params)
        response_data = response.json()
        pppoe_basicinfo = response_data.get("data", {})
        if pppoe_basicinfo is not None:
            return pppoe_basicinfo
        else:
            logging.error("从控制节点获取配置信息失败，返回数据为空，请检查本机系统获取的唯一标识符是否与控制节点一致！")
    except requests.RequestException as e:
        logging.error("从控制节点获取配置信息失败，错误信息：%s", str(e))


def get_interface_status(ifname):
    try:
        result = subprocess.check_output(['ip', 'link', 'show', ifname])
        result = result.decode('utf-8')
        if any("DOWN" in line for line in result.split('\n')):
            return "DOWN"
        else:
            return "UP"
    except subprocess.CalledProcessError as e:
        logging.error(e)
        return "Error"


def get_ip_address(ifname):
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        ifaddr = fcntl.ioctl(s.fileno(), 0x8915, struct.pack('256s', ifname[:15].encode('utf-8')))
        ip_address = socket.inet_ntoa(struct.unpack('4s', ifaddr[20:24])[0])
        return ip_address
    except Exception as e:
        logging.error(e)
        return None


def create_netif_info_dict():
    prefix = 'enp'
    try:
        with open('/proc/net/dev') as f:
            interfaces = [line.split(':')[0].strip() for line in f if ':' in line]
        sorted_interfaces = sorted([ifname for ifname in interfaces if ifname.startswith(prefix)],
                                   key=lambda x: int(''.join(filter(str.isdigit, x[len(prefix):]))))
        netif_info = {}
        for ifname in sorted_interfaces:
            netif_info[ifname] = {
                "Status": get_interface_status(ifname),
                "IP": get_ip_address(ifname)
            }
        return netif_info
    except Exception as e:
        logging.error(e)
        return None


# 初始化-主函数
def install_pppoe_runtime_environment():
    def check_configure_dns():
        logging.info("开始检测和配置DNS...")
        result = subprocess.run(['grep', '-E', '^nameserver', '/etc/resolv.conf'], stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, universal_newlines=True)
        if not result.stdout:
            subprocess.run(
                ['sudo', 'bash', '-c', 'echo "nameserver 114.114.114.114\nnameserver 8.8.8.8" >> /etc/resolv.conf'])
            logging.info("检测到系统未配置DNS,已将DNS配置为114和8.8.8.8")

    def close_Net_workManager():
        cmd1 = "sudo systemctl stop NetworkManager"
        cmd2 = "sudo systemctl disable NetworkManager"
        subprocess.run(cmd1, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
        subprocess.run(cmd2, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
        logging.info("已经关闭NetworkManager并禁用开机自启")

    def install_package(package_name):
        # 检测是否已经安装yum list installed | grep 包名
        logging.info(f"开始安装{package_name}...")
        try:
            subprocess.run(['sudo', 'yum', 'install', '-y', package_name], stdout=subprocess.DEVNULL,
                           stderr=subprocess.DEVNULL, check=True)
            logging.info(f"{package_name}已安装")
        except Exception as e:
            logging.error(f"安装{package_name}时发生错误：{e}")
            sys.exit(1)

    def load_8021q_module():
        logging.info("开始加载802.1q模块...")
        try:
            subprocess.run(["sudo", "modprobe", "8021q"], check=True)
            logging.info("802.1q模块已加载")
        except subprocess.CalledProcessError as e:
            logging.error(f"加载802.1q模块时发生错误：{e}")
            sys.exit(1)

    def add_8021q_to_modules_file():
        try:
            with open("/etc/modules", "a") as modules_file:
                modules_file.write("8021q\n")
            logging.info("已将802.1q模块添加到/etc/modules文件")
        except Exception as e:
            logging.warn(f"向/etc/modules文件添加802.1q模块时发生错误：{e}")

    def configure_snmpd_conf_and_start_the_service(community_name="machine@Y%Ip8zaY8dA1", port=161):
        config_lines = [
            f"rocommunity {community_name}",
            f"agentAddress udp:{port}",
        ]
        file_path = "/etc/snmp/snmpd.conf"
        # 读取现有内容
        with open(file_path, "r") as snmpd_conf:
            existing_content = snmpd_conf.read()
        # 将配置写入文件，加在现有内容之前
        with open(file_path, "w") as snmpd_conf:
            snmpd_conf.write("\n".join(config_lines) + "\n" + existing_content)
        # 重启SNMP服务
        try:
            cmd1 = "sudo systemctl restart snmpd"
            cmd2 = "sudo systemctl enable snmpd"
            subprocess.run(cmd1, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
            subprocess.run(cmd2, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
            logging.info("SNMP服务已启动并设置为开机自启")
        except subprocess.CalledProcessError as e:
            logging.error(f"重启SNMP服务时出错: {e}")

    check_configure_dns()
    close_Net_workManager()
    install_package('epel-release')
    install_package('rp-pppoe')
    install_package('vconfig')
    install_package("net-snmp")
    install_package("net-snmp-utils")
    install_package("fping")
    # install_package('docker')
    load_8021q_module()
    add_8021q_to_modules_file()
    configure_snmpd_conf_and_start_the_service()


# 初始化和拨号流程运行前检查函数
# 检查标记
def check_run_flag(type):
    if type == "init":
        return os.path.exists((os.path.join(os.path.dirname(os.path.abspath(__file__)), 'init.flag')))
    if type == "pppoe":
        return os.path.exists((os.path.join(os.path.dirname(os.path.abspath(__file__)), 'pppoe.flag')))


# 创建标记
def set_run_flag(type):
    if type == "init":
        with open((os.path.join(os.path.dirname(os.path.abspath(__file__)), 'init.flag')), "w") as file:
            file.write("这台机器之前已部署了拨号环境，并安装了docker")
    if type == "pppoe":
        with open((os.path.join(os.path.dirname(os.path.abspath(__file__)), 'pppoe.flag')), "w") as file:
            file.write("这台机器之前已经创建了拨号配置文件")


def write_secrets_to_pppoe_config_file(account, secret):
    secrets_content = f'"{account}"        *       "{secret}"\n'
    paths = ["/etc/ppp/chap-secrets", "/etc/ppp/pap-secrets"]
    try:
        for path in paths:
            with open(path, "a") as secrets_file:
                secrets_file.write(secrets_content)
        logging.info("拨号账户密码信息已写入/etc/ppp/chap-secret和/etc/ppp/pap-secrets")
    except Exception as e:
        logging.info(f"向/etc/ppp/chap-secret和/etc/ppp/pap-secrets写入拨号账户密码信息时发生错误：{e}")
        sys.exit(1)


def create_ifconfig_file(file_type, ifname, vlanid=None, pppoe_user=None, macaddr=None, pppoe_number=None):
    if file_type == "ifname-vlan":
        ifconfig_content = f"TYPE=vlan\nPROXY_METHOD=none\nBROWSER_ONLY=no\nBOOTPROTO=static\nDEFROUTE=yes\nIPV4_FAILURE_FATAL=no\nIPV6INIT=yes\nIPV6_AUTOCONF=yes\nIPV6_DEFROUTE=yes\nIPV6_FAILURE_FATAL=no\nIPV6_ADDR_GEN_MODE=stable-privacy\nNAME={ifname}.{vlanid}\nDEVICE={ifname}.{vlanid}\nVLAN_ID={vlanid}\nVLAN=yes\nONBOOT=yes\nMACADDR={macaddr}\n"
        file_path = f'/etc/sysconfig/network-scripts/ifcfg-{ifname}.{vlanid}'
        # 对于后续更新中无需重建虚拟网卡
        if os.path.exists(file_path):
            file_path = None
    elif file_type == "pppoe-vlan":
        ifconfig_content = f"USERCTL=yes\nBOOTPROTO=dialup\nNAME=DSL{pppoe_number}\nDEVICE={pppoe_number}\nTYPE=xDSL\nONBOOT=yes\nPIDFILE=/var/run/pppoe-ads{pppoe_number}.pid\nFIREWALL=NONE\nPING=.\nPPPOE_TIMEOUT=80\nLCP_FAILURE=3\nLCP_INTERVAL=20\nCLAMPMSS=1412\nCONNECT_POLL=6\nCONNECT_TIMEOUT=60\nDEFROUTE=no\nSYNCHRONOUS=no\nETH={ifname}.{vlanid}\nPROVIDER=DSL{pppoe_number}\nUSER={pppoe_user}\nPEERDNS=no\nDEMAND=no\n"
        file_path = f'/etc/sysconfig/network-scripts/ifcfg-{pppoe_number}'
    elif file_type == "pppoe-no-vlan":
        ifconfig_content = f"USERCTL=yes\nBOOTPROTO=dialup\nNAME=DSL{pppoe_number}\nDEVICE={pppoe_number}\nTYPE=xDSL\nONBOOT=yes\nPIDFILE=/var/run/pppoe-ads{pppoe_number}.pid\nFIREWALL=NONE\nPING=.\nPPPOE_TIMEOUT=80\nLCP_FAILURE=3\nLCP_INTERVAL=20\nCLAMPMSS=1412\nCONNECT_POLL=6\nCONNECT_TIMEOUT=60\nDEFROUTE=no\nSYNCHRONOUS=no\nETH={ifname}\nPROVIDER=DSL{pppoe_number}\nUSER={pppoe_user}\nPEERDNS=no\nDEMAND=no\n"
        file_path = f'/etc/sysconfig/network-scripts/ifcfg-{pppoe_number}'
    try:
        if file_path is not None:
            with open(file_path, 'w') as file:
                file.write(ifconfig_content)
        logging.info(f"{ifname}的{file_type}接口配置文件已创建")
    except Exception as e:
        logging.error(f"{ifname}的{file_type}接口配置文件创建失败，错误信息：{e}")
        sys.exit(1)


def create_routing_tables(table_number, pppoe_ifname):
    rt_tables_file = "/etc/iproute2/rt_tables"
    # 获取当前路由表优先级编号，用于后续编号去重
    table_numbers_list = []
    with open(rt_tables_file, 'r') as file:
        rt_tables = file.read()  # 读取用于条目内容去重
        for line in file:
            line = line.strip()
            if line and not line.startswith('#'):
                match = re.match(r'^\s*(\d+)', line)
                if match:
                    number = int(match.group(1))
                    table_numbers_list.append(number)
    # 确保table_number的唯一性
    while table_number in table_numbers_list:
        table_number += 1
    try:
        check_string = f"{table_number} {pppoe_ifname}_table"
        with open(rt_tables_file, 'r') as file:
            if check_string not in file.read():
                # 如果同名路由表不存在则添加
                command = f"echo '{check_string}' >> {rt_tables_file}"
                subprocess.run(command, shell=True, check=True)
                logging.info(f"添加路由表'{check_string}' 到 {rt_tables_file}成功！")
            else:
                logging.info(f"路由表'{check_string}' 已经被添加于 {rt_tables_file}中，无需重复添加")
    except FileNotFoundError:
        logging.error(f"错误: {rt_tables_file} 不存在")
    table_number += 1
    return table_number


def get_local_pppoe_ifname(pppoe_ifname):
    command = f"pppoe-status /etc/sysconfig/network-scripts/ifcfg-{pppoe_ifname}"
    try:
        result = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True,
                                  universal_newlines=True)
        stdout, stderr = result.communicate()

        if result.returncode == 0:
            ifname_pattern = ':(.*?):'
            match = re.search(ifname_pattern, stdout)
            if match:
                ifname = match.group(1).strip()
                return ifname
            else:
                ifname = ""
                return ifname
    except Exception as e:
        logging.exception(f"发生异常：{str(e)}")


def get_local_pppoe_ip(pppoe_ifname):
    command = f"pppoe-status /etc/sysconfig/network-scripts/ifcfg-{pppoe_ifname}"
    try:
        result = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True,
                                  universal_newlines=True)
        stdout, stderr = result.communicate()

        if result.returncode == 0:
            ip_pattern = 'inet(.*?)peer'
            match = re.search(ip_pattern, stdout)
            if match:
                ip_address = match.group(1).strip()
                return ip_address
            else:
                ip_address = ""
                return ip_address
    except Exception as e:
        logging.exception(f"发生异常：{str(e)}")


# 获取mac地址
def get_mac_address(interface):
    try:
        # 获取网卡的MAC地址
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        mac_address = fcntl.ioctl(sock.fileno(), 0x8927, struct.pack('256s', interface[:15].encode('utf-8')))
        mac_address = ':'.join(['%02x' % b for b in mac_address[18:24]])
        return mac_address
    except IOError:
        return f"接口{interface}未获取到mac地址"


def update_pppline_to_control_node(node_status, pppline):
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    data = {
        "alarmTime": current_time,
        "machineTag": machineTag,
        "nodeStatus": node_status,
        "pppline": pppline
    }
    try:
        response = requests.post(update_pppline_api_url, headers=question_headers, json=data)
        if "200" in response.text:
            logging.info("更新pppoe在线状态信息成功,已经推送至控制平台")
        else:
            logging.error(f"更新pppoe在线状态信息失败，错误信息：{response.text}")
    except requests.RequestException as e:
        logging.error("更新pppoe在线状态信息失败，错误信息：%s", str(e))


def update_pppline_monitor_to_control_node(pppline_monitor_info):
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    data = {
        "machineTag": machineTag,
        "monitorInfo": pppline_monitor_info,
        "reportTime": current_time
    }
    try:
        response = requests.post(update_pppline_monitor_info_api_url, headers=question_headers, json=data)
        if "200" in response.text:
            logging.info("更新pppoe在线状态信息成功，已推送至控制平台")
        else:
            logging.error(f"更新pppoe在线状态信息失败，错误信息：{response.text}")
    except requests.RequestException as e:
        logging.error("更新pppoe在线状态信息失败，错误信息：%s", str(e))


def update_dial_connect_to_control_node(type, node_name, pppoe_ifname):
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    if type == 30:
        info = f"{node_name}节点机器-{machineTag}：{pppoe_ifname}拨号断线"
    if type == 40:
        info = f"{node_name}节点机器-{machineTag}：{pppoe_ifname}拨号重连成功"
    data = {
        "alarmComment": f"{current_time} {info}",
        "alarmTime": current_time,
        "machineTag": machineTag,
        "type": type
    }
    try:
        response = requests.post(update_dial_connect_api_url, headers=question_headers, json=data)
        if "200" in response.text:
            logging.info("更新拨号断连信息成功，已推送至控制平台")
        else:
            logging.info(f"更新拨号断连信息失败，错误信息：{response.text}")

    except requests.RequestException as e:
        logging.error("更新pppoe重连信息失败，错误信息：%s", str(e))


def get_node_status(pppoe_ifname):
    try:
        cmd = f"fping -I {pppoe_ifname} baidu.com"
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
        if "alive" in result.stdout.decode('utf-8'):
            return 1
        else:
            return 0
    except subprocess.CalledProcessError as e:
        logging.error(f"检测节点拨号网卡互联网连通性出错：{e}")


# 断线重连监测上报-主函数
def set_update_discon_flag(pppoe_ifname):
    discon_flag_path = os.path.join(script_path, f'{pppoe_ifname}_discon.flag')
    with open(discon_flag_path, "w") as file:
        file.write(f"{pppoe_ifname}断线告警标记")


def check_update_discon_flag(pppoe_ifname):
    discon_flag_path = os.path.join(script_path, f'{pppoe_ifname}_discon.flag')
    return os.path.exists(discon_flag_path)


def check_pppoe_connect_process_exists(pppoe_ifname):
    cmd = "ps aux | grep pppoe-connect"
    result = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True, universal_newlines=True)
    stdout, stderr = result.communicate()
    if f"ifcfg-{pppoe_ifname}" in stdout:
        return True
    else:
        return False


def check_for_reconnection_and_update_to_crontrol_node():
    pppoe_basicinfo = get_pppoe_basicinfo_from_control_node()
    node_name = pppoe_basicinfo["city"]
    pppline = pppoe_basicinfo['pppline']
    retry_counts_path = os.path.join(script_path, 'retry_counts.json')
    with open(retry_counts_path, 'r', encoding='utf-8') as file:
        retry_counts = json.load(file)
    for pppoe_ifname in pppline.keys():
        if get_local_pppoe_ip(f'{pppoe_ifname}') is None:
            type = 30
            pppoe_user = pppline[pppoe_ifname]['user']
            if check_update_discon_flag(pppoe_ifname) is False:
                update_dial_connect_to_control_node(type, node_name, pppoe_ifname)
                logging.info(f"{pppoe_ifname}({pppoe_user}) 拨号网卡断线，已经上报控制节点")
                # 检测pppoe-connect进程是否存在，避免一号多拨
                if check_pppoe_connect_process_exists(pppoe_ifname) is False:
                    logging.info(
                        f"检测到{pppoe_ifname}({pppoe_user})的pppoe-connect驻守进程已经不存在，即将重新进行拨号...")
                    pppoe_dial_up(pppoe_ifname, pppoe_user)
                set_update_discon_flag(pppoe_ifname)
        else:
            type = 40
            if check_update_discon_flag(pppoe_ifname):
                logging.info(f"{pppoe_ifname} 拨号网卡重拨成功，已经上报控制节点")
                if pppoe_ifname not in retry_counts.keys():
                    retry_counts[pppoe_ifname] = 1
                if retry_counts[pppoe_ifname] is None:
                    retry_counts[pppoe_ifname] = 1
                if retry_counts[pppoe_ifname] > 500:  # 计数500归零
                    retry_counts[pppoe_ifname] = 1
                else:
                    retry_counts[pppoe_ifname] += 1
                # 写入重拨次数到文件，方便后续调用
                with open(retry_counts_path, 'w', encoding='utf-8') as file:
                    json.dump(retry_counts, file, ensure_ascii=False, indent=2)
                update_dial_connect_to_control_node(type, node_name, pppoe_ifname)
                os.remove(f"{pppoe_ifname}_discon.flag")


# 节点具体信息上报到控制节点 或者客户-主函数
def collect_node_spacific_info_update_to_control_node_or_customers():
    def create_local_pppline_empty_dict(pppoe_basicinfo):
        pppline = pppoe_basicinfo['pppline']
        # 创建本地字典pppline
        pppline_local = {}
        for pppoe_ifname in pppline.keys():
            # pppline_local
            pppline_local[pppoe_ifname] = {}
            pppline_local[pppoe_ifname]['status'] = ''
            pppline_local[pppoe_ifname]['ip'] = ''
            pppline_local[pppoe_ifname]['ssh_port'] = '22'
            pppline_local[pppoe_ifname]['min_port'] = '0'
            pppline_local[pppoe_ifname]['max_port'] = '0'
            pppline_local[pppoe_ifname]['max_upbw_mbps'] = pppline[pppoe_ifname]['bandwidth']
            pppline_local[pppoe_ifname]['max_downbw_mbps'] = pppline[pppoe_ifname]['bandwidth']
        return pppline_local

    pppoe_basicinfo = get_pppoe_basicinfo_from_control_node()
    node_name = pppoe_basicinfo["city"]
    report_on = pppoe_basicinfo["reported"]
    pppline_local = create_local_pppline_empty_dict(pppoe_basicinfo)
    node_status = 0  # 默认节点不可用
    # 读取拨号网卡的重拨次数
    retry_counts_path = os.path.join(script_path, 'retry_counts.json')
    with open(retry_counts_path, 'r', encoding='utf-8') as file:
        retry_counts = json.load(file)
    for pppoe_ifname in pppline_local.keys():
        status = get_node_status(pppoe_ifname)
        if status == 1:
            node_status = 1  # 但凡有一个接口能通公网，证明节点可用..
        # 创建上报控制节点必要更新信息
        pppline_local[pppoe_ifname]['retry_counts'] = retry_counts[pppoe_ifname]
        pppline_local[pppoe_ifname]["status"] = status
        pppline_local[pppoe_ifname]["ip"] = get_local_pppoe_ip(f'{pppoe_ifname}')

    # 上报平台
    update_pppline_to_control_node(node_status, pppline_local)
    # 是否上报客户
    if report_on == 1:
        # 上报路径
        reportLocalPath = pppoe_basicinfo["reportLocalPath"]
        # 创建上报客户的必要节点更新信息
        pppoe_basicinfo_for_customers = {}
        pppoe_basicinfo_for_customers['sid'] = pppoe_basicinfo['name']
        pppoe_basicinfo_for_customers['timestamp'] = int(time.time())
        for pppoe_ifname in pppline_local.keys():
            pppoe_basicinfo_for_customers['status'] = get_node_status(pppoe_ifname)
        pppoe_basicinfo_for_customers['province'] = pppoe_basicinfo['province']
        pppoe_basicinfo_for_customers['city'] = node_name
        pppoe_basicinfo_for_customers['provider'] = pppoe_basicinfo['provider']
        pppoe_basicinfo_for_customers['isp'] = pppoe_basicinfo['isp']
        pppoe_basicinfo_for_customers['nat_type'] = pppoe_basicinfo['authType']
        pppoe_basicinfo_for_customers['upstreambandwidth'] = pppoe_basicinfo['upstreambandwidth']
        pppoe_basicinfo_for_customers['linecount'] = pppoe_basicinfo['linecount']
        pppoe_basicinfo_for_customers['cpu'] = pppoe_basicinfo['cpu']
        pppoe_basicinfo_for_customers['memory'] = pppoe_basicinfo['memory']
        pppoe_basicinfo_for_customers['pppline'] = {}
        pppoe_basicinfo_for_customers['pppline'] = pppline_local
        # 上报给客户
        with open(reportLocalPath, 'w', encoding='utf-8') as file:
            json.dump(pppoe_basicinfo_for_customers, file, ensure_ascii=False, indent=2)
        logging.info("已经向客户更新推送了最新的拨号状态信息")
    # 存储一份到本地
    pppoe_basicinfo_path = os.path.join(script_path, 'pppoe_basicinfo.json')
    with open(pppoe_basicinfo_path, 'w', encoding='utf-8') as file:
        json.dump(pppoe_basicinfo_for_customers, file, ensure_ascii=False, indent=2)


# 拨号前的配置-主函数
def create_pppoe_connection_file_and_routing_tables(ppp_line):
    # 获取本机的所有mac地址列表
    def get_local_mac_address_list():
        mac_addresses = []
        for interface in socket.if_nameindex():
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                mac_address = fcntl.ioctl(sock.fileno(), 0x8927, struct.pack('256s', interface[1][:15].encode('utf-8')))
                mac_address = ':'.join(['%02x' % b for b in mac_address[18:24]])
                mac_addresses.append(mac_address)
            except:
                pass
        return mac_addresses

    # 虚拟网卡的mac地址推导,并验证在本机的唯一性
    def derivation_mac_address(mac_addr):
        # 接下来的优化方向：获取
        last_two_digits = int(mac_addr[-2:], 16)
        last_two_digits = (last_two_digits + 1) % 256
        new_last_two_digits = format(last_two_digits, '02x')
        new_mac_address = mac_address[:-2] + new_last_two_digits
        # 与本机所有mac地址比较，如果已存在，再生成新mac检查是否与本机现有mac重复,直到获取唯一的mac
        while new_mac_address in original_mac_address_list:
            new_mac_address = derivation_mac_address(new_mac_address)
        return new_mac_address

    # 开始拨号前的配置
    # pppoe_basicinfo = get_pppoe_basicinfo_from_control_node()
    # logging.info("从控制节点获取配置信息成功")
    # ppp_line = pppoe_basicinfo['pppline']
    # 检查平台提供的拨号信息是否完整
    counts = 0
    for ifname in ppp_line.keys():
        if ppp_line[ifname]['user'] is None or ppp_line[ifname]['pass'] is None:
            counts += 1
            # if counts < len(ppp_line):
    #     logging.error("部分拨号网卡用户名或密码信息为空，请检查控制平台信息填写是否完整")
    table_number = 50
    # 创建本机的mac地址表用于后续进行比对
    original_mac_address_list = get_local_mac_address_list()
    # 定义初始mac
    mac_address = "00:00:00:00:00:00"
    # 遍历平台提供的信息并开始写入配置文件
    for pppoe_ifname in ppp_line.keys():
        pppoe_user = ppp_line[pppoe_ifname]['user']
        pppoe_pass = ppp_line[pppoe_ifname]['pass']
        pppoe_vlan = ppp_line[pppoe_ifname]['vlan']
        dial_up_ifnmme = ppp_line[pppoe_ifname]['eth']
        write_secrets_to_pppoe_config_file(pppoe_user, pppoe_pass)
        # 如果接口vlan文件已存在，则不进行创建
        if pppoe_vlan == "0":
            logging.info(f"{pppoe_ifname}没有VLAN")
            create_ifconfig_file('pppoe-no-vlan', ifname=dial_up_ifnmme, vlanid=pppoe_vlan, pppoe_user=pppoe_user,
                                 pppoe_number=pppoe_ifname)
            # 创建路由表并通过create_routing_tables的返回值得出新的路由表优先级编号
            table_number = create_routing_tables(table_number, pppoe_ifname)
        else:
            logging.info(f"{pppoe_ifname}所属VLAN{pppoe_vlan}")

            create_ifconfig_file('ifname-vlan', ifname=dial_up_ifnmme, vlanid=pppoe_vlan, pppoe_user=pppoe_user,
                                 macaddr=mac_address, pppoe_number=pppoe_ifname)
            create_ifconfig_file('pppoe-vlan', ifname=dial_up_ifnmme, vlanid=pppoe_vlan, pppoe_user=pppoe_user,
                                 macaddr=mac_address, pppoe_number=pppoe_ifname)
            table_number = create_routing_tables(table_number, pppoe_ifname)
            table_number += 1  # 路由表序号+1
            mac_address = derivation_mac_address(mac_address)  # mac地址后2位尾数按照16进制+1
            # 开启Vlan子接口
            cmd = f"ifup {dial_up_ifnmme}.{pppoe_vlan}"
            subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
            logging.info(f"Vlan子接口{dial_up_ifnmme}.{pppoe_vlan}已启用")
    return ppp_line


def pppoe_dial_up(pppoe_ifname, pppoe_user):
    try:
        logging.info(f"{pppoe_ifname}({pppoe_user}) 开始拨号...")
        command = f"pppoe-connect /etc/sysconfig/network-scripts/ifcfg-{pppoe_ifname} &"
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True,
                                   universal_newlines=True)
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


# 自动维护路由
# 路由维护-主函数
def update_pppoe_routing_table(pppline):
    def get_current_route_rule_ip():
        def get_ip_rules():
            try:
                result = subprocess.check_output(["ip", "rule", "list"], universal_newlines=True)
                return result
            except subprocess.CalledProcessError as e:
                logging.error(f"Error: {e}")
                return None

        def extract_ip_addresses(input_string):
            ip_pattern = r'\b(?:\d{1,3}\.){3}\d{1,3}\b'
            ip_addresses = re.findall(ip_pattern, input_string)
            return ip_addresses

        ip_rules_output = get_ip_rules()
        ip_list = extract_ip_addresses(ip_rules_output)
        # logging.info(f"当前路由规则中的IP地址列表：{ip_list}")
        return ip_list

    def get_ip_address(ifname):
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            ip_address = socket.inet_ntoa(fcntl.ioctl(
                sock.fileno(),
                0x8915,
                struct.pack('256s', bytes(ifname[:15], 'utf-8')))[20:24])
            return ip_address
        except Exception as e:
            logging.error(f"获取{ifname}的IP时出错: {str(e)}")
            return None

    def del_rules(ip, table):
        cmd = f"ip rule del from {ip} table {table}"
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
        if result.returncode != 0:
            logging.error(f"删除路由时出错: {cmd} 错误代码：{result.stderr.decode('utf-8')}")
        else:
            logging.info(f"删除无效IP路由路由成功: {cmd}")

    # ip rule del from 10.0.192.176 table v9
    # 这是删路由

    def add_rules(ifname, table, ip):
        cmd1 = f"ip route add default dev {ifname} table {table}"
        cmd2 = f"ip rule add from {ip} table {table}"
        result1 = subprocess.run(cmd1, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
        result2 = subprocess.run(cmd2, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
        if result1.returncode != 0:
            if result2.returncode != 0:
                logging.error(f"{ifname}添加新路由时出错，错误代码：{result1.stderr.decode('utf-8')}")
        else:
            logging.info(f"新拨号网卡：{ifname} 新获取到的IP：{ip} 添加路由成功")

    # ifname和table对应
    # ip route add default dev ppp0 table v1
    # ip rule add from 10.0.192.2 table v1
    # 这是加路由
    def get_expired_ip_router_rules(keyword):
        try:
            # result = subprocess.run(['ip', 'rule', 'list'], capture_output=True, text=True, check=True)
            result = subprocess.run(["ip", "rule", "list"], stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                    universal_newlines=True)
            output_lines = result.stdout.splitlines()
            relevant_line = next((line for line in output_lines if keyword in line), None)

            if relevant_line:
                start_index = relevant_line.find('ppp')
                if start_index != -1:
                    extracted_content = relevant_line[start_index:]
                    return extracted_content
            return None
        except subprocess.CalledProcessError as e:
            logging.error(f"Error: {e}")
            return None

    def get_pppoe_ip_address_list():
        pppoe_ip_address_list = []
        for ifname in pppoe_info.keys():
            ip_address = get_ip_address(ifname)
            pppoe_info[ifname]['ip'] = ip_address
            if ip_address is not None:
                pppoe_ip_address_list.append(ip_address)

        return pppoe_ip_address_list

    def find_ifnmae_by_ip(pppoe_info, target_ip):
        for key, value in pppoe_info.items():
            if value['ip'] == target_ip:
                return key
        return None

    def find_ifnmae_by_table(pppoe_info, target_ip):
        for key, value in pppoe_info.items():
            if value['table'] == target_ip:
                return key
        return None

    def from_route_rules_get_old_ip_table():
        route_ip_list = get_current_route_rule_ip()
        old_ip_table = {}
        for ip in route_ip_list:
            data = get_expired_ip_router_rules(ip)
            old_table = re.sub(r'\s+', '', data)
            old_ip_table[old_table] = ip

        return old_ip_table

    def del_duplicate_ip_routing_rules():
        def get_ip_routing_rules():
            try:
                result = subprocess.check_output(["ip", "rule", "list"], universal_newlines=True)
                return result
            except subprocess.CalledProcessError as e:
                logging.error(f"Error: {e}")
                return None

        def extract_ip_addresses(input_string):
            ip_pattern = r'from.*?$'
            ip_addresses = re.findall(ip_pattern, input_string, re.MULTILINE)
            return ip_addresses

        ip_routing_rules_output = get_ip_routing_rules()
        ip_routing_rules_list = extract_ip_addresses(ip_routing_rules_output)
        # 删除重复的路由
        ip_routing_rules_counter = Counter(ip_routing_rules_list)
        for ip_routing_rules, count in ip_routing_rules_counter.items():
            if count > 1:
                logging.info(f"检测到重复路由{ip_routing_rules},即将清理")
                for i in range(count - 1):
                    cmd = f"ip rule del {ip_routing_rules.strip()}"
                    subprocess.run(cmd, shell=True)
                logging.info(f"重复路由清理完毕")

    # 创建当前在线的网卡信息
    pppoe_info = {}
    for pppoe_ifname in pppline.keys():
        pppoe_info[pppoe_ifname] = {}
        pppoe_info[pppoe_ifname]['ip'] = ''
        pppoe_info[pppoe_ifname]['table'] = f'{pppoe_ifname}_table'

    # 获取当前在线ip列表和路由表中所包含的ip列表
    pppoe_ip_address_list = get_pppoe_ip_address_list()
    route_ipaddress_list = get_current_route_rule_ip()

    # 检测当前路由表中的是否有重复的条目并删除
    del_duplicate_ip_routing_rules()

    # 删除无效路由
    route_set = set(route_ipaddress_list)
    pppoe_set = set(pppoe_ip_address_list)

    same = route_set.intersection(pppoe_set)
    expired_ip_list = route_set - same

    if route_set == pppoe_set:
        logging.info(f"当前在线IP和路由表IP条目符合，在线IP:{pppoe_ip_address_list}")
    else:
        logging.info(f"当前在线IP和路由表IP条目不符合! 即将开始删除无效IP路和新增新拨号的IP路由")

    # 创建新拨号网卡的IP集合,其中包括了路由表ip和接口对应关系与目前不一致的
    # new_ip_list = set()
    # 路由表ip和接口对应关系与目前不一致的也要加入无效列表，避免重拨获取到的ip和原来一样的情况

    # 路由表ip和接口对应关系与目前一致，但是对应的路由表有误的也要加入无效列表，避免
    old_ip_table = from_route_rules_get_old_ip_table()
    for old_table, old_ip in old_ip_table.items():
        ifname = find_ifnmae_by_table(pppoe_info, old_table)
        if old_ip_table[old_table] != pppoe_info[ifname]['ip']:
            # if old_ip !=  pppoe_info[ifname]['ip']:
            expired_ip_list.add(old_ip_table[old_table])
            # new_ip_list.add(old_ip_table[old_table])
    for ip in expired_ip_list:
        table = get_expired_ip_router_rules(ip)
        # logging.info(f"无效路由:{ip} 对应的表项:{table}")
        del_rules(ip, table)
    if len(expired_ip_list) != 0:
        logging.info("无效路由已经全部清除")

    # 再次获取清理后的路由表
    route_set = set(route_ipaddress_list)

    # 添加新拨号获取的IP路由
    new_ip_list = pppoe_set - route_set
    # new_ip_list.add(different_ip_list)

    for ip in new_ip_list:
        ifname = find_ifnmae_by_ip(pppoe_info, ip)
        table = pppoe_info[ifname]['table']
        # logging.info(f"新拨号网卡：{ifname}，所获取的新IP：{ip}, 对应路由表：{table}")
        add_rules(ifname, table, ip)

    if len(new_ip_list) != 0:
        logging.info(f"所有新拨号网卡获取到的IP路由已添加！")


# 检查控制平台是否存在拨号信息的更新-主函数
def check_for_updates_and_config():
    def check_updates(pppline_local, pppline_control_node):
        if pppline_local != pppline_control_node:
            logging.info("检测到控制节点拨号信息发生更新")
            # 1. pppline_control_node有的键而pppline_local中没有的：账号新增
            keys_only_in_control_node = set(pppline_control_node.keys()) - set(pppline_local.keys())
            # 2. pppline_control_node没有有的键而pppline_local有的：账号减少
            keys_only_in_local = set(pppline_local.keys()) - set(pppline_control_node.keys())
            # 3. pppline_control_node和pppline_local都有的键但是值不一样的：账号更改
            same_keys_but_different_values = {}
            for key, value in pppline_control_node.items():
                if key in pppline_local and pppline_local[key]['user'] != pppline_control_node[key]['user']:
                    same_keys_but_different_values[key] = value
            return keys_only_in_control_node, keys_only_in_local, same_keys_but_different_values
        else:
            # 如果没有更新，返回空值
            return None, None, None

    # 获取当前云平台最新数据
    pppline_control_node = get_pppoe_basicinfo_from_control_node()["pppline"]
    # 获取本地存储的上次拨号成功的数据
    pppline_path = os.path.join(script_path, 'pppline.json')
    with open(pppline_path, 'r', encoding='utf-8') as file:
        pppline_local = json.load(file)
    # 获取差异数据
    keys_only_in_control_node, keys_only_in_local, same_keys_but_different_values = check_updates(pppline_local,
                                                                                                  pppline_control_node)
    # 1. 云平台有本地没有
    if keys_only_in_control_node:
        # 创建更新拨号信息列表
        add_pppoe_list = {}
        for ifname in keys_only_in_control_node:
            add_pppoe_list[ifname] = {}
            add_pppoe_list[ifname] = pppline_control_node[ifname]
            pppoe_user = pppline_control_node[ifname]['user']
            dial_up_ifname = pppline_control_node[ifname]['eth']
            logging.info(f"检测到云平台账号新增，配置接口名：ifcfg-{ifname} 物理接口：{dial_up_ifname} 账号：{pppoe_user}")
        # 创建新增项的拨号前配置
        create_pppoe_connection_file_and_routing_tables(add_pppoe_list)
        logging.info("所有新增拨号账号已建立拨号前的配置文件并写入密码信息")

    # 2. 本地有云平台没有
    if keys_only_in_local:
        logging.info("账号减少：%s", keys_only_in_local)
        for ifname in keys_only_in_local:
            pppoe_user = pppline_local[ifname]['user']
            dial_up_ifname = pppline_local[ifname]['eth']
            logging.info(f"检测到云平台账号删减，配置接口名：ifcfg-{ifname} 物理接口：{dial_up_ifname} 账号：{pppoe_user}")

            # 3. 本地和云平台都有但是值不一样
    if same_keys_but_different_values:
        modify_pppoe_list = {}
        for ifname in same_keys_but_different_values:
            modify_pppoe_list[ifname] = {}
            modify_pppoe_list[ifname] = pppline_control_node[ifname]
            old_pppoe_user = pppline_local[ifname]['user']
            pppoe_user = pppline_control_node[ifname]['user']
            logging.info(
                f"检测到云平台账号信息变动，配置接口名：ifcfg-{ifname} 原账号：{old_pppoe_user} 新账号：{pppoe_user}")
        create_pppoe_connection_file_and_routing_tables(modify_pppoe_list)
        logging.info("所有变更拨号账号已建立拨号前的配置文件并写入密码信息")
        # 写入此次拨号信息到硬盘，方便后续从云控制平台拉去信息与其对比，判断是否有更新
        with open(pppline_path, 'w', encoding='utf-8') as file:
            json.dump(pppline_control_node, file, ensure_ascii=False, indent=2)


# 网络监控数据采集上报-主函数
def traffic_speed_and_pingloss_collection():
    # 获取拨号接口带宽速率
    def get_pppline_bandwitch():
        def get_snmp_data(community, host, oid, port=161, is_string=False):
            result = {}
            for (errorIndication,
                 errorStatus,
                 errorIndex,
                 varBinds) in nextCmd(SnmpEngine(),
                                      CommunityData(community),
                                      UdpTransportTarget((host, port)),
                                      ContextData(),
                                      ObjectType(ObjectIdentity(oid)),
                                      lexicographicMode=False):

                if errorIndication:
                    logging.info(errorIndication)
                    break
                elif errorStatus:
                    logging.info('%s at %s' % (errorStatus.prettyPrint(),
                                               errorIndex and varBinds[int(errorIndex) - 1][0] or '?'))
                    break
                else:
                    for varBind in varBinds:
                        if is_string:
                            result[varBind[0].prettyPrint()] = varBind[1].prettyPrint()
                        else:
                            result[varBind[0].prettyPrint()] = int(varBind[1])
            return result

        def calculate_rate(old_values, new_values, interval):
            rates = {}
            for key in old_values:
                if key in new_values:
                    rates[key] = (new_values[key] - old_values[key]) / interval
            return rates

        def extract_last_value(s):
            # 使用'.'作为分隔符，将字符串分割为列表
            parts = s.split('.')
            # 返回列表的最后一个元素
            return parts[-1]

        community_string = 'machine@Y%Ip8zaY8dA1'
        host_ip = 'localhost'
        snmp_port = 161
        interval = 5  # in seconds

        in_octets_1 = get_snmp_data(community_string, host_ip, '1.3.6.1.2.1.2.2.1.10', snmp_port)
        out_octets_1 = get_snmp_data(community_string, host_ip, '1.3.6.1.2.1.2.2.1.16', snmp_port)
        time.sleep(interval)
        in_octets_2 = get_snmp_data(community_string, host_ip, '1.3.6.1.2.1.2.2.1.10', snmp_port)
        out_octets_2 = get_snmp_data(community_string, host_ip, '1.3.6.1.2.1.2.2.1.16', snmp_port)
        # 包含oid和接口名的字典
        ifname_dict = get_snmp_data(community_string, host_ip, '1.3.6.1.2.1.2.2.1.2', snmp_port, is_string=True)
        # 包含oid和进出口速率的字典
        in_rate_dict = calculate_rate(in_octets_1, in_octets_2, interval)
        out_rate_dict = calculate_rate(out_octets_1, out_octets_2, interval)

        # 创建包含接口名和速率的字典
        interface_in_rates = {}
        interface_out_rates = {}

        for ifname_oid, name in ifname_dict.items():
            ifname_index = extract_last_value(ifname_oid)
            for in_rate_oid in in_rate_dict.keys():
                in_rate_index = extract_last_value(in_rate_oid)
                if in_rate_index == ifname_index:
                    ifname = ifname_dict[ifname_oid]
                    in_rate = in_rate_dict[in_rate_oid]
                    interface_in_rates[ifname] = in_rate
            for out_rate_oid in out_rate_dict.keys():
                out_rate_index = extract_last_value(out_rate_oid)
                if out_rate_index == ifname_index:
                    ifname = ifname_dict[ifname_oid]
                    out_rate = out_rate_dict[out_rate_oid]
                    interface_out_rates[ifname] = out_rate

        # 创建上下行数据写入到到监控信息字典
        pppline_monitor_info_path = os.path.join(script_path, 'pppline_monitor_info.json')
        with open(pppline_monitor_info_path, 'r', encoding='utf-8') as file:
            pppline_monitor_info = json.load(file)
        for ifname in pppline_monitor_info.keys():
            online_ifname = get_local_pppoe_ifname(ifname)
            pppline_monitor_info[ifname]['current_max_upbw_mbps'] = round(
                interface_out_rates.get(online_ifname, 0.00) * 8 / 1000, 2)
            logging.info(
                f"{ifname}({pppline_monitor_info[ifname]['pppoe_user']})实时上行速率：{pppline_monitor_info[ifname]['current_max_upbw_mbps']}mbps")
            pppline_monitor_info[ifname]['current_max_downbw_mbps'] = round(
                interface_in_rates.get(online_ifname, 0.00) * 8 / 1000, 2)
            logging.info(
                f"{ifname}({pppline_monitor_info[ifname]['pppoe_user']})实时下行速率：{pppline_monitor_info[ifname]['current_max_downbw_mbps']}mbps")
        # 将字典写入本地文件
        with open(pppline_monitor_info_path, 'w', encoding='utf-8') as file:
            json.dump(pppline_monitor_info, file, ensure_ascii=False, indent=2)
        logging.info("实时上下行数据采集完成！")

    def get_pingloss_and_rtt():
        # 继续优化的方向就是将ping结果先存入字典，然后进行排序后输出，目前多线程结果输出是乱序的
        # fping -I eth0 -c 4 -q 8.8.8.8 8.8.4.4
        def ping_check(pppoe_ifname, local_pppoe_ifname):
            command = f"ping -i 0.5 -c 10 -I {pppoe_ifname} baidu.com"
            process = subprocess.Popen(command, stdout=subprocess.PIPE, shell=True)
            output, error = process.communicate()

            packet_loss = re.search(r"(\d+)% packet loss", output.decode("utf-8"))
            rtt = re.search(r"rtt min/avg/max/mdev = (.+)/(.+)/(.+)/(.+) ms", output.decode("utf-8"))
            if packet_loss:
                if rtt:
                    packet_loss = packet_loss.group(1)
                    rtt = rtt.group(3)
                    ifname_string = f"拨号接口：{pppoe_ifname}({local_pppoe_ifname})"
                    pccket_loss_string = f"丢包率：{int(packet_loss)}%"
                    rtt_string = f"延时：{round(float(rtt))}ms"
                    logging.info(f"{ifname_string:<20} {pccket_loss_string:<7} {rtt_string:<7}")
                    # 写入本地文件
                    pppline_monitor_info[ifname]['pingloss'] = int(packet_loss)
                    pppline_monitor_info[ifname]['rtt'] = float(rtt)
                    with open(pppline_monitor_info_path, 'w', encoding='utf-8') as file:
                        json.dump(pppline_monitor_info, file, ensure_ascii=False, indent=2)
                else:
                    logging.info(f"{pppoe_ifname} 获取ping延时数据出错")
            else:
                logging.info(f"{pppoe_ifname} 获取ping丢包率数据出错")

        def ping_round_list():
            threads = []
            for pppoe_ifname in pppline_monitor_info.keys():
                local_pppoe_ifname = pppline_monitor_info[pppoe_ifname]['online_ifname']
                thread = threading.Thread(target=ping_check, args=(pppoe_ifname, local_pppoe_ifname))
                thread.start()
                threads.append(thread)
            # 等待所有线程完成
            for thread in threads:
                thread.join()

        # 读取文件监控信息本地文件
        pppline_monitor_info_path = os.path.join(script_path, 'pppline_monitor_info.json')
        with open(pppline_monitor_info_path, 'r', encoding='utf-8') as file:
            pppline_monitor_info = json.load(file)
        # 启动ping线程
        ping_round_list()
        logging.info("Ping检测完成！")

    # 读取本地最新的拨号接口配置文件
    pppline_path = os.path.join(script_path, 'pppline.json')
    with open(pppline_path, 'r', encoding='utf-8') as file:
        pppline_local = json.load(file)

    # 创建监控信息记录文件
    pppline_monitor_info = {}
    for ifname in pppline_local.keys():
        pppline_monitor_info[ifname] = {}
        online_ifname = get_local_pppoe_ifname(ifname)
        pppline_monitor_info[ifname]['online_ifname'] = online_ifname
        pppline_monitor_info[ifname]['pppoe_user'] = pppline_local[ifname]['user']

    pppline_monitor_info_path = os.path.join(script_path, 'pppline_monitor_info.json')
    with open(pppline_monitor_info_path, 'w', encoding='utf-8') as file:
        json.dump(pppline_monitor_info, file, ensure_ascii=False, indent=2)
    # 获取接口实时上下行
    get_pppline_bandwitch()
    # 获取线路丢包延时
    get_pingloss_and_rtt()
    # 读取监控文件信息数据并推送数据到控制平台
    with open(pppline_monitor_info_path, 'r', encoding='utf-8') as file:
        pppline_monitor_info = json.load(file)
    update_pppline_monitor_to_control_node(pppline_monitor_info)


# 路由表维护-线程
def keep_pppoe_ip_routing_tables_available():
    while True:
        # 从本地获取拨号信息
        pppline_path = os.path.join(script_path, 'pppline.json')
        with open(pppline_path, 'r', encoding='utf-8') as file:
            pppline = json.load(file)
        update_pppoe_routing_table(pppline)
        time.sleep(15)


# 重拨信息汇报-线程
def monitor_dial_connect_and_update():
    pppoe_basicinfo = get_pppoe_basicinfo_from_control_node()
    retry_counts = {}
    # 重播次数初始化并写入文件到硬盘
    retry_counts_path = os.path.join(script_path, 'retry_counts.json')
    if os.path.exists(retry_counts_path) is False:
        for ifname in pppoe_basicinfo['pppline'].keys():
            retry_counts[ifname] = 0
        with open(retry_counts_path, 'w', encoding='utf-8') as file:
            json.dump(retry_counts, file, ensure_ascii=False, indent=2)
    while True:
        check_for_reconnection_and_update_to_crontrol_node()
        time.sleep(0.3)


# 节点综合信息上报平台及客户-线程
def report_node_info_to_control_node_and_customer():
    reportInterval = 15
    pppoe_basicinfo = get_pppoe_basicinfo_from_control_node()
    if pppoe_basicinfo["reported"] == 1:
        reportInterval = pppoe_basicinfo["reportInterval"]
        target_file_path = pppoe_basicinfo["reportLocalPath"]
        target_directory = os.path.dirname(target_file_path)
        if not os.path.exists(target_directory):
            os.makedirs(target_directory)
    while True:
        collect_node_spacific_info_update_to_control_node_or_customers()
        time.sleep(reportInterval)


# 实时流量采集上报——线程
def traffic_speed_collection_and_write_to_file():
    while True:
        traffic_speed_and_pingloss_collection()
        time.sleep(15)


# 检查控制节点是否有拨号信息的更新-线程
def check_for_control_node_updates():
    while True:
        check_for_updates_and_config()
        time.sleep(120)


if __name__ == "__main__":
    # 一次性执行
    # 1. 初始化环境部署搭建
    # 2. 创建拨号配置文件并执行拨号
    # 创建四个线程持续执行
    # 1. 重拨信息上报5-10s
    # 2. 流量采集汇报
    # 3. 自动维护路由
    # 4. 监测控制台是否有账号更新

    # 是否进行初始化
    logging.info(logo)
    if not check_run_flag(type="init"):
        logging.info("====================初始化环境部署====================")
        install_pppoe_runtime_environment()
        set_run_flag(type="init")
    else:
        logging.info("检测到系统已具备PPPoE拨号业务环境")

    # 检查是否已经创建过拨号文件
    if not check_run_flag(type="pppoe"):
        # 开始拨号前的配置
        pppoe_basicinfo = get_pppoe_basicinfo_from_control_node()
        ppp_line = pppoe_basicinfo['pppline']
        logging.info("从控制节点获取配置信息成功")
        logging.info("====================创建拨号配置文件===================")
        pppline = create_pppoe_connection_file_and_routing_tables(ppp_line)
        set_run_flag(type="pppoe")
        # 开始拨号
        logging.info("====================开始拨号...=======================")
        for ifname in pppline.keys():
            pppoe_user = pppline[ifname]['user']
            pppoe_dial_up(ifname, pppoe_user)
        time.sleep(3)
        # 写入路由
        update_pppoe_routing_table(pppline)
        # 检测互联网联通性
        for ifname in pppline.keys():
            status = get_node_status(ifname)
            if status == 1:
                logging.info(f"{ifname} 已通公网")
            else:
                logging.error(
                    f"{ifname} 未通公网，请使用命令：pppoe-status /etc/sysconfig/network-scripts/ifcfg-{ifname} 查看拨号状态,或询问运营商出网是否正常")
        # 写入首次拨号信息到硬盘，方便后续从云控制平台拉去信息与其对比，判断是否有更新
        pppline_path = os.path.join(script_path, 'pppline.json')
        with open(pppline_path, 'w', encoding='utf-8') as file:
            json.dump(pppline, file, ensure_ascii=False, indent=2)
        logging.info(success)
        # 执行完初始化就退出,后续作为服务启动
        # sys.exit(0)
    else:
        logging.info("检测到系统已存在pppoe拨号文件，后续会从服务器更新验证这些文件是否是最新的")

    # 初始化后启动线程持续运行其他后续工作线程

    threading.Thread(target=report_node_info_to_control_node_and_customer).start()
    logging.info("====================节点信息更新上报线程：已启动====================")
    threading.Thread(target=monitor_dial_connect_and_update).start()
    logging.info("====================断线重拨上报监控线程：已启动====================")
    threading.Thread(target=check_for_control_node_updates).start()
    logging.info("====================节点信息更新检查线程：已启动====================")
    threading.Thread(target=keep_pppoe_ip_routing_tables_available).start()
    logging.info("====================动态策略路由维护线程：已启动====================")
    threading.Thread(target=traffic_speed_collection_and_write_to_file).start()
    logging.info("====================网络监控数据采集上报线程：已启动================\n【程序实时日志】")

# 脚本程序的部署运行与状态反馈
# 1. 从控制平台启用，下发本程序到纳管设备执行
# 2. 程序在裸机环境中自动创建程序所需运行环境，写入系统服务，以及安装拨号相关组件
# 3. 程序开始进行拨号操作，等待拨号成功，且开始作为服务持续运行之后，本程序将返回一个退出码为0，代表成功
#   以上所有步骤（包含拨号部分的各项操作）任意环节出错，自动停止继续执行，并返回退出码为1
#   所有运行日志保存在auto_pppoe.log，运行过程中也可以通过service auto_pppoe status查看

# 拨号部分逻辑
# 1. 从控制平台获取当前机器的拨号配置信息
# 2. 根据获取到的信息将pppoe用户密码信息写入到到系统文件
# 3. 创建网卡文件，涵盖带vlan和不带vlan的两种情况：带vlan的同时创建vlan接口配置文件（更改其mac）和pppoe拨号配置文件；不带vlan的只需创建pppoe拨号配置文件（需指定mac）
# 4. 开始首轮拨号，以及拨号失败后的重拨操作（间隔1s），对于3次拨不上的，会记录到日志，然后将这些账号重拨间隔改为15s或者终止继续重拨
# 4. 根据拨号成功获取到的IP信息，写入系统策略路由
# 5. 在这之后，程序其中一个线程监控pppoe状态信息并上报，以及断线重拨操作（间隔1s），对于3次拨不上的，会记录到日志，然后将这些账号重拨间隔改为15s或者终止继续重拨
# 6. 另一个线程持续检测控制平台是否有拨号信息的更新并获取拨号（只拨号新增的，不会全部重播

#  二、 Auto_pppoe脚本程序的部署运行与状态反馈
# 1. 从控制平台启用，下发本程序到纳管设备执行
# 2. 程序在裸机环境中自动创建程序所需运行环境，写入系统服务，以及安装拨号相关组件
# 3. 程序开始进行拨号操作，等待拨号成功，且开始作为服务持续运行之后，本程序将返回一个退出              码为0，代表成功
# 以上所有步骤（包含拨号部分的各项操作）任意环节出错，自动停止继续执行，并返回退出码为1，所有运行日志保存在auto_pppoe.log，运行过程中也可以通过service auto_pppoe status查看

# 三、 Auto_pppoe拨号部分逻辑
# 1. 从控制平台获取当前机器的拨号配置信息
# 2. 创建拨号所需的软件运行环境
# 3. 根据获取到的信息将pppoe用户密码信息写入到到系统文件
# 4. 创建网卡文件，涵盖带vlan和不带vlan的两种情况：带vlan的同时创建vlan接口配置文件（更改其mac）和pppoe拨号配置文件；不带vlan的只需创建pppoe拨号配置文件（需指定mac）
# 5. 开始首轮拨号，以及拨号失败后的重拨操作（间隔1s），对于3次拨不上的，会记录到日志，然后将这些账号重拨间隔改为15s或者终止继续重拨
# 6. 根据拨号成功获取到的IP信息，写入系统策略路由
# 7. 测试每个拨号网卡的公网连通性，并记录结果
# 8. 在这之后，断线重拨监控上报线程监控pppoe状态信息并上报至平台及客户，以及断线重拨操作（间隔1s），对于3次拨不上的，会记录到日志，然后将这些账号重拨间隔改为15s或者终止继续重拨
# 9. 动态路由维护线程负责实时根据重拨的IP信息变动自动更新写入路由
# 10. 流量采集监控上报线程会采集每个拨号网卡的周期内的上下行数据并反馈至平台及客户
# 11. 获取控制平台更新线程持续检测控制平台是否有拨号信息的更新并获取拨号（只拨号新增的，不会全部重播
