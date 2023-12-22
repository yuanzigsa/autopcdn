import os
import json
import time
import threading
from datetime import datetime
import modules.data_sync as sync
import modules.init as init
from modules.logger import logging
import modules.route_keeper as route
import modules.update_check as update
import modules.monitor as monitor


# Time : 2023/12/08
# Author : yuan_zi

logo = """开始启动Auto_PPPoE脚本程序...\n
     ██               ██                  ███████    ██████  ███████   ████     ██                 ██      ██ 
    ████             ░██                 ░██░░░░██  ██░░░░██░██░░░░██ ░██░██   ░██                ███     ███ 
   ██░░██   ██   ██ ██████  ██████       ░██   ░██ ██    ░░ ░██    ░██░██░░██  ░██       ██    ██░░██    ░░██ 
  ██  ░░██ ░██  ░██░░░██░  ██░░░░██      ░███████ ░██       ░██    ░██░██ ░░██ ░██      ░██   ░██ ░██     ░██ 
 ██████████░██  ░██  ░██  ░██   ░██      ░██░░░░  ░██       ░██    ░██░██  ░░██░██      ░░██ ░██  ░██     ░██ 
░██░░░░░░██░██  ░██  ░██  ░██   ░██      ░██      ░░██    ██░██    ██ ░██   ░░████       ░░████   ░██  ██ ░██ 
░██     ░██░░██████  ░░██ ░░██████  █████░██       ░░██████ ░███████  ░██    ░░███ █████  ░░██    ████░██ ████
░░      ░░  ░░░░░░    ░░   ░░░░░░  ░░░░░ ░░         ░░░░░░  ░░░░░░░   ░░      ░░░ ░░░░░    ░░    ░░░░ ░░ ░░░░ 
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
# 创建标记
def set_run_flag(set_type, type):
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    if set_type == "env_init":
        with open('info/env_init.flag', "w") as file:
            file.write(f"这台机器已经于{current_time}部署了pcdn环境，业务Type={type}\n")
    if set_type == "net_conf":
        with open('info/net_conf.flag', "w") as file:
            file.write(f"这台已经于{current_time}创建了网络配置文件，业务Type={type}\n")


# 检查标记
def check_run_flag(check_type):
    if check_type == "env_init":
        return os.path.exists('info/env_init.flag')
    if check_type == "net_conf":
        return os.path.exists('info/net_conf.flag')


# 路由表维护-线程
def keep_pppoe_ip_routing_tables_available():
    while True:
        # 从本地获取拨号信息
        pppline = sync.read_from_json_file('pppline.json')
        route.update_routing_table(pppline)
        time.sleep(30)


# 重拨信息汇报-线程
def monitor_dial_connect_and_update():
    pppoe_basicinfo = sync.get_pppoe_basicinfo_from_control_node()
    retry_counts = {}
    # 重播次数初始化并写入文件到硬盘
    retry_counts_path = os.path.join(sync.info_path, 'retry_counts.json')
    if os.path.exists(retry_counts_path) is False:
        for ifname in pppoe_basicinfo['pppline'].keys():
            retry_counts[ifname] = 0
        with open(retry_counts_path, 'w', encoding='utf-8') as file:
            json.dump(retry_counts, file, ensure_ascii=False, indent=2)
    while True:
        sync.check_for_reconnection_and_update_to_crontrol_node()
        time.sleep(1)


# 节点综合信息上报平台及客户-线程
def report_node_info_to_control_node_and_customer():
    def_interval = 20
    pppoe_basicinfo = sync.get_pppoe_basicinfo_from_control_node()
    if pppoe_basicinfo["reported"] == 1:
        def_interval = pppoe_basicinfo["reportInterval"]
        target_file_path = pppoe_basicinfo["reportLocalPath"]
        target_directory = os.path.dirname(target_file_path)
        if not os.path.exists(target_directory):
            os.makedirs(target_directory)
    while True:
        # 记录函数开始执行的时间
        start_time = time.time()
        # 启动
        sync.collect_node_spacific_info_update_to_control_node_or_customers()
        # 计算实际执行时间
        execution_time = time.time() - start_time
        # 确保推送间隔
        next_interval = max(def_interval - execution_time, 1)
        time.sleep(next_interval)


# 拨号线路监控信息采集上报——线程
def monitor_and_push():
    def_interval = 15
    # 创建监控信息记录文件
    # 静态信息在这里采集，实时动态信息在monitor中进行采集并推送
    monitor_info = {}
    model, cores = monitor.get_cpu_info()
    monitor_info['system_info'] = monitor.get_system_info()
    monitor_info['cpu_model'] = model
    monitor_info['cpu_cores'] = cores
    logging.info(monitor_info)
    sync.write_to_json_file(monitor_info, 'monitor_info.json')


    while True:
        # 记录函数开始执行的时间
        start_time = time.time()
        # 启动
        monitor.network_and_hardware_monitor()
        # 计算实际执行时间
        execution_time = time.time() - start_time
        # 确保推送间隔
        next_interval = max(def_interval - execution_time, 1)
        time.sleep(next_interval)


# 检查控制节点是否有拨号信息的更新-线程
def check_for_control_node_updates():
    while True:
        update.check_for_updates_and_config()
        time.sleep(600)


if __name__ == "__main__":
    ##### 在这里需要判断是专线和还是拨号，并声明这个全局变量
    if 1+1 ==2:
        pcdn_type = "pppoe"  # or "static_ip"
    # 是否进行初始化
    logging.info(logo)
    if not check_run_flag("env_init"):
        logging.info("====================初始化环境部署====================")
        init.install_pppoe_runtime_environment()
        set_run_flag("env_init", pcdn_type)
    else:
        logging.info("检测到系统已具备PPPoE拨号业务环境")

    # 检查是否已经创建过拨号文件
    if not check_run_flag("net_conf"):
        # 开始拨号前的配置  # 需要新增专线的配置
        pppoe_basicinfo = sync.get_pppoe_basicinfo_from_control_node()
        ppp_line = pppoe_basicinfo['pppline']
        logging.info("从控制节点获取配置信息成功")
        logging.info("====================创建拨号配置文件===================")
        pppline = init.create_pppoe_connection_file_and_routing_tables(ppp_line)
        set_run_flag("net_conf")
        # 开始拨号
        logging.info("====================开始拨号...=======================")
        for ifname in pppline.keys():
            pppoe_user = pppline[ifname]['user']
            init.pppoe_dial_up(ifname, pppoe_user)
        time.sleep(3)
        # 写入路由
        route.update_routing_table(pppline)
        # 检测互联网联通性
        for ifname in pppline.keys():
            status = sync.get_node_status(ifname)
            if status == 1:
                logging.info(f"{ifname} 已通公网")
            else:
                logging.error(
                    f"{ifname} 未通公网，请使用命令：pppoe-status /etc/sysconfig/network-scripts/ifcfg-{ifname} 查看拨号状态,或询问运营商出网是否正常")
        # 写入首次拨号信息到硬盘，方便后续从云控制平台拉去信息与其对比，判断是否有更新
        pppline_path = os.path.join(sync.info_path, 'pppline.json')
        with open(pppline_path, 'w', encoding='utf-8') as file:
            json.dump(pppline, file, ensure_ascii=False, indent=2)
        logging.info(success)
    else:
        logging.info("检测到系统已存在pppoe拨号文件，后续会从服务器更新验证这些文件是否是最新的")

    # 初始化后启动线程持续运行其他后续工作线程
    threading.Thread(target=report_node_info_to_control_node_and_customer).start()
    logging.info("====================节点信息更新上报线程：已启动！====================")

    threading.Thread(target=monitor_dial_connect_and_update).start()
    logging.info("====================断线重拨监控上报线程：已启动！====================")

    threading.Thread(target=check_for_control_node_updates).start()
    logging.info("====================节点信息更新检查线程：已启动！====================")

    threading.Thread(target=keep_pppoe_ip_routing_tables_available).start()
    logging.info("====================动态策略路由维护线程：已启动！====================")

    threading.Thread(target=monitor_and_push).start()
    logging.info("====================运维监控数据采集线程：已启动！====================\n【程序实时日志】")



# 下一步优化线程， 线程是否存活

