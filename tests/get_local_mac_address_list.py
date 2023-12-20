import socket
import fcntl
import struct

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

mac = "11:11:11:11:11:11"
mac_list =  get_local_mac_address_list()
mac_list.append(mac)
print(mac_list)

# 打印mac_list的类型
print(type(mac_list))

if mac in mac_list:
    print("MAC地址在列表中")
else:
    print("MAC地址不在列表中")