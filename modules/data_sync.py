import re
import os
import json
import time
import requests
import datetime
import subprocess
from datetime import datetime
from modules.logger import logging
from modules.init import pppoe_dial_up
import modules.route_keeper as route


# Time : 2023/12/08
# Author : yuan_zi

# 网络和硬件监控信息在monitor模块进行上传


# 获取配置信息
try:
    with open("config/config.json", "r") as file:
        config_info = json.load(file)
except FileNotFoundError:
    print("config.json配置文件不存在")
except IOError as e:
    print("读取配置文件出错")

get_pppoe_basicinfo_api_url = config_info["get_pppoe_basicinfo_api_url"]
update_pppline_api_url = config_info["update_pppline_api_url"]
update_dial_connect_api_url = config_info["update_dial_connect_api_url"]
update_pppline_monitor_info_api_url = config_info["update_pppline_monitor_info_api_url"]
update_monitor_info_api_url = config_info["update_monitor_info_api_url"]
question_headers = config_info["question_headers"]

info_path = "info"
if not os.path.exists(info_path):
    os.makedirs(info_path)
# 读取机器的唯一标识
machineTag = open(os.path.join(info_path, 'machineTag.info'), 'r').read().replace('\n', '')

# 写json文件
def write_to_json_file(value, file):
    path = os.path.join("info", file)
    with open(path, 'w', encoding='utf-8') as file:
        json.dump(value, file, ensure_ascii=False, indent=2)


# 读json文件
def read_from_json_file(file):
    path = os.path.join("info", file)
    with open(path, 'r', encoding='utf-8') as file:
        value = json.load(file)
    return value

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


def update_local_operate_to_control_node(node_status, info, operate):
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    data = {
        "alarmTime": current_time,
        "machineTag": machineTag,
        "nodeStatus": node_status,
        "pppline": info
    }
    try:
        response = requests.post(update_pppline_api_url, headers=question_headers, json=data)
        if "200" in response.text:
            logging.info(f"已将{operate}操作上报至平台")
        else:
            logging.error("更新机器操作动态信息失败，错误信息：{response.text}")
    except requests.RequestException as e:
        logging.error("更新机器操作动态信息失败，错误信息：%s", str(e))


def update_pppline_monitor_to_control_node(pppline_monitor_info):
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    data = {
        "machineTag": machineTag,
        "monitorInfo": pppline_monitor_info,
        "reportTime": current_time
    }
    try:
        response = requests.post(update_monitor_info_api_url, headers=question_headers, json=data)
        if "200" in response.text:
            logging.info("已将最的线路监控信息推送至控制平台")
        else:
            logging.error(f"更新线路监控信息失败，错误信息：{response.text}")
    except requests.RequestException as e:
        logging.error("更新线路监控信息失败，错误信息：%s", str(e))



def update_monitor_info_to_control_node(monitor_info):
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    data = {
        "machineTag": machineTag,
        "monitorInfo": monitor_info,
        "reportTime": current_time
    }
    try:
        response = requests.post(update_monitor_info_api_url, headers=question_headers, json=data)
        if "200" in response.text:
            logging.info("已将最新网络和硬件监控信息推送至控制平台")
        else:
            logging.error(f"更新网络和硬件监控信息失败，错误信息：{response.text}")
    except requests.RequestException as e:
        logging.error("更新网络和硬件监控信息失败，错误信息：%s", str(e))



def update_dial_connect_to_control_node(type, node_name, pppoe_ifname, pppoe_user):
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    if type == 30:
        info = f"{node_name}节点机器-{machineTag}：{pppoe_ifname}({pppoe_user})拨号断线"
    if type == 40:
        info = f"{node_name}节点机器-{machineTag}：{pppoe_ifname}({pppoe_user})拨号重连成功"
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


def get_node_status(ifname):
    try:
        cmd = f"fping -I {ifname} baidu.com"
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
        if "alive" in result.stdout.decode('utf-8'):
            return 1
        else:
            return 0
    except subprocess.CalledProcessError as e:
        logging.error(f"检测节点拨号网卡互联网连通性出错：{e}")


# 断线重连监测上报-主函数
def set_update_discon_flag(pppoe_ifname):
    discon_flag_path = os.path.join(info_path, f'{pppoe_ifname}_discon.flag')
    with open(discon_flag_path, "w") as file:
        file.write(f"{pppoe_ifname}断线告警标记")


def check_update_discon_flag(pppoe_ifname):
    discon_flag_path = os.path.join(info_path, f'{pppoe_ifname}_discon.flag')
    return os.path.exists(discon_flag_path)


def check_pppoe_connect_process_exists(pppoe_ifname):
    cmd = "ps aux | grep pppoe-connect"
    result = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True, universal_newlines=True)
    stdout, stderr = result.communicate()
    if f"ifcfg-{pppoe_ifname}" in stdout:
        return True
    else:
        return False

# 拨号重连信息更新上传到控制节点
def check_for_reconnection_and_update_to_crontrol_node():

    pppoe_basicinfo = get_pppoe_basicinfo_from_control_node()
    node_name = pppoe_basicinfo["city"]
    pppline = pppoe_basicinfo['pppline']
    retry_counts_path = os.path.join(info_path, 'retry_counts.json')
    with open(retry_counts_path, 'r', encoding='utf-8') as file:
        retry_counts = json.load(file)
    for pppoe_ifname in pppline.keys():
        if get_local_pppoe_ip(f'{pppoe_ifname}') is None:
            type = 30
            pppoe_user = pppline[pppoe_ifname]['user']
            if check_update_discon_flag(pppoe_ifname) is False:
                update_dial_connect_to_control_node(type, node_name, pppoe_ifname, pppoe_user)
                set_update_discon_flag(pppoe_ifname)
                logging.info(f"{pppoe_ifname}({pppoe_user}) 检测到拨号网卡断线，已经上报控制节点")
            # 检测pppoe-connect进程是否存在，避免一号多拨
            if check_pppoe_connect_process_exists(pppoe_ifname) is False:
                logging.info(f"检测到{pppoe_ifname}({pppoe_user})的pppoe-connect驻守进程已经不存在，即将重新进行拨号...")
                pppoe_dial_up(pppoe_ifname, pppoe_user)
        else:
            type = 40
            pppoe_user = pppline[pppoe_ifname]['user']
            if check_update_discon_flag(pppoe_ifname):
                logging.info(f"{pppoe_ifname} 检测到拨号网卡已经重连，已经上报控制节点")
                # 立即更新路由
                route.update_routing_table(pppline)

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
                update_dial_connect_to_control_node(type, node_name, pppoe_ifname, pppoe_user)
                os.remove(f"info/{pppoe_ifname}_discon.flag")


# 节点具体信息上报到控制节点
def collect_node_spacific_info_update_to_control_node_or_customers(report_on, reportLocalPath, pcdn_basicinfo, pcdn_type):
    def create_local_netline_info(pcdn_basicinfo):
        netline = pcdn_basicinfo['pppline']
        # 创建本地字典netline
        netline_local = {}
        for line in netline.keys():
            # netline_local
            netline_local[line] = {}
            netline_local[line]['status'] = ''
            if pcdn_type == 'static_ip':
                netline_local[line]['ip'] = netline[line]['ip']
                netline_local[line]['eth'] = netline[line]['eth']
            netline_local[line]['ssh_port'] = '22'
            netline_local[line]['min_port'] = 0
            netline_local[line]['max_port'] = 0
            netline_local[line]['max_upbw_mbps'] = int(netline[line]['bandwidth'])
            netline_local[line]['max_downbw_mbps'] = int(netline[line]['bandwidth'])
            netline_local[line]['disabled'] = netline[line]['disabled']
        return netline_local


    # 创建初始上报客户的节点固定更新信息，后续直接从本地获取
    def create_pcdn_basicinfo_for_customers(node_status, netline_local):
        pcdn_basicinfo_for_customers = {}
        pcdn_basicinfo_for_customers['sid'] = pcdn_basicinfo['name']
        pcdn_basicinfo_for_customers['timestamp'] = int(time.time())
        pcdn_basicinfo_for_customers['status'] = node_status
        pcdn_basicinfo_for_customers['city'] = pcdn_basicinfo["city"]
        pcdn_basicinfo_for_customers['province'] = pcdn_basicinfo['province']
        pcdn_basicinfo_for_customers['isp'] = pcdn_basicinfo['isp']
        pcdn_basicinfo_for_customers['nat_type'] = pcdn_basicinfo['natType']
        pcdn_basicinfo_for_customers['provider'] = pcdn_basicinfo['provider']
        pcdn_basicinfo_for_customers['upstreambandwidth'] = pcdn_basicinfo['upstreambandwidth']
        pcdn_basicinfo_for_customers['linecount'] = pcdn_basicinfo['linecount']
        pcdn_basicinfo_for_customers['cpu'] = pcdn_basicinfo['cpu']
        pcdn_basicinfo_for_customers['memory'] = pcdn_basicinfo['memory']
        pcdn_basicinfo_for_customers['pppline'] = {}
        pcdn_basicinfo_for_customers['pppline'] = netline_local
        for line in pcdn_basicinfo_for_customers['pppline']:
            del pcdn_basicinfo_for_customers['pppline'][line]['disabled']
            del pcdn_basicinfo_for_customers['pppline'][line]['eth']
        return pcdn_basicinfo_for_customers, node_status

    # 按照要求完善推送给客户的信息
    def update_pcdn_basicinfo_for_costumers(pcdn_basicinfo):
        node_status = 0  # 默认节点状态不可用
        # 读取节点基础信息并创建本地数据记录文件
        netline_local = create_local_netline_info(pcdn_basicinfo)
        if pcdn_type == "pppoe":
            # 读取拨号网卡的重拨次数
            retry_counts = read_from_json_file("retry_counts.json")
            for pppoe_ifname in netline_local.keys():
                node_status = get_node_status(pppoe_ifname)
                if netline_local[pppoe_ifname]['disabled'] == 0:
                    node_status = 0
                # 创建上报控制节点必要更新信息
                netline_local[pppoe_ifname]["status"] = node_status
                netline_local[pppoe_ifname]["ip"] = get_local_pppoe_ip(f'{pppoe_ifname}')
                netline_local[pppoe_ifname]['retry_count'] = retry_counts[pppoe_ifname]

        if pcdn_type == "static_ip":
            for line in netline_local.keys():
                ifname = pcdn_basicinfo['pppline'][line]['eth']
                node_status = get_node_status(ifname)
                if netline_local[line]['disabled'] == 0:
                    node_status = 0
                netline_local[line]["status"] = node_status
                netline_local[line]["ip"] = netline_local[line]["ip"]
                netline_local[line]['retry_count'] = 0


            for line in netline_local.keys():
                ifname = pcdn_basicinfo['pppline'][line]['eth']
                netline_local[ifname] ={}
                netline_local[ifname] = netline_local[line]
                print(netline_local)
                netline_local[line].clear()
                print(netline_local)

        # 返回客户需要的信息
        return create_pcdn_basicinfo_for_customers(node_status, netline_local)


    # 更新本地数据信息给客户
    def update_pcdn_basicinfo_local_for_costumers(pcdn_basicinfo):
        node_status = 0  # 默认节点状态不可用
        # 读取本地文件
        pcdn_basicinfo['timestamp'] = int(time.time())
        netline_local = pcdn_basicinfo['pppline']

        if pcdn_type == "pppoe":
            # 读取拨号网卡的重拨次数
            retry_counts = read_from_json_file("retry_counts.json")
            for pppoe_ifname in netline_local.keys():
                node_status = get_node_status(pppoe_ifname)
                if netline_local[pppoe_ifname]['disabled'] == 0:
                    node_status = 0
                # 创建上报控制节点必要更新信息
                netline_local[pppoe_ifname]['retry_counts'] = retry_counts[pppoe_ifname]
                netline_local[pppoe_ifname]["status"] = node_status
                netline_local[pppoe_ifname]["ip"] = get_local_pppoe_ip(f'{pppoe_ifname}')

        if pcdn_type == "static_ip":
            for line in netline_local.keys():
                ifname = pcdn_basicinfo['pppline'][line]['eth']
                node_status = get_node_status(ifname)
                if netline_local[line]['disabled'] == 0:
                    node_status = 0
                netline_local[line]["status"] = node_status
                netline_local[line]["ip"] = netline_local[line]["ip"]

        # 返回客户需要的信息
        return pcdn_basicinfo, node_status

    # 上报给客户
    def report_customer(data):
        with open(reportLocalPath, 'w', encoding='utf-8') as file:
            json.dump(data, file, ensure_ascii=False, indent=2)
        logging.info("已经向客户更新推送了最新的拨号状态信息")


    # 是否上报客户
    if report_on == 1:
        # 从本地文件获取信息，避免频繁请求控制节点
        pcdn_basicinfo_path = os.path.join(info_path, 'pcdn_basicinfo.json')
        if os.path.exists(pcdn_basicinfo_path) is True:
            logging.debug("本地有pcdn_basicinfo信息，读取本地文件修改动态信息进行上传")
            # 本地有文件直接读取修改动态的数值并上报
            pcdn_basicinfo_local = read_from_json_file("pcdn_basicinfo.json")
            # pcdn_basicinfo_for_customers, node_status = update_pcdn_basicinfo_local_for_costumers(pcdn_basicinfo_local)
            pcdn_basicinfo_for_customers, node_status = update_pcdn_basicinfo_for_costumers(pcdn_basicinfo_local)
        else:
            # 本地没有文件则进行创建
            logging.debug("本地没有pcdn_basicinfo信息，即将进行创建")
            pcdn_basicinfo_for_customers, node_status = update_pcdn_basicinfo_for_costumers(pcdn_basicinfo)
            # 存储一份到本地
            write_to_json_file(pcdn_basicinfo, "pcdn_basicinfo.json")

        # 上报给客户
        report_customer(pcdn_basicinfo_for_customers)
        # 告诉平台已经上报了客户
        update_local_operate_to_control_node(node_status, '已经将最新线路信息推送至客户', '线路信息上报至客户')











