import requests
from datetime import datetime

machineTag = "JKHBHUJH"
update_monitor_info_api_url = "http://122.191.108.42:9119/orion/expose-api/machine-monitor/upload-monitor-info"
question_headers  = {
    "O-Login-Token": "accessToken",
    "accessToken": "ops_access",
    "script_path": "/opt/auto_pppoe"
  }
def update_monitor_info_to_control_node(monitor_info):
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    data = {
        "machineTag": machineTag,
        "monitorInfo": monitor_info,
        "reportTime": current_time
    }
    try:
        response = requests.post(update_monitor_info_api_url, headers=question_headers, json=data)
        if "200" in response.text:
            print("已将最新网络和硬件监控信息推送至控制平台")
        else:
            print(f"更新网络和硬件监控信息失败，错误信息：{response.text}")
    except requests.RequestException as e:
        print("更新网络和硬件监控信息失败，错误信息：%s", str(e))


update_monitor_info_to_control_node("最新网络和硬件监控信息")