import re
import json
import time
import psutil
import platform
import threading
import subprocess
from pysnmp.hlapi import *
import modules.data_sync as sync
from modules.logger import logging



# Time : 2023/12/08
# Author : yuan_zi


# 获取系统信息
def get_system_info():
    system_info = platform.platform()
    return system_info


# 获取系统运行时间
def get_uptime():
    boot_time = psutil.boot_time()
    uptime_seconds = int(time.time() - boot_time)
    uptime_str = time.strftime("%d days, %H:%M:%S", time.gmtime(uptime_seconds))
    return uptime_str


# 获取cpu信息
def get_cpu_info():
    try:
        with open('/proc/cpuinfo', 'r') as file:
            for line in file:
                if line.strip().startswith("model name"):
                    cpu_model = line.split(":")[1].strip()
                    # cpu_info = f"Model: {cpu_model}"
                    break
    except FileNotFoundError:
        pass

    cpu_cores = psutil.cpu_count(logical=False)
    # cpu_usage = psutil.cpu_percent(interval=1)
    return cpu_model, cpu_cores

# 获取cpu使用率
def get_cpu_useage():
    cpu_usage = psutil.cpu_percent(interval=1)
    return cpu_usage

def get_memory_info():
    memory = psutil.virtual_memory()
    return memory.total, memory.used, memory.percent


def get_total_memory_gb():
    memory_info = psutil.virtual_memory()
    total_memory_bytes = memory_info.total
    total_memory_gb = round(total_memory_bytes / (1024 ** 3))
    return total_memory_gb

def get_disk_io():
    disk_io_before = psutil.disk_io_counters()
    time.sleep(1)  # 等待1s
    disk_io_after = psutil.disk_io_counters()

    read_speed = disk_io_after.read_bytes - disk_io_before.read_bytes
    write_speed = disk_io_after.write_bytes - disk_io_before.write_bytes

    return read_speed, write_speed

# 获取硬盘空间
def get_disk_space():
    def is_interesting_partition(partition):
        # 过滤掉容量为0的挂载点和一些不常用的挂载点
        return (
                partition.fstype
                and partition.opts != 'swap'
                and psutil.disk_usage(partition.mountpoint).total > 0
        )

    visited_mount_points = set() # 用于去重
    partitions = psutil.disk_partitions(all=True)
    # 创建磁盘挂载点信息字典
    mount_points_info = {}

    for partition in partitions:
        if (is_interesting_partition(partition)and partition.mountpoint not in visited_mount_points): # 去重
            mount_point = partition.mountpoint
            try:
                partition_usage = psutil.disk_usage(mount_point)
                if partition_usage.used > 0:
                    mount_points_info[mount_point] = {}
                    mount_points_info[mount_point]['total'] = partition_usage.total
                    mount_points_info[mount_point]['used'] = partition_usage.used
                    mount_points_info[mount_point]['useage'] = partition_usage.percent
                    # print(f'Mount Point: {mount_point}')
                    # print(f'Total disk space: {partition_usage.total / (1024 ** 3):.2f} GB')
                    # print(f'Used disk space: {partition_usage.used / (1024 ** 3):.2f} GB')
                    # print(f'Disk usage: {partition_usage.percent}%\n')
                    visited_mount_points.add(mount_point)
            except Exception as e:
                logging.error(f'读取磁盘挂载点{mount_point}信息错误: {e}')
    return  mount_points_info

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
    monitor_info = sync.read_from_json_file('monitor_info.json')
    for ifname in monitor_info['line'].keys():
        online_ifname = get_local_pppoe_ifname(ifname)
        monitor_info['line'][ifname]['current_max_upbw_mbps'] = round(interface_out_rates.get(online_ifname, 0.00) * 8 / 1000000, 2)
        # logging.info(f"{ifname}({monitor_info['line'][ifname]['pppoe_user']})实时上行速率：{monitor_info['line'][ifname]['current_max_upbw_mbps']}mbps")
        monitor_info['line'][ifname]['current_max_downbw_mbps'] = round(interface_in_rates.get(online_ifname, 0.00) * 8 / 1000000, 2)
        # logging.info(f"{ifname}({monitor_info['line'][ifname]['pppoe_user']})实时下行速率：{monitor_info['line'][ifname]['current_max_downbw_mbps']}mbps")
    # 将字典写入本地文件
    sync.write_to_json_file(monitor_info, 'monitor_info.json')
    # 输出概况日志
    upbw_list = [values['current_max_upbw_mbps'] for values in monitor_info['line'].values()]
    max_upbw = max(upbw_list)
    min_upbw = min(upbw_list)
    avg_upbw = round(sum(upbw_list) / len(upbw_list), 2)
    downbw_list = [values['current_max_downbw_mbps'] for values in monitor_info['line'].values()]
    max_downbw = max(downbw_list)
    min_downbw = min(downbw_list)
    avg_downbw = round(sum(downbw_list) / len(downbw_list), 2)
    logging.info(f"实时上下行数据采集完成！")
    logging.info(f"当前所有线路上行数据：[平均值：{avg_upbw}mbps, 最大值：{max_upbw}mbps, 最小值：{min_upbw}mbps]")
    logging.info(f"当前所有线路下行数据：[平均值：{avg_downbw}mbps, 最大值：{max_downbw}mbps, 最小值：{min_downbw}mbps]")


def get_pingloss_and_rtt():
    # 继续优化的方向就是将ping结果先存入字典，然后进行排序后输出，目前多线程结果输出是乱序的
    # fping -I eth0 -c 4 -q 8.8.8.8 8.8.4.4
    def ping_check(pppoe_ifname, local_pppoe_ifname):
        command = f"ping -i 0.5 -c 20 -I {pppoe_ifname} baidu.com"
        process = subprocess.Popen(command, stdout=subprocess.PIPE, shell=True)
        output, error = process.communicate()

        packet_loss = re.search(r"(\d+)% packet loss", output.decode("utf-8"))
        rtt = re.search(r"rtt min/avg/max/mdev = (.+)/(.+)/(.+)/(.+) ms", output.decode("utf-8"))
        if packet_loss:
            if rtt:
                packet_loss = packet_loss.group(1)
                rtt = rtt.group(3)
                # ifname_string = f"拨号接口：{pppoe_ifname}({local_pppoe_ifname})"
                # pccket_loss_string = f"丢包率：{int(packet_loss)}%"
                # rtt_string = f"延时：{round(float(rtt))}ms"
                # logging.info(f"{ifname_string:<20} {pccket_loss_string:<7} {rtt_string:<7}")
                # 写入本地文件
                monitor_info['line'][pppoe_ifname]['pingloss'] = int(packet_loss)
                monitor_info['line'][pppoe_ifname]['rtt'] = float(rtt)
                sync.write_to_json_file(monitor_info, 'monitor_info.json')
            else:
                logging.info(f"{pppoe_ifname} 获取ping延时数据出错")
        else:
            logging.info(f"{pppoe_ifname} 获取ping丢包率数据出错")

    def ping_round_list():
        threads = []
        for pppoe_ifname in monitor_info['line'].keys():
            local_pppoe_ifname = monitor_info['line'][pppoe_ifname]['online_ifname']
            thread = threading.Thread(target=ping_check, args=(pppoe_ifname, local_pppoe_ifname))
            thread.start()
            threads.append(thread)
        # 等待所有线程完成
        for thread in threads:
            thread.join()
   # 读取本地json文件
    monitor_info = sync.read_from_json_file('monitor_info.json')
    # 启动ping线程
    ping_round_list()
    # 输出概况到日志
    pingloss_values = [monitor_info['line'][pppoe_ifname]['pingloss'] for pppoe_ifname in monitor_info['line']]
    avg_pingloss = round(sum(pingloss_values) / len(pingloss_values), 2)
    max_pingloss = max(pingloss_values)
    min_pingloss = min(pingloss_values)
    rtt_values = [monitor_info['line'][pppoe_ifname]['rtt'] for pppoe_ifname in monitor_info['line']]

    avg_rtt = round(sum(rtt_values) / len(rtt_values), 2)
    max_rtt = round(max(rtt_values), 2)
    min_rtt = round(min(rtt_values), 2)
    logging.info(f"ping检测完成！")
    logging.info(f"当前所有线路pingloss数据：[平均值：{avg_pingloss}%， 最大值：{max_pingloss}%， 最小值：{min_pingloss}%]")
    logging.info(f"当前所有线路rtt数据：[平均值：{avg_rtt}ms， 最大值：{max_rtt}ms， 最小值：{min_rtt}ms]")


# 网络监控数据采集上报
def network_and_hardware_monitor():
    read, write = get_disk_io()
    total, used, useage = get_memory_info()
    disk_space = get_disk_space()
    # 根据最新的线路信息创建对应的监控信息记录字典
    monitor_info = sync.read_from_json_file('monitor_info.json')
    pppline_local = sync.read_from_json_file('pppline.json')
    monitor_info['uptime'] = get_uptime()
    monitor_info['current_cpu_useage'] = get_cpu_useage()
    monitor_info['disk_space'] = {}
    for mount in disk_space.keys():
        monitor_info['disk_space'][mount] = {}
        monitor_info['disk_space'][mount]['total'] = disk_space[mount]['total']
        monitor_info['disk_space'][mount]['used'] = disk_space[mount]['used']
        monitor_info['disk_space'][mount]['useage'] = disk_space[mount]['useage']
    monitor_info['disk_io'] = {}
    monitor_info['disk_io']['read'] = read
    monitor_info['disk_io']['write'] = write
    monitor_info['memory'] = {}
    monitor_info['memory']['total'] = total
    monitor_info['memory']['used'] = used
    monitor_info['memory']['useage'] = useage

    monitor_info['line'] = {}
    for ifname in pppline_local.keys():
        online_ifname = get_local_pppoe_ifname(ifname)
        monitor_info['line'][ifname] = {}
        monitor_info['line'][ifname]['online_ifname'] = online_ifname
        monitor_info['line'][ifname]['pppoe_user'] = pppline_local[ifname]['user']

    # 写入文件
    sync.write_to_json_file(monitor_info, 'monitor_info.json')
    logging.info("硬件信息已采集完成！")
    # 获取接口实时上下行
    get_pppline_bandwitch()
    # 获取线路丢包延时
    get_pingloss_and_rtt()
    # 读取监控文件信息数据并推送数据到控制平台
    monitor_info = sync.read_from_json_file('monitor_info.json')
    compressed_monitor_info = json.dumps(monitor_info, separators=(',', ':'), ensure_ascii=False)

    # 推送
    sync.update_monitor_info_to_control_node(compressed_monitor_info)

