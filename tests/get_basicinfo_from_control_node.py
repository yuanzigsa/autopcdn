import requests
import logging

machineTag = "VTCXNZLT"

get_pppoe_basicinfo_api_url = "http://120.26.111.213:9119/orion/expose-api/machine-info/get-config"

question_headers = {
    "O-Login-Token": "accessToken",
    "accessToken": "ops_access",
    "script_path": "/opt/auto_pppoe"
  }

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

info = get_pppoe_basicinfo_from_control_node()
print(info)

{'authType': 1, 'city': '石家庄', 'cpu': 32, 'createTime': 1700700170065, 'description': None, 'groupIdList': [2], 'host': 'cs.trkjhb.cn', 'id': 3, 'isp': 'CT', 'keyId': None,
 'keyName': None, 'lastConnectTime': 1701697907000, 'lineType': 2, 'linecount': 15, 'memory': 64, 'name': 'PCDN-SHIJIAZHUANG-CT-DSIX3NGF', 'natType': 1, 'nodeStatus': 1,
 'pppline': {'ip2': {'ip': '9.9.9.9', 'eth': 'eth2', 'mask': '255.255.255.0', 'gateway': '9.9.9.1', 'disabled': '0', 'bandwidth': '0'}, 'ip1': {'ip': '9.9.9.9', 'eth': 'eth1', 'mask': '255.255.255.0', 'gateway': '9.9.9.1', 'disabled': '0', 'bandwidth': '0'}, 'ip3': {'ip': '9.9.9.9', 'eth': 'eth3', 'mask': '255.255.255.0', 'gateway': '9.9.9.1', 'disabled': '0', 'bandwidth': '0'}},
 'provider': 'YWT', 'province': '河北', 'proxyHost': None, 'proxyId': None, 'proxyPort': None, 'proxyType': None, 'reportInterval': 15,
 'reportLocalPath': '/opt/tools/basicinfo/ppp_basicinfo.json', 'reported': 1, 'sshPort': 1022, 'status': 1, 'tag': 'DSIX3NGF', 'updateTime': 1703491028324,
 'upstreambandwidth': 3000, 'username': 'root'}
