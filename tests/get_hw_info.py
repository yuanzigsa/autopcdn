import logging
import os
import platform
import socket
import psutil
import time

def get_os_info():
    return f"Operating System: {platform.system()} {platform.version()}"

def get_host_info():
    return f"Hostname: {socket.gethostname()}"



def get_uptime():
    boot_time = psutil.boot_time()
    uptime_seconds = int(time.time() - boot_time)
    uptime_str = time.strftime("%d days, %H:%M:%S", time.gmtime(uptime_seconds))
    return uptime_str




def get_memory_info():
    memory = psutil.virtual_memory()
    return memory.total, memory.used, memory.percent


def get_all_mount_points():
    def is_interesting_partition(partition):
        # 过滤掉容量为0的挂载点和一些不常用的挂载点
        return (
                partition.fstype
                and partition.opts != 'swap'
                and psutil.disk_usage(partition.mountpoint).total > 0
        )

    visited_mount_points = set() # 用于去重
    partitions = psutil.disk_partitions(all=True)
    # 创建磁盘挂载点信息字典
    mount_points_info = {}

    for partition in partitions:
        if (is_interesting_partition(partition)and partition.mountpoint not in visited_mount_points): # 去重
            mount_point = partition.mountpoint
            try:
                partition_usage = psutil.disk_usage(mount_point)
                if partition_usage.used > 0:
                    mount_points_info[mount_point] = {}
                    mount_points_info[mount_point]['total'] = partition_usage.total
                    mount_points_info[mount_point]['used'] = partition_usage.used
                    mount_points_info[mount_point]['usage'] = partition_usage.percent
                    # print(f'Mount Point: {mount_point}')
                    # print(f'Total disk space: {partition_usage.total / (1024 ** 3):.2f} GB')
                    # print(f'Used disk space: {partition_usage.used / (1024 ** 3):.2f} GB')
                    # print(f'Disk usage: {partition_usage.percent}%\n')
                    visited_mount_points.add(mount_point)
            except Exception as e:
                logging.error(f'读取磁盘挂载点{mount_point}信息错误: {e}')
    return  mount_points_info


def get_load_avg():
    load_avg = os.getloadavg()
    return f"Load Average: {', '.join(map(str, load_avg))}"

def get_disk_io():
    disk_io_before = psutil.disk_io_counters()
    time.sleep(1)  # 等待1s
    disk_io_after = psutil.disk_io_counters()

    read_speed = disk_io_after.read_bytes - disk_io_before.read_bytes
    write_speed = disk_io_after.write_bytes - disk_io_before.write_bytes

    return read_speed, write_speed

def get_system_info():
    system_info = {platform.platform()}
    return system_info

def get_cpu_info():
    try:
        with open('/proc/cpuinfo', 'r') as file:
            for line in file:
                if line.strip().startswith("model name"):
                    cpu_model = line.split(":")[1].strip()
                    # cpu_info = f"Model: {cpu_model}"
                    break
    except FileNotFoundError:
        pass

    cpu_cores = psutil.cpu_count(logical=False)
    # cpu_usage = psutil.cpu_percent(interval=1)
    return cpu_model, cpu_cores

def get_cpu_useage():
    cpu_usage = psutil.cpu_percent(interval=1)
    return cpu_usage


if __name__ == "__main__":
    print(get_os_info())
    print(get_host_info())
    print(get_boot_time())
    print(get_system_info())
    print(get_cpu_info())
    print(get_memory_info())
    print(get_load_avg())
    print(get_disk_io())
