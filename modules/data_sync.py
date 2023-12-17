import re
import os
import json
import time
import requests
import datetime
import subprocess
from datetime import datetime
from modules.logger import logging
from modules.pppoe_init import pppoe_dial_up


# Time : 2023/12/08
# Author : yuan_zi

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
question_headers = config_info["question_headers"]

info_path = "info"
if not os.path.exists(info_path):
    os.makedirs(info_path)
# 读取机器的唯一标识
machineTag = open(os.path.join(info_path, 'machineTag.info'), 'r').read().replace('\n', '')


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
            logging.info("已将最新pppoe拨号线路监控信息推送至控制平台")
        else:
            logging.error(f"更新pppoe拨号线路监控信息失败，错误信息：{response.text}")
    except requests.RequestException as e:
        logging.error("更新pppoe拨号线路监控信息失败，错误信息：%s", str(e))


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


# 节点具体信息上报到控制节点
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
    retry_counts_path = os.path.join(info_path, 'retry_counts.json')
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
    pppoe_basicinfo_path = os.path.join(info_path, 'pppoe_basicinfo.json')
    with open(pppoe_basicinfo_path, 'w', encoding='utf-8') as file:
        json.dump(pppoe_basicinfo_for_customers, file, ensure_ascii=False, indent=2)
