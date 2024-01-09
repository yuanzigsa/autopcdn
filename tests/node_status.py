import subprocess


def get_node_status(pppoe_ifname):
    try:
        cmd = f"fping -I {pppoe_ifname} baidu.com"
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
        if "alive" in result.stdout.decode('utf-8'):
            return 1
        else:
            return 0
    except subprocess.CalledProcessError as e:
        pass


def node_status(netline_local):
    for ifname in netline_local.keys():
        if netline_local[ifname]['disabled'] == 0:
            status = get_node_status(ifname)
            if status == 1:
                # 但凡有一个接口能通公网且没有被控制节点禁用，证明节点可用..
                node_status = 1
                return node_status
            else:
                continue
        else:
            node_status = 0
            return node_status


netline_local = {}
netline_local['ip1']["disabled"] = 0
netline_local['ip1']["di"] = 0