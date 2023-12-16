import os
import json
import time
import threading
from modules.logger import logging
from modules.pppoe_init import pppoe_dial_up
from modules.data_sync import get_node_status
from modules.route_keeper import update_pppoe_routing_table
from modules.network_monitor import traffic_speed_and_pingloss_collection
from modules.update_check import check_for_updates_and_config
from modules.pppoe_init import install_pppoe_runtime_environment
from modules.pppoe_init import create_pppoe_connection_file_and_routing_tables
from modules.data_sync import get_pppoe_basicinfo_from_control_node, info_path
from modules.data_sync import check_for_reconnection_and_update_to_crontrol_node
from modules.data_sync import collect_node_spacific_info_update_to_control_node_or_customers

# Time : 2023/12/08
# Author : yuan_zi

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


# 初始化和拨号流程运行前检查函数
# 检查标记
def check_run_flag(check_type):
    if check_type == "init":
        return os.path.exists(f'{info_path}/init.flag')
    if check_type == "pppoe":
        return os.path.exists(f'{info_path}/pppoe.flag')


# 创建标记
def set_run_flag(set_type):
    if set_type == "init":
        with open((os.path.join(os.path.dirname(os.path.abspath(__file__)), 'init.flag')), "w") as file:
            file.write("这台机器之前已部署了拨号环境，并安装了docker")
    if set_type == "pppoe":
        with open((os.path.join(os.path.dirname(os.path.abspath(__file__)), 'pppoe.flag')), "w") as file:
            file.write("这台机器之前已经创建了拨号配置文件")


# 路由表维护-线程
def keep_pppoe_ip_routing_tables_available():
    while True:
        # 从本地获取拨号信息
        pppline_path = os.path.join(info_path, 'pppline.json')
        with open(pppline_path, 'r', encoding='utf-8') as file:
            pppline = json.load(file)
        update_pppoe_routing_table(pppline)
        time.sleep(15)


# 重拨信息汇报-线程
def monitor_dial_connect_and_update():
    pppoe_basicinfo = get_pppoe_basicinfo_from_control_node()
    retry_counts = {}
    # 重播次数初始化并写入文件到硬盘
    retry_counts_path = os.path.join(info_path, 'retry_counts.json')
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
    report_interval = 14
    pppoe_basicinfo = get_pppoe_basicinfo_from_control_node()
    if pppoe_basicinfo["reported"] == 1:
        interval = pppoe_basicinfo["reportInterval"]
        report_interval = interval - 1
        target_file_path = pppoe_basicinfo["reportLocalPath"]
        target_directory = os.path.dirname(target_file_path)
        if not os.path.exists(target_directory):
            os.makedirs(target_directory)
    while True:
        collect_node_spacific_info_update_to_control_node_or_customers()
        time.sleep(report_interval)


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
    if not check_run_flag("init"):
        logging.info("====================初始化环境部署====================")
        install_pppoe_runtime_environment()
        set_run_flag("init")
    else:
        logging.info("检测到系统已具备PPPoE拨号业务环境")

    # 检查是否已经创建过拨号文件
    if not check_run_flag("pppoe"):
        # 开始拨号前的配置

        pppoe_basicinfo = get_pppoe_basicinfo_from_control_node()
        ppp_line = pppoe_basicinfo['pppline']
        logging.info("从控制节点获取配置信息成功")
        logging.info("====================创建拨号配置文件===================")
        pppline = create_pppoe_connection_file_and_routing_tables(ppp_line)
        set_run_flag("pppoe")
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
        pppline_path = os.path.join(info_path, 'pppline.json')
        with open(pppline_path, 'w', encoding='utf-8') as file:
            json.dump(pppline, file, ensure_ascii=False, indent=2)
        logging.info(success)
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


