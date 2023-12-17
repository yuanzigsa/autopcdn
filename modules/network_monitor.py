import re
import os
import json
import time
import threading
import subprocess
from pysnmp.hlapi import *
import modules.data_sync as sync
from modules.logger import logging



# Time : 2023/12/08
# Author : yuan_zi


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
    pppline_monitor_info = read_from_json_file('pppline_monitor_info.json')
    for ifname in pppline_monitor_info.keys():
        online_ifname = get_local_pppoe_ifname(ifname)
        pppline_monitor_info[ifname]['current_max_upbw_mbps'] = round(interface_out_rates.get(online_ifname, 0.00) * 8 / 1000000, 2)
        logging.info(
            f"{ifname}({pppline_monitor_info[ifname]['pppoe_user']})实时上行速率：{pppline_monitor_info[ifname]['current_max_upbw_mbps']}mbps")
        pppline_monitor_info[ifname]['current_max_downbw_mbps'] = round(interface_in_rates.get(online_ifname, 0.00) * 8 / 1000000, 2)
        logging.info(
            f"{ifname}({pppline_monitor_info[ifname]['pppoe_user']})实时下行速率：{pppline_monitor_info[ifname]['current_max_downbw_mbps']}mbps")
    # 将字典写入本地文件
    write_to_json_file(pppline_monitor_info, 'pppline_monitor_info.json')
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
                pppline_monitor_info[pppoe_ifname]['pingloss'] = int(packet_loss)
                pppline_monitor_info[pppoe_ifname]['rtt'] = float(rtt)
                write_to_json_file(pppline_monitor_info, 'pppline_monitor_info.json')
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
   # 读取本地json文件
    pppline_monitor_info = read_from_json_file('pppline_monitor_info.json')
    # 启动ping线程
    ping_round_list()
    logging.info("Ping检测完成！")


# 网络监控数据采集上报
def traffic_speed_and_pingloss_collection():
    # 读取本地最新的拨号接口配置文件
    pppline_local = read_from_json_file('pppline.json')

    # 创建监控信息记录文件
    pppline_monitor_info = {}
    for ifname in pppline_local.keys():
        pppline_monitor_info[ifname] = {}
        online_ifname = get_local_pppoe_ifname(ifname)
        pppline_monitor_info[ifname]['online_ifname'] = online_ifname
        pppline_monitor_info[ifname]['pppoe_user'] = pppline_local[ifname]['user']

    # 写入文件
    write_to_json_file(pppline_monitor_info, 'pppline_monitor_info.json')
    # 获取接口实时上下行
    get_pppline_bandwitch()
    # 获取线路丢包延时
    get_pingloss_and_rtt()
    # 读取监控文件信息数据并推送数据到控制平台
    pppline_monitor_info = read_from_json_file('pppline_monitor_info.json')
    sync.update_pppline_monitor_to_control_node(pppline_monitor_info)


