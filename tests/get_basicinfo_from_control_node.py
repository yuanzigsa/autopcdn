import requests
import logging

machineTag = "JKHBHUJH"

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

netline = info['pppline']
for line in netline:
    print(netline[line]['eth'])