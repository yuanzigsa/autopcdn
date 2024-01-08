import os
import json
import modules.data_sync as sync
import modules.init as init
from modules.logger import logging


# Time : 2023/12/08
# Author : yuan_zi

# 检查控制平台是否存在拨号信息的更新
def check_for_updates_and_config():
    def check_updates(pppline_local, pppline_control_node):
        if pppline_local != pppline_control_node:
            info = "检测到拨号信息发生更新"
            logging.info(info)
            # 上报平台机器动态
            sync.update_local_operate_to_control_node(1, info, '平台信息更新检查')
            # 1. pppline_control_node有的键而pppline_local中没有的：账号新增
            keys_only_in_control_node = set(pppline_control_node.keys()) - set(pppline_local.keys())
            # 2. pppline_control_node没有有的键而pppline_local有的：账号减少
            keys_only_in_local = set(pppline_local.keys()) - set(pppline_control_node.keys())
            # 3. pppline_control_node和pppline_local都有的键但是值不一样的：账号更改
            same_keys_but_different_values = {}
            for key, value in pppline_control_node.items():
                if key in pppline_local and pppline_local[key]['user'] != pppline_control_node[key]['user']:
                    same_keys_but_different_values[key] = value
            return keys_only_in_control_node, keys_only_in_local, same_keys_but_different_values
        else:
            # 如果没有更新，返回空值
            return None, None, None

    # 获取当前云平台最新数据
    pppline_control_node = sync.get_pppoe_basicinfo_from_control_node()["pppline"]
    # 获取本地存储的上次拨号成功的数据
    pppline_local = sync.read_from_json_file('pppline.json')
    # 获取差异数据
    keys_only_in_control_node, keys_only_in_local, same_keys_but_different_values = check_updates(pppline_local, pppline_control_node)
    # 1. 云平台有本地没有
    if keys_only_in_control_node:
        # 创建更新拨号信息列表
        add_pppoe_list = {}
        for ifname in keys_only_in_control_node:
            add_pppoe_list[ifname] = {}
            add_pppoe_list[ifname] = pppline_control_node[ifname]
            pppoe_user = pppline_control_node[ifname]['user']
            dial_up_ifname = pppline_control_node[ifname]['eth']
            logging.info(f"检测到云平台账号新增，配置接口名：ifcfg-{ifname} 物理接口：{dial_up_ifname} 账号：{pppoe_user}")
        # 创建新增项的拨号前配置
        init.create_pppoe_connection_file_and_routing_tables(add_pppoe_list)
        logging.info("所有新增拨号账号已建立拨号前的配置文件并写入密码信息")
        # 写入本地
        sync.write_to_json_file(pppline_control_node, 'pppline.json')

    # 2. 本地有云平台没有
    if keys_only_in_local:
        logging.info("账号减少：%s", keys_only_in_local)
        for ifname in keys_only_in_local:
            pppoe_user = pppline_local[ifname]['user']
            dial_up_ifname = pppline_local[ifname]['eth']
            logging.info(f"检测到云平台账号删减，配置接口名：ifcfg-{ifname} 物理接口：{dial_up_ifname} 账号：{pppoe_user}")

            # 3. 本地和云平台都有但是值不一样
    if same_keys_but_different_values:
        modify_pppoe_list = {}
        for ifname in same_keys_but_different_values:
            modify_pppoe_list[ifname] = {}
            modify_pppoe_list[ifname] = pppline_control_node[ifname]
            old_pppoe_user = pppline_local[ifname]['user']
            pppoe_user = pppline_control_node[ifname]['user']
            logging.info(
                f"检测到云平台账号信息变动，配置接口名：ifcfg-{ifname} 原账号：{old_pppoe_user} 新账号：{pppoe_user}")
        init.create_pppoe_connection_file_and_routing_tables(modify_pppoe_list)
        logging.info("所有变更拨号账号已建立拨号前的配置文件并写入密码信息")
        # 写入此次拨号信息到硬盘，方便后续从云控制平台拉去信息与其对比，判断是否有更新
        sync.write_to_json_file(pppline_control_node, 'pppline.json')


# 节点机器基础信息检查，检查是否有更新，检查到更新写入本地