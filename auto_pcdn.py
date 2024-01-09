import os
import sys
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


##############################################################
# author：yuanzi
# Date：Dec. 8th, 2023
# Version：1.2
##############################################################

logo = f"""开始启动AutoPCDN程序...\n
     ██               ██                  ███████    ██████  ███████   ████     ██
    ████             ░██                 ░██░░░░██  ██░░░░██░██░░░░██ ░██░██   ░██
   ██░░██   ██   ██ ██████  ██████       ░██   ░██ ██    ░░ ░██    ░██░██░░██  ░██
  ██  ░░██ ░██  ░██░░░██░  ██░░░░██      ░███████ ░██       ░██    ░██░██ ░░██ ░██
 ██████████░██  ░██  ░██  ░██   ░██      ░██░░░░  ░██       ░██    ░██░██  ░░██░██
░██░░░░░░██░██  ░██  ░██  ░██   ░██      ░██      ░░██    ██░██    ██ ░██   ░░████
░██     ░██░░██████  ░░██ ░░██████  █████░██       ░░██████ ░███████  ░██    ░░███
░░      ░░  ░░░░░░    ░░   ░░░░░░  ░░░░░ ░░         ░░░░░░  ░░░░░░░   ░░      ░░░ 

【程序版本】：v1.2   
【更新时间】：2023/12/23
【系统信息】：{monitor.get_system_info()}  
【CPU 信息】：{monitor.get_cpu_info()[0]}  {monitor.get_cpu_info()[1]} cores
【内存总量】：{monitor.get_total_memory_gb()}GB
【当前路径】：{os.getcwd()}
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

# 专线ip是否带vlan
def static_ip_with_vlan(net_line_conf):
    for ifname in net_line_conf:
        for key in  net_line_conf[ifname]:
            if "vlan" in key:
                return True
            else:
                return False

# 判断是专线还是拨号
def check_pcdn_type(net_line_conf):
    # 在这里需要判断是专线和还是拨号，并声明这个全局变量
    for ifname in net_line_conf:
        for key in  net_line_conf[ifname]:
            if "user" in key:
                pcdn_type = "pppoe"
                return pcdn_type
            elif "ip" in key:
                pcdn_type = "static_ip"
                return pcdn_type
            break
        break

# 动态策略路由维护-线程
def keep_pppoe_ip_routing_tables_available():
    while True:
        try:
            # 从本地获取拨号信息
            pppline = sync.read_from_json_file('pppline.json')
            route.update_routing_table(pppline)
            time.sleep(60)
        except Exception as e:
            logging.error(f"动态策略路由维护线程出错，错误信息：{e}，正在尝试重新启动")
            time.sleep(1)


# 断线重拨监控上报-线程
def monitor_dial_connect_and_update():
    pppoe_basicinfo = sync.get_pppoe_basicinfo_from_control_node()
    retry_counts = {}
    # 重播次数初始化并写入文件到硬盘
    retry_counts_path = os.path.join(sync.info_path, 'retry_counts.json')
    if os.path.exists(retry_counts_path) is False:
        for ifname in pppoe_basicinfo['pppline'].keys():
            retry_counts[ifname] = 0
        sync.write_to_json_file("retry_counts.json")
    while True:
        try:
            sync.check_for_reconnection_and_update_to_crontrol_node()
            time.sleep(1)
        except Exception as e:
            logging.error(f"断线重拨监控上报线程出错，错误信息：{e}, 正在尝试重新启动")
            time.sleep(1)


# 节点信息更新上报线程-线程
def report_node_info_to_control_node_and_customer():
    if pcdn_basicinfo["reported"] == 1:
        def_interval = pcdn_basicinfo["reportInterval"]
        target_file_path = pcdn_basicinfo["reportLocalPath"]
        target_directory = os.path.dirname(target_file_path)
        if os.path.exists(target_directory) is False:
            os.makedirs(target_directory)
        while True:
            try:
                # 记录函数开始执行的时间
                start_time = time.time()
                # 启动
                sync.collect_node_spacific_info_update_to_control_node_or_customers(pcdn_basicinfo["reported"], target_file_path, pcdn_basicinfo, pcdn_type)
                # 计算实际执行时间
                execution_time = time.time() - start_time
                # 确保推送间隔
                next_interval = max(def_interval - execution_time, 1)
                time.sleep(next_interval)
            except Exception as e:
                logging.error(f"节点信息更新上报线程出错，错误信息：{e}, 正在尝试重新启动")
                time.sleep(1)
    else:
        logging.info("节点信息无需更新上报到客户，已停止节点信息更新上报线程")
        pass


# 运维监控数据采集上报——线程
def monitor_and_push():
    def_interval = 60
    # 创建监控信息记录文件
    # 静态信息在这里采集，实时动态信息在monitor中进行采集并推送
    monitor_info = {}
    model, cores = monitor.get_cpu_info()
    monitor_info['system_info'] = monitor.get_system_info()
    monitor_info['cpu_model'] = model
    monitor_info['cpu_cores'] = cores
    sync.write_to_json_file(monitor_info, 'monitor_info.json')
    while True:
        try:
            # 记录函数开始执行的时间
            start_time = time.time()
            # 启动
            monitor.network_and_hardware_monitor(pcdn_type)
            # 计算实际执行时间
            execution_time = time.time() - start_time
            # 确保推送间隔
            next_interval = max(def_interval - execution_time, 1)
            time.sleep(next_interval)
        except Exception as e:
            logging.error(f"运维监控数据采集上报线程出错，错误信息：{e}, 正在尝试重新启动")
            time.sleep(1)


# 节点配置更新检查-线程
def check_for_control_node_updates():
    while True:
        try:
            update.check_for_updates_and_config()
            time.sleep(600)
        except Exception as e:
            logging.error(f"节点配置更新检查线程出错，错误信息：{e}, 正在尝试重新启动")
            time.sleep(1)


# 执行线程任务
def start_thread(target_function, thread_name):
    # 创建线程对象并设置守护线程
    thread = threading.Thread(target=target_function, name=thread_name)
    # 启动线程
    thread.start()
    # 记录日志
    logging.info(f"===================={thread_name}线程：已启动！====================")



if __name__ == "__main__":
    # 启动logo
    logging.info(logo)
    # 从控制节点获取信息
    pcdn_basicinfo = sync.get_pppoe_basicinfo_from_control_node()
    net_line_conf = pcdn_basicinfo['pppline']
    logging.info("从控制节点获取信息成功！")
    if net_line_conf is None:
       logging.error("从控制节点获取的网络配置信息为空，请在控制平台检查关于本机器的网络配置！")
       sys.exit(1)
    # 获取pcdn类型
    pcdn_type = check_pcdn_type(net_line_conf)
    logging.info(f"本机的网络类型为：[{pcdn_type}]")
    if pcdn_type is None:
        logging.info("未知的pcdn类型，在控制平台检查关于本机器的网络配置！")
        sys.exit(1)

    # 是否进行初始化
    if check_run_flag("env_init") is False:
        logging.info("====================初始化环境部署====================")
        init.install_pcdn_runtime_environment(pcdn_type)
        set_run_flag("env_init", pcdn_type)
    else:
        logging.info("检测到系统已具备PCDN业务环境")

    # 配置网络前，检查是否已经创建过网络配置文件
    if check_run_flag("net_conf") is False:
        # PPPoE的网络配置
        if pcdn_type == "pppoe":
            logging.info("====================创建拨号配置文件===================")
            pppline = init.create_pppoe_connection_file_and_routing_tables(net_line_conf)
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
                if sync.get_node_status(ifname) == 1:
                    logging.info(f"{ifname} 已通公网")
                else:
                    logging.error(f"{ifname} 未通公网，请使用命令：pppoe-status /etc/sysconfig/network-scripts/ifcfg-{ifname} 查看连接状态,或询问运营商出网是否正常")
            # 写入首次拨号信息到硬盘，方便后续从云控制平台拉去信息与其对比，判断是否有更新
            sync.write_to_json_file(pppline, 'pppline.json')

        # 固定IP的网络配置
        if pcdn_type == "static_ip":
            logging.info("====================创建网络配置文件===================")
            if static_ip_with_vlan(net_line_conf) is True:
                init.create_static_ip_connection_file_and_routing_tables(net_line_conf)
                # 写入路由
                route.write_routing_rules(net_line_conf)
                # 检测互联网连通性
                for line in net_line_conf.keys():
                    ifname = f"{net_line_conf[line]['eth']}.{net_line_conf[line]['vlan']}"
                    if sync.get_node_status(ifname) == 1:
                        logging.info(f"{ifname} 已通公网")
                    else:
                        logging.error(f"{ifname} 未通公网，请使用命令：ifconfig {ifname} 查看连接状态,或询问运营商出网是否正常")
                sync.write_to_json_file(net_line_conf, 'net_conf.json')
            else:
                logging.info("检测到本机为不带vlan的专线IP网络，无需进行网络配置")
            # 写入网络配置信息到硬盘，方便后续从云控制平台拉去信息与其对比，判断是否有更新
            sync.write_to_json_file(net_line_conf, 'pppline.json')
        # 网络配置完成打上标记
        logging.info(success)
        set_run_flag("net_conf", pcdn_type)
    else:
        logging.info("检测到系统已进行过网络配置，后续会定时从控制节点获取更新")

    # 初始化后启动线程持续运行其他后续工作线程
    # 那其实也就是说，后面如果加入了固定ip的业务，下面某些线程其实是不用启动的
    if pcdn_type == "pppoe":
        start_thread(monitor_dial_connect_and_update, '断线重拨监控上报')
        start_thread(keep_pppoe_ip_routing_tables_available, '动态策略路由维护')
    start_thread(check_for_control_node_updates, '节点配置更新检查')
    start_thread(report_node_info_to_control_node_and_customer, '节点信息更新上报')
    start_thread(monitor_and_push, '运维监控数据采集')

    # start_thread(report_node_info_to_control_node_and_customer, '节点信息更新上报')
    # start_thread(monitor_dial_connect_and_update, '断线重拨监控上报')
    # start_thread(check_for_control_node_updates, '节点配置更新检查')
    # start_thread(keep_pppoe_ip_routing_tables_available, '动态策略路由维护')
    # start_thread(monitor_and_push, '运维监控数据采集')