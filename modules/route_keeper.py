import re
import struct
import fcntl
import socket
import subprocess
from collections import Counter
from modules.logger import logging

# Time : 2023/12/08
# Author : yuan_zi
"""
路由维护模块
"""

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

def get_pppoe_ip_address_list(pppoe_info):
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
def update_routing_table(pppline):
    # 创建当前在线的网卡信息
    pppoe_info = {}
    for pppoe_ifname in pppline.keys():
        pppoe_info[pppoe_ifname] = {}
        pppoe_info[pppoe_ifname]['ip'] = ''
        pppoe_info[pppoe_ifname]['table'] = f'{pppoe_ifname}_table'

    # 获取当前在线ip列表和路由表中所包含的ip列表
    pppoe_ip_address_list = get_pppoe_ip_address_list(pppoe_info)
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
    # 删除
    for ip in expired_ip_list:
        table = get_expired_ip_router_rules(ip)
        # logging.info(f"无效路由:{ip} 对应的表项:{table}")
        del_rules(ip, table)
    if len(expired_ip_list) != 0:
        logging.info("无效路由已经全部清除")

    # 再次获取清理后的路由表
    route_ipaddress_list = get_current_route_rule_ip()
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

