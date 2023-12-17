import os
import json


def read_from_json_file(file):
    path = os.path.join("info", file)
    with open(path, 'r', encoding='utf-8') as file:
        value = json.load(file)
    return value

value = read_from_json_file('pppline_monitor_info.json')

for ifname in value.keys():
    value[ifname]['status'] = 0
    value[ifname]['current_max_upbw_mbps'] = round(0 * 8 / 1000, 2)

print(value)


path = os.path.join("info", 'pppline_monitor_info.json')
with open(path, 'w', encoding='utf-8') as file:
    json.dump(value, file, ensure_ascii=False, indent=2)