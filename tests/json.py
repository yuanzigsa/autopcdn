# import os
# import json
#
#
# def read_from_json_file(file):
#     path = os.path.join("info", file)
#     with open(path, 'r', encoding='utf-8') as file:
#         value = json.load(file)
#     return value
#
# data = read_from_json_file('monitor_info.json')
# data = json_string_compact = json.dumps(data, separators=(',', ':'))
#
#
#
#
# data2 = '''{  \"system_info\":\"Linux-3.10.0-1160.el7.x86_64-x86_64-with-centos-7.9.2009-Core\",  \"cpu_model\":\"Intel(R) Xeon(R) CPU E5-2683 v4 @ 2.10GHz\",  \"cpu_cores\":4,  \"uptime\":\"04 days, 07:04:26\",  \"current_cpu_useage\":2.2,  \"disk_space\":{    \"/run\":{      \"total\":4100595712,      \"used\":261140480,      \"useage\":6.4    },    \"/\":{      \"total\":47217381376,      \"used\":3345444864,      \"useage\":7.1    },    \"/boot\":{      \"total\":1063256064,      \"used\":157163520,      \"useage\":14.8    }  },  \"disk_io\":{    \"read\":0,    \"write\":16384  },  \"memory\":{    \"total\":8201191424,    \"used\":768708608,    \"useage\":16.2  },  \"line\":{    \"ppp0\":{      \"online_ifname\":\"ppp0\",      \"pppoe_user\":202301,      \"current_max_upbw_mbps\":0.0,      \"current_max_downbw_mbps\":0.0,      \"pingloss\":0,      \"rtt\":28.079    },    \"ppp1\":{      \"online_ifname\":\"ppp1\",      \"pppoe_user\":202302,      \"current_max_upbw_mbps\":0.0,      \"current_max_downbw_mbps\":0.0,      \"pingloss\":0,      \"rtt\":26.806    },    \"ppp2\":{      \"online_ifname\":\"ppp2\",      \"pppoe_user\":202303,      \"current_max_upbw_mbps\":0.0,      \"current_max_downbw_mbps\":0.0,      \"pingloss\":0,      \"rtt\":26.884    },    \"ppp3\":{      \"online_ifname\":\"ppp3\",      \"pppoe_user\":202304,      \"current_max_upbw_mbps\":0.0,      \"current_max_downbw_mbps\":0.0,      \"pingloss\":0,      \"rtt\":28.664    }  }}'''
#
# print(data)
# print(len(data))
# print(len(data2))