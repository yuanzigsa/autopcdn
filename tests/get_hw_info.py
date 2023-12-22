import os
import platform
import socket
import psutil
import time

def get_os_info():
    return f"Operating System: {platform.system()} {platform.version()}"

def get_host_info():
    return f"Hostname: {socket.gethostname()}"

def get_boot_time():
    boot_time = psutil.boot_time()
    uptime_seconds = int(time.time() - boot_time)
    uptime_str = time.strftime("%H:%M:%S", time.gmtime(uptime_seconds))
    return f"Uptime: {uptime_str}"

def get_system_info():
    return f"System Version: {platform.platform()}"


def get_memory_info():
    memory = psutil.virtual_memory()
    return f"Memory: {memory.total} bytes, Used: {memory.used} bytes, Usage: {memory.percent}%"

# def get_disk_info():
#     partitions = psutil.disk_partitions()
#     disk_info = []
#     for partition in partitions:
#         usage = psutil.disk_usage(partition.mountpoint)
#         disk_info.append(f"{partition.device} - Total: {usage.total} bytes, Used: {usage.used} bytes, Usage: {usage.percent}%")
#     return "\n".join(disk_info)


import psutil


def is_interesting_partition(partition):
    interesting_mount_points = ['/', '/home', '/var', '/tmp', '/var/log', '/boot']
    return partition.mountpoint in interesting_mount_points and partition.fstype and partition.opts != 'swap' and psutil.disk_usage(
        partition.mountpoint).total > 0


def get_interesting_mount_points():
    partitions = psutil.disk_partitions(all=True)

    for partition in partitions:
        if is_interesting_partition(partition):
            mount_point = partition.mountpoint
            try:
                partition_usage = psutil.disk_usage(mount_point)
                print(f'Mount Point: {mount_point}')
                print(f'Total disk space: {partition_usage.total / (1024 ** 3):.2f} GB')
                print(f'Used disk space: {partition_usage.used / (1024 ** 3):.2f} GB')
                print(f'Disk usage: {partition_usage.percent}%\n')
            except Exception as e:
                print(f'Error reading {mount_point}: {e}')


get_interesting_mount_points()


def get_load_avg():
    load_avg = os.getloadavg()
    return f"Load Average: {', '.join(map(str, load_avg))}"

def get_disk_io():
    disk_io_before = psutil.disk_io_counters()
    time.sleep(1)  # 等待1s
    disk_io_after = psutil.disk_io_counters()

    read_speed = disk_io_after.read_bytes - disk_io_before.read_bytes
    write_speed = disk_io_after.write_bytes - disk_io_before.write_bytes

    return f"Disk IO - Read Speed: {read_speed} bytes/s, Write Speed: {write_speed} bytes/s"


def get_cpu_info():
    cpu_info = f"CPU: {platform.processor()}"
    try:
        with open('/proc/cpuinfo', 'r') as file:
            for line in file:
                if line.strip().startswith("model name"):
                    cpu_model = line.split(":")[1].strip()
                    cpu_info += f", Model: {cpu_model}"
                    break
    except FileNotFoundError:
        pass

    cpu_cores = psutil.cpu_count(logical=False)
    cpu_usage = psutil.cpu_percent(interval=1)

    return f"{cpu_info}, Cores: {cpu_cores}, CPU Usage: {cpu_usage}%"

if __name__ == "__main__":
    print(get_os_info())
    print(get_host_info())
    print(get_boot_time())
    print(get_system_info())
    print(get_cpu_info())
    print(get_memory_info())
    print(get_load_avg())
    print(get_disk_io())
    # print(get_disk_info())
    print(get_physical_disk_info())