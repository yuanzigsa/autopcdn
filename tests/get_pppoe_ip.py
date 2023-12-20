import subprocess
import re
import logging

def get_local_pppoe_ip(pppoe_ifname):
    command = f"pppoe-status /etc/sysconfig/network-scripts/ifcfg-{pppoe_ifname}"
    try:
        result = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True,
                                  universal_newlines=True)
        stdout, stderr = result.communicate()

        if result.returncode == 0:
            ip_pattern = 'inet(.*?)peer'
            match = re.search(ip_pattern, stdout)
            if match:
                ip_address = match.group(1).strip()
                return ip_address
            else:
                ip_address = ""
                return ip_address
    except Exception as e:
        logging.exception(f"发生异常：{str(e)}")


print(get_local_pppoe_ip("ppp0"))