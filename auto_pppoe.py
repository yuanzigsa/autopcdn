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
import logging
import subprocess
import concurrent.futures
from datetime import datetime
from logging.handlers import TimedRotatingFileHandler

# 控制节点基础信息获取与推送的API接口
get_pppoe_basicinfo_api_url = "http://122.191.108.42:9119/orion/expose-api/machine-info/get-config"
update_pppline_api_url = "http://122.191.108.42:9119/orion/expose-api/machine-info/update-pppline"
update_dial_connect_api_url = "http://122.191.108.42:9119/orion/expose-api/machine-info/update-dial-connect"
question_headers = {"O-Login-Token": "accessToken","accessToken": "ops_access"}
machineTag = open('/opt/script/machineTag.info', 'r').read().replace('\n', '')

# 配置日志以方便维护
# log_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'auto_pppoe.log')
# file_handler = TimedRotatingFileHandler(log_file, when="midnight", interval=1, backupCount=30, encoding='utf-8')
# file_handler.suffix = "%Y%m%d"
# file_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
# file_handler.setLevel(logging.INFO)
# logging.getLogger().addHandler(file_handler)

# 配置日志以方便维护
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
file_handler = logging.FileHandler(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'auto_pppoe.log'))
file_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
logging.getLogger().addHandler(file_handler)


def get_pppoe_basicinfo_from_control_node():
    params = {
        "machineTag": f"{machineTag}"
    }
    try:
        response = requests.get(get_pppoe_basicinfo_api_url, headers=question_headers, params=params)
        response.raise_for_status()
        response_data = response.json()
        pppoe_basicinfo = response_data.get("data", {})
        if pppoe_basicinfo is not None:
            
            return pppoe_basicinfo
        else:
            logging.error("从控制节点获取配置信息失败，返回数据为空，请检查本机系统获取的唯一标识符是否与控制节点一致！")
            sys.exit(1)
    except requests.RequestException as e:
        logging.error("从控制节点获取配置信息失败，错误信息：%s", str(e))
        sys.exit(1)


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
        sorted_interfaces = sorted([ifname for ifname in interfaces if ifname.startswith(prefix)], key=lambda x: int(''.join(filter(str.isdigit, x[len(prefix):]))))
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
        result = subprocess.run(['grep', '-E', '^nameserver', '/etc/resolv.conf'], stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
        if not result.stdout:
            subprocess.run(['sudo', 'bash', '-c', 'echo "nameserver 114.114.114.114\nnameserver 8.8.8.8" >> /etc/resolv.conf'])
            logging.info("检测到系统未配置DNS,已将DNS配置为114和8.8.8.8")

    def close_Net_workManager():
        cmd1 = "sudo systemctl stop NetworkManager"
        cmd2 = "sudo systemctl disable NetworkManager"
        subprocess.run(cmd1, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
        subprocess.run(cmd2, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
        logging.info("已经关闭NetworkManager并禁用开机自启")

    def install_package(package_name):
        logging.info(f"开始安装{package_name}...")
        try:
            subprocess.run(['sudo', 'yum', 'install', '-y', package_name], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
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

    check_configure_dns()
    close_Net_workManager()
    install_package('epel-release')
    install_package('rp-pppoe')
    install_package('vconfig')
    # install_package('docker')
    load_8021q_module()
    add_8021q_to_modules_file()

# 初始化和拨号流程运行前检查函数
# 检查标记
def check_run_flag(type):
    if type == "init":
        return os.path.exists("init.flag")
    if type == "pppoe":
        return os.path.exists("pppoe.flag")
# 创建标记
def set_run_flag(type):
    if type == "init":
        with open("init.flag", "w") as file:
            file.write("这台机器之前已部署了拨号环境，并安装了docker")
    if type == "pppoe":
        with open("pppoe.flag", "w") as file:
            file.write("这台机器之前已经创建了拨号配置文件")

def write_secrets_to_pppoe_config_file(account, secret ):
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
        ifconfig_content = f"TYPE=vlan\nPROXY_METHOD=none\nBROWSER_ONLY=no\nBOOTPROTO=static\nDEFROUTE=yes\nIPV4_FAILURE_FATAL=no\nIPV6INIT=yes\nIPV6_AUTOCONF=yes\nIPV6_DEFROUTE=yes\nIPV6_FAILURE_FATAL=no\nIPV6_ADDR_GEN_MODE=stable-privacy\nNAME={ifname}.{vlanid}\nDEVICE={ifname}.{vlanid}\nONBOOT=yes\nMACADDR={macaddr}\n"
        file_path = f'/etc/sysconfig/network-scripts/ifcfg-{ifname}.{vlanid}'
    elif file_type == "pppoe-vlan":
        ifconfig_content = f"USERCTL=yes\nBOOTPROTO=dialup\nNAME=DSL{pppoe_number}\nDEVICE={pppoe_number}\nTYPE=xDSL\nONBOOT=yes\nPIDFILE=/var/run/pppoe-ads{pppoe_number}.pid\nFIREWALL=NONE\nPING=.\nPPPOE_TIMEOUT=80\nLCP_FAILURE=3\nLCP_INTERVAL=20\nCLAMPMSS=1412\nCONNECT_POLL=6\nCONNECT_TIMEOUT=60\nDEFROUTE=no\nSYNCHRONOUS=no\nETH={ifname}.{vlanid}\nPROVIDER=DSL{pppoe_number}\nUSER={pppoe_user}\nPEERDNS=no\nDEMAND=no\n"
        file_path = f'/etc/sysconfig/network-scripts/ifcfg-{pppoe_number}'
    elif file_type == "pppoe-no-vlan":
        ifconfig_content = f"USERCTL=yes\nBOOTPROTO=dialup\nNAME=DSL{pppoe_number}\nDEVICE={pppoe_number}\nTYPE=xDSL\nONBOOT=yes\nPIDFILE=/var/run/pppoe-ads{pppoe_number}.pid\nFIREWALL=NONE\nPING=.\nPPPOE_TIMEOUT=80\nLCP_FAILURE=3\nLCP_INTERVAL=20\nCLAMPMSS=1412\nCONNECT_POLL=6\nCONNECT_TIMEOUT=60\nDEFROUTE=no\nSYNCHRONOUS=no\nETH={ifname}\nPROVIDER=DSL{pppoe_number}\nUSER={pppoe_user}\nPEERDNS=no\nDEMAND=no\n"
        file_path = f'/etc/sysconfig/network-scripts/ifcfg-{pppoe_number}'
    try:
        with open(file_path, 'w') as file:
            file.write(ifconfig_content)
        logging.info(f"{ifname}的{file_type}接口配置文件已创建")
    except Exception as e:
        logging.error(f"{ifname}的{file_type}接口配置文件创建失败，错误信息：{e}")
        sys.exit(1)

def create_routing_tables(table_number, pppoe_ifname):
    def run_command(command):
        result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
        if result.returncode != 0:
            logging.error(f"执行这条命令时出错: {command} 错误代码：{result.stderr.decode('utf-8')}")
            sys.exit(1)

    run_command(f"echo '{table_number} {pppoe_ifname}_table' >> /etc/iproute2/rt_tables")
    logging.info(f'{pppoe_ifname}接口路由表已创建')

def create_local_pppline_empty_dict():
    pppoe_basicinfo = get_pppoe_basicinfo_from_control_node()
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
        pppline_local[pppoe_ifname]['max_upbw_mbps'] = ''
        pppline_local[pppoe_ifname]['max_downbw_mbps'] = ''
        pppline_local[pppoe_ifname]['retry_count'] = 0 #计数懂啊500归零
    return pppline_local

def get_local_pppoe_ifname(pppoe_ifname):
    command = f"pppoe-status /etc/sysconfig/network-scripts/ifcfg-{pppoe_ifname}"
    try:
        result = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True, universal_newlines=True)    
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
        else:
            logging.info(f"{pppoe_ifname}未获取到IP地址，请检查拨号状态")
    except Exception as e:
        logging.exception(f"发生异常：{str(e)}")

def get_local_pppoe_ip(pppoe_ifname):
    command = f"pppoe-status /etc/sysconfig/network-scripts/ifcfg-{pppoe_ifname}"
    try:
        result = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True, universal_newlines=True)    
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
        else:
            logging.info(f"{pppoe_ifname}未获取到IP地址，请检查拨号状态")
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

def update_pppline_to_control_node(node_status,  pppline):
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    data = {
        "alarmTime": current_time,
        "machineTag": machineTag,
        "nodeStatus": node_status,
        "pppline": pppline
    }
    try:
        response = requests.post(update_pppline_api_url, headers=question_headers, json=data)
        response.raise_for_status()
        logging.info("更新pppoe在线状态信息成功")
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
        response.raise_for_status()
        logging.info("更新拨号连接信息成功")
    except requests.RequestException as e:
        logging.error("更新pppoe重连信息失败，错误信息：%s", str(e))

def get_node_status(pppoe_ifname):
    try:
        cmd = f"ping -c 2 -I {pppoe_ifname} baidu.com"
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
        if "time=" in result.stdout.decode('utf-8'):
            return 1
        else:
            return 0
    except subprocess.CalledProcessError as e:
        logging.error(f"检测节点拨号网卡互联网连通性出错：{e}")

# 监控上报-主函数
pppoe_basicinfo = get_pppoe_basicinfo_from_control_node()
node_name = pppoe_basicinfo["city"]
reportInterval = 15
report_on = pppoe_basicinfo["reported"]
if report_on == 1:
    reportInterval = pppoe_basicinfo["reportInterval"]
    reportLocalPath = pppoe_basicinfo["reportLocalPath"]

# 断线重连监测上报
def set_update_discon_flag(pppoe_ifname):
    with open(f"{pppoe_ifname}_discon.flag", "w") as file:
        file.write(f"{pppoe_ifname}断线告警标记")

def check_update_discon_flag(pppoe_ifname):
    return os.path.exists(f"{pppoe_ifname}_discon.flag")

def check_for_reconnection_and_update_to_crontrol_node():
    pppline = get_pppoe_basicinfo_from_control_node()['pppline']
    # with open('pppoe_basicinfo.json', 'w', encoding='utf-8') as file:
    #     json.dump(pppoe_basicinfo_local, file, ensure_ascii=False, indent=2)
    with open("pppoe_basicinfo.json", 'r', encoding='utf-8') as file:
        pppoe_basicinfo_local = json.load(file)
    for pppoe_ifname in pppline.keys():
        if get_local_pppoe_ip(f'{pppoe_ifname}') is None:
            type = 30
            if check_update_discon_flag(pppoe_ifname) is False:
                logging.info(f"{pppoe_ifname} 拨号网卡断线，已经上报控制节点")
                update_dial_connect_to_control_node(type, node_name, pppoe_ifname)
                set_update_discon_flag(pppoe_ifname)
        else:
            type = 40
            if check_update_discon_flag(pppoe_ifname):
                logging.info(f"{pppoe_ifname} 拨号网卡重拨成功，已经上报控制节点")
                pppoe_basicinfo_local[pppoe_ifname]["retry_counts"] += 1
                if pppoe_basicinfo_local[pppoe_ifname]["retry_counts"] > 500: #计数500归零
                    pppoe_basicinfo_local[pppoe_ifname]["retry_counts"] = 1
                # 写入重拨次数到文件，方便后续调用
                with open('pppoe_basicinfo.json', 'w', encoding='utf-8') as file:
                    json.dump(pppoe_basicinfo_local, file, ensure_ascii=False, indent=2)
                update_dial_connect_to_control_node(type, node_name, pppoe_ifname)
                os.remove(f"{pppoe_ifname}_discon.flag")

# 节点具体信息上报到控制节点 或者客户
def collect_node_spacific_info_update_to_control_node_or_customers():
    pppline_local = create_local_pppline_empty_dict()
    node_status = 0 # 默认节点不可用
    with open('pppoe_basicinfo.json', 'r', encoding='utf-8') as file:
        pppoe_basicinfo_local = json.load(file)
    for pppoe_ifname in pppline_local.keys():
        status = get_node_status(pppoe_ifname)
        if status == 1:
            node_status = 1 # 但凡有一个接口能通外网，证明节点可用..
        pppline_local[pppoe_ifname]['retry_counts'] = pppoe_basicinfo_local[pppoe_ifname]["retry_counts"]
        pppline_local[pppoe_ifname]["status"] = status
        pppline_local[pppoe_ifname]["ip"] = get_local_pppoe_ip(f'{pppoe_ifname}')
        pppline_local[pppoe_ifname]['max_upbw_mbps'] = ''
        pppline_local[pppoe_ifname]['max_downbw_mbps'] = ''
    # 上报平台
    update_pppline_to_control_node(node_status, pppline_local)
    logging.info("最新节点拨号信息已上报至平台")
    # 是否上报客户
    if report_on == 1:
        pppoe_basicinfo_for_customers = {}
        pppoe_basicinfo_for_customers['sid'] = pppoe_basicinfo['name']
        pppoe_basicinfo_for_customers['timestamp'] = int(time.time())
        for pppoe_ifname in pppline_local.keys():
            pppoe_basicinfo_for_customers['status'] = get_node_status(pppoe_ifname)
        pppoe_basicinfo_for_customers['province'] = pppoe_basicinfo['province']
        pppoe_basicinfo_for_customers['city'] = node_name
        pppoe_basicinfo_for_customers['provider'] = pppoe_basicinfo['provider']
        pppoe_basicinfo_for_customers['isp'] = pppoe_basicinfo['isp']
        pppoe_basicinfo_for_customers['nat_type'] = pppoe_basicinfo['authTye']
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
    with open("pppoe_basicinfo.json", 'w', encoding='utf-8') as file:
        json.dump(pppoe_basicinfo_for_customers, file, ensure_ascii=False, indent=2)
    

# [root@localhost ~]# pppoe-status /etc/sysconfig/network-scripts/ifcfg-ppp2
# pppoe-status: Link is attached to ppp4, but ppp4 is down

# pppline信息定时上报
# update_pppline_to_control_node(pppline)

# "pppline": {
#         "ppp0": {
#                 "status": 1,
#                 "ip": "1.1.1.1",
#                 "ssh_port": "22",
#                 "min_port": 0,
#                 "max_port": 0,
#                 "max_upbw_mbps": 100,
#                 "max_downbw_mbps": 100,
#                 "retry_count": 0
#         }
# }

# nodeStatus ping公网决定
# def get_node_status(pppoe_ifname):

# command = f"grep 'Connect: {ifname}' /var/log/messages | grep '<-->' | wc -l"
# output = os.popen(command).read()
# retry_count = int(output) - 1
# def create_pppoe_connection_file():

# 返回拨号网卡名

# 拨号前的配置-主函数
def create_pppoe_connection_file_and_routing_tables():
    get_pppoe_basicinfo_from_control_node()
    logging.info("从控制节点获取配置信息成功")
    pppoe_basicinfo = get_pppoe_basicinfo_from_control_node()
    ppp_line = pppoe_basicinfo['pppline']
    # macaddr = get_mac_address(dial_up_ifnmme)
    table_number = 50
    for pppoe_ifname in ppp_line.keys():
        pppoe_user = ppp_line[pppoe_ifname]['user']
        pppoe_pass = ppp_line[pppoe_ifname]['pass']
        pppoe_vlan = ppp_line[pppoe_ifname]['vlan']
        dial_up_ifnmme = ppp_line[pppoe_ifname]['eth']
        write_secrets_to_pppoe_config_file(pppoe_user, pppoe_pass)
        if pppoe_vlan == "0":
            logging.info(f"{pppoe_ifname}没有VLAN")
            create_ifconfig_file('pppoe-no-vlan', ifname=dial_up_ifnmme, vlanid=pppoe_vlan, pppoe_user=pppoe_user, pppoe_number=pppoe_ifname)
            create_routing_tables(table_number, pppoe_ifname)
            table_number += 1
        else:
            logging.info(f"{pppoe_ifname}所属VLAN{pppoe_vlan}")
            create_ifconfig_file('ifname-vlan', ifname=dial_up_ifnmme, vlanid=pppoe_vlan, pppoe_user=pppoe_user, pppoe_number=pppoe_ifname)
            create_ifconfig_file('pppoe-vlan', ifname=dial_up_ifnmme, vlanid=pppoe_vlan, pppoe_user=pppoe_user, pppoe_number=pppoe_ifname)
            create_routing_tables(table_number, pppoe_ifname)
            table_number += 1
            #添加Vlan
            subprocess.run([f"vconfig", "add", "pppoe_vlan"])
    return ppp_line

def pppoe_dial_up(pppoe_ifname):
    try:
        logging.info(f"{pppoe_ifname}开始拨号...")
        command = f"pppoe-connect /etc/sysconfig/network-scripts/ifcfg-{pppoe_ifname}"
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True, universal_newlines=True)
        success_flag = "succeeded"
        timeout = time.time() + 10
        while True:
            if time.time() > timeout:
                output = process.stdout.readline()
                if success_flag in output:
                    logging.info(f"{pppoe_ifname}拨号成功！")
                    break
    except subprocess.CalledProcessError as e:
        logging.error(f"{pppoe_ifname}拨号出错：{e}")
        return f"{pppoe_ifname}拨号出错：{e}"


# 自动维护路由
# 路由维护-主函数
# 优化项：先获取本机当前获取到的IP段生成集合再去路由表筛选出这个段的
def update_pppoe_routing_table(pppline):
    def get_current_route_rule_ip():
        def get_ip_rules():
            try:
                result = subprocess.check_output(["ip", "rule", "list"], universal_newlines=True)
                return result
            except subprocess.CalledProcessError as e:
                print(f"Error: {e}")
                return None
            
        def extract_ip_addresses(input_string):
            ip_pattern = r'\b(?:\d{1,3}\.){3}\d{1,3}\b'
            ip_addresses = re.findall(ip_pattern, input_string)
            return ip_addresses

        ip_rules_output = get_ip_rules()
        result = extract_ip_addresses(ip_rules_output)
        ip_list = [x for x in result if str(x).startswith('10')]
        # logging.info(f"当前路由规则中的IP地址列表：{ip_list}")
        return ip_list

    # def get_pppoe_ifname(prefix='ppp'):
    #     try:
    #         with open('/proc/net/dev') as f:
    #             interfaces = [line.split(':')[0].strip() for line in f if ':' in line]
    #             # sorted_interfaces = sorted([ifname for ifname in interfaces if ifname.startswith(prefix)],key=lambda x: int(x[len(prefix):])
    #             sorted_interfaces = sorted([ifname for ifname in interfaces if ifname.startswith(prefix)],key=lambda x: int(x[len(prefix):])
    #         )
    #         return sorted_interfaces
    #     except Exception as e:
    #         print(f"出错: {str(e)}")
    #         return None
        
    def get_ip_address(ifname):
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            ip_address = socket.inet_ntoa(fcntl.ioctl(
                sock.fileno(),
                0x8915,
                struct.pack('256s', bytes(ifname[:15], 'utf-8')))[20:24])
            return ip_address
        except Exception as e:
            logging.error(f"{ifname}：未获取到ip地址, 请检查拨号状态")
            return None
    # for ifname in get_pppoe_ifname():
    # ip_address = get_ip_address(ifname)

    def del_rules(ip, table):
        cmd = f"ip rule del from {ip} table {table}"
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
        if result.returncode != 0:
            logging.error(f"删除路由时出错: {cmd} 错误代码：{result.stderr.decode('utf-8')}")
            sys.exit(1)
        else:
            logging.info(f"删除无效IP路由路由成功: {cmd}")
    # ip rule del from 10.0.192.176 table v9
    # 这是删路由

    def add_rules(ifname, table, ip ):
        cmd1 = f"ip route add default dev {ifname} table {table}" 
        cmd2 = f"ip rule add from {ip} table {table}"
        result1 = subprocess.run(cmd1, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
        result2 = subprocess.run(cmd2, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
        if result1.returncode != 0:
            if result2.returncode != 0:
                logging.error(f"{ifname}添加新路由时出错，错误代码：{result1.stderr.decode('utf-8')}")
                sys.exit(1)
        else:
            logging.info(f"新拨号网卡：{ifname} 新获取到的IP：{ip} 添加路由成功")

    # ifname和table对应
    # ip route add default dev ppp0 table v1
    # ip rule add from 10.0.192.2 table v1
    # 这是加路由
    def get_expired_ip_router_rules(keyword):
        try:
            # result = subprocess.run(['ip', 'rule', 'list'], capture_output=True, text=True, check=True)
            result = subprocess.run(["ip", "rule", "list"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
            output_lines = result.stdout.splitlines()
            relevant_line = next((line for line in output_lines if keyword in line), None)

            if relevant_line:
                start_index = relevant_line.find('v')
                if start_index != -1:
                    extracted_content = relevant_line[start_index:]
                    return extracted_content
            return None
        except subprocess.CalledProcessError as e:
            print(f"Error: {e}")
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

    # 创建当前在线的网卡信息
    pppoe_info = {}
    for pppoe_ifname in pppline.keys():
        pppoe_info[pppoe_ifname] = {}
        pppoe_info[pppoe_ifname]['ip'] = ''
        pppoe_info[pppoe_ifname]['table'] = f'{pppoe_ifname}_table'
    
    # 获取当前在线ip列表和路由表中所包含的ip列表
    pppoe_ip_address_list = get_pppoe_ip_address_list()
    route_ipaddress_list = get_current_route_rule_ip()

    # 检测当前路由表中的是否有重复的条目有待编写

    # 删除无效路由
    route_set = set(route_ipaddress_list)
    pppoe_set = set(pppoe_ip_address_list)

    same = route_set.intersection(pppoe_set)
    expired_ip_list = route_set - same

    if route_set == pppoe_set:
        logging.info(f"当前在线IP和路由表IP条目符合，在线IP:{pppoe_ip_address_list}")
    else:
        logging.info(f"当前在线IP和路由表IP条目不符合! 即将开始删除无效IP路由和新增新拨号的IP路由")

    # 创建新拨号网卡的IP集合,其中包括了路由表ip和接口对应关系与目前不一致的
    # new_ip_list = set()
    # 路由表ip和接口对应关系与目前不一致的也要加入无效列表，避免重拨获取到的ip和原来一样的情况
    old_ip_table = from_route_rules_get_old_ip_table()
    for old_table, old_ip  in old_ip_table.items():
        ifname = find_ifnmae_by_table(pppoe_info,old_table)
        if old_ip_table[old_table] !=  pppoe_info[ifname]['ip']:
            expired_ip_list.add(old_ip_table[old_table])
            # new_ip_list.add(old_ip_table[old_table])
    for ip in expired_ip_list:
        table = get_expired_ip_router_rules(ip)
        # logging.info(f"无效路由:{ip} 对应的表项:{table}")
        del_rules(ip , table)
    if len(expired_ip_list) != 0:
        logging.info("无效路由已经全部清除")
    else:
        logging.info("目前没有无效路由")

    # 再次获取清理后的路由表
    route_set = set(route_ipaddress_list)

    #添加新拨号获取的IP路由
    new_ip_list = pppoe_set - route_set
    # new_ip_list.add(different_ip_list)

    for ip in new_ip_list:
        ifname = find_ifnmae_by_ip(pppoe_info, ip)
        table = pppoe_info[ifname]['table']
        # logging.info(f"新拨号网卡：{ifname}，所获取的新IP：{ip}, 对应路由表：{table}")
        add_rules(ifname, table, ip)
    
    if len(new_ip_list) != 0:
        logging.info(f"所有新拨号网卡获取到的IP路由已添加！")
    else:
        logging.info("目前没有新拨号网卡产生新IP")

# 检查控制平台是否存在拨号信息的更新
def check_for_updates():
    with open('pppline.json', 'r', encoding='utf-8') as file:
        pppline_local = json.load(file)
    pppline_control_node = get_pppoe_basicinfo_from_control_node()["pppline"]
    if pppline_local != pppline_control_node:
        logging.info("检测到控制节点拨号信息发生更新")
        differences = {key: (pppline_control_node[key], pppline_local[key]) for key in pppline_control_node if key in pppline_local and pppline_control_node[key] != pppline_local[key]}
        if differences:
            for ifname in differences.keys():
                print(differences)
        else:
            logging.info("控制节点拨号信息无更新")
# 判断是否存在同名接口配置文件
# 判断是否存在vlan 删除以前的配置文件
# 将新的pppline信息写入硬盘

    

# 路由表维护-线程
def keep_pppoe_ip_routing_tables_available():
    while True:
        pppline = get_pppoe_basicinfo_from_control_node()['pppline']
        update_pppoe_routing_table(pppline)
        time.sleep(5)

# 重拨信息汇报-线程
def monitor_dial_connect_and_update():
    while True:
        check_for_reconnection_and_update_to_crontrol_node()

# 节点综合信息上报平台及客户-线程
def report_node_info_to_control_node_and_customer():
    while True:
        collect_node_spacific_info_update_to_control_node_or_customers()
        time.sleep(reportInterval)

# 流量采集汇报-线程


# 检查控制节点是否有拨号信息的更新
def check_for_control_node_updates():
    while True:
        check_for_updates()
        time.sleep(10)


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
    if not check_run_flag(type="init"):
        logging.info("【初始化环境部署】")
        install_pppoe_runtime_environment()
        set_run_flag(type="init")
    else:
        logging.info("检测到系统已具备PPPoE拨号业务环境")

    # 检查是否已经创建过拨号文件
    if not check_run_flag(type="pppoe"):
        logging.info("【创建拨号配置文件】")
        pppline = create_pppoe_connection_file_and_routing_tables()
        # 开始拨号
        logging.info("【开始拨号...】")
        for ifname  in pppline.keys():
            pppoe_dial_up(ifname)
        set_run_flag(type="pppoe")
        # 写入路由
        update_pppoe_routing_table(pppline)
        # 检测互联网联通性
        for ifname in pppline.keys():
            status = get_node_status(ifname)
            if status == 1:
                logging.info(f"{ifname}已通外网")
            else:
                logging.info(f"{ifname}未能连接到互联网，请使用命令：pppoe-status /etc/sysconfig/network-scripts/ifcfg-{ifname} 查看拨号状态")
        # 写入首次拨号信息到硬盘，方便后续从云控制平台拉去信息与其对比，判断是否有更新
        with open("pppline.json", 'w', encoding='utf-8') as file:
            json.dump(pppline, file, ensure_ascii=False, indent=2)
    else:
        logging.info("检测到系统已存在pppoe拨号文件，后续会从服务器更新验证这些文件是否是最新的")

    threading.Thread(target=keep_pppoe_ip_routing_tables_available).start()
    threading.Thread(target=report_node_info_to_control_node_and_customer).start()
    threading.Thread(target=monitor_dial_connect_and_update).start()
    
    # threading.Thread(target=check_for_control_node_updates).start()

#脚本程序的部署运行与状态反馈
#1. 从控制平台启用，下发本程序到纳管设备执行
#2. 程序在裸机环境中自动创建程序所需运行环境，写入系统服务，以及安装拨号相关组件
#3. 程序开始进行拨号操作，等待拨号成功，且开始作为服务持续运行之后，本程序将返回一个退出码为0，代表成功
#   以上所有步骤（包含拨号部分的各项操作）任意环节出错，自动停止继续执行，并返回退出码为1
#   所有运行日志保存在auto_pppoe.log，运行过程中也可以通过service auto_pppoe status查看 

#拨号部分逻辑
#1. 从控制平台获取当前机器的拨号配置信息
#2. 根据获取到的信息将pppoe用户密码信息写入到到系统文件
#3. 创建网卡文件，涵盖带vlan和不带vlan的两种情况：带vlan的同时创建vlan接口配置文件（更改其mac）和pppoe拨号配置文件；不带vlan的只需创建pppoe拨号配置文件（需指定mac）
#4. 开始首轮拨号，以及拨号失败后的重拨操作（间隔1s），对于3次拨不上的，会记录到日志，然后将这些账号重拨间隔改为15s或者终止继续重拨
#4. 根据拨号成功获取到的IP信息，写入系统策略路由
#5. 在这之后，程序其中一个线程监控pppoe状态信息并上报，以及断线重拨操作（间隔1s），对于3次拨不上的，会记录到日志，然后将这些账号重拨间隔改为15s或者终止继续重拨
#6. 另一个线程持续检测控制平台是否有拨号信息的更新并获取拨号（只拨号新增的，不会全部重播





