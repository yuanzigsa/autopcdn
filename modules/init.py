import os
import re
import sys
import time
import fcntl
import struct
import socket
import subprocess
from modules.logger import logging

# Time : 2023/12/08
# Author : yuan_zi

"""
PPoE拨号初始化环境
"""


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
            existing_content = snmpd_conf.read().splitlines()

        # 创建一个新的列表来存储需要保留的行
        new_content = []
        flag_1 = "rocommunity"
        flag_2 = "agentAddress"

        for line in existing_content:
            if flag_1 in line:
                continue
            if flag_2 in line:
                continue

            # 将未匹配到 flag_1 和 flag_2 的行添加到新的内容中
            new_content.append(line)

        # 在 new_content 列表的最前面插入新的配置行
        new_content.insert(0, config_lines[1])
        new_content.insert(0, config_lines[0])

        # 将配置写入文件，加在现有内容之前
        with open(file_path, "w") as snmpd_conf:
            snmpd_conf.write("\n".join(new_content) + "\n")

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


# 创建配置文件，带vlan的不带vlan 后面还要加入专线的
def create_ifconfig_file(file_type, ifname, vlanid=None, ip=None, pppoe_user=None, macaddr=None, pppoe_number=None):
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


# 创建路由表
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
def derivation_mac_address(mac_addr, ori_mac_list):
    last_two_digits = int(mac_addr[-2:], 16)
    last_two_digits = (last_two_digits + 1) % 256
    new_last_two_digits = format(last_two_digits, '02x')
    new_mac_address = mac_addr[:-2] + new_last_two_digits
    # 与本机所有mac地址比较，如果已存在，再生成新mac检查是否与本机现有mac重复,直到获取唯一的mac
    while new_mac_address in ori_mac_list:
        new_mac_address = derivation_mac_address(new_mac_address)
    return new_mac_address


# 创建pppoe拨号前的配置文件以及创建路由表
def create_pppoe_connection_file_and_routing_tables(ppp_line):
    # 定义初始路由表编号
    table_number = 50
    # 定义初始mac
    mac_address = "00:00:00:00:00:01"
    # 创建本机的mac地址表用于后续进行比对
    original_mac_address_list = get_local_mac_address_list()
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
            create_ifconfig_file('pppoe-no-vlan', ifname=dial_up_ifnmme, vlanid=pppoe_vlan, pppoe_user=pppoe_user, pppoe_number=pppoe_ifname)
            # 创建路由表并通过create_routing_tables的返回值得出新的路由表优先级编号
            table_number = create_routing_tables(table_number, pppoe_ifname)
        else:
            logging.info(f"{pppoe_ifname}所属VLAN{pppoe_vlan}")
            create_ifconfig_file('ifname-vlan', ifname=dial_up_ifnmme, vlanid=pppoe_vlan, pppoe_user=pppoe_user, macaddr=mac_address, pppoe_number=pppoe_ifname)
            create_ifconfig_file('pppoe-vlan', ifname=dial_up_ifnmme, vlanid=pppoe_vlan, pppoe_user=pppoe_user, macaddr=mac_address, pppoe_number=pppoe_ifname)
            table_number = create_routing_tables(table_number, pppoe_ifname)
            # 添加这个mac到已存在列表，避免后续mac与之重复
            original_mac_address_list.append(mac_address)
            mac_address = derivation_mac_address(mac_address, original_mac_address_list)  # mac地址后2位尾数按照16进制+1
            # 开启Vlan子接口
            cmd = f"ifup {dial_up_ifnmme}.{pppoe_vlan}"
            subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
            logging.info(f"Vlan子接口{dial_up_ifnmme}.{pppoe_vlan}已启用")
    return ppp_line


# 拨号
def pppoe_dial_up(pppoe_ifname, pppoe_user):
    try:
        logging.info(f"{pppoe_ifname}({pppoe_user}) 开始拨号...")
        command = f"pppoe-connect /etc/sysconfig/network-scripts/ifcfg-{pppoe_ifname} &"
        # 创建子进程
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True, universal_newlines=True,  preexec_fn=os.setpgrp)
        # start_new_session分离子进程（避免关闭父进程后子进程随之退出）
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