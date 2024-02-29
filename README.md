![image](https://github.com/yuanzigsa/autopcdn/assets/30451380/a5c3eb6f-742c-4f6f-870f-03c997411bb7)

# PCDN平台agent程序

## 一、项目简介

### 1.1 开发背景

出于业务的需求，我们急需一个PCDN管理平台，以实现对大规模机器的业务自动化部署和管理。然而，由于外包开发人员对于PCDN业务中涉及的PPPOE拨号、专线IP等网络接入方式，以及业务部署逻辑并不十分清楚，因此在这个项目中，由我来进行自动化部署程序和监控agent的开发。
AutoPCDN的开发基于Python3及其众多依赖库，如pysnmp、requests、psutil、watchdog等。这一项目真正实现了与控制平台的数据交互、PCDN网络（包括pppoe拨号和专线IP）的自动部署、业务环境配置，以及网络和硬件性能监控服务，同时提供给客户信息调用API。在这个过程中，我通过深入的技术研究和实践，不仅确保了平台的高效运作，同时为公司的大规模机器管理提供了一套完善的解决方案。

### 1.2 环境要求

- 系统：centos 7
- python版本：3.6+
- 依赖库：psutil、pysnmp、watchdog

### 1.3 项目目录结构

```shell
|-- auto_pcdn.py            # 主程序入口，用于启动pcdn初始化、线路质量监控和信息更新推送等功能
|-- modules/                # 功能模块文件夹，包含主模块依赖的子模块
|   |-- __init__.py
|   |-- data_sync.py        # 与控制节点进行信息同步,实现信息更新推送功能
|   |-- network_monitor.py  # 实现线路质量监控功能
|   |-- pppoe_init.py       # 拨号前的环境的部署，配置生成
|   |-- route_keeper.py     # 动态路由的维护
|   |-- logger.py           # 日志
|-- config/                 # 配置文件目录
|   |-- config.json         # 包含服务请求api、请求方法的定义
|-- tests/                  # 测试文件夹，包含所有的测试用例
|   |-- test.py
|-- log/                    # 存放分片日志 
|   |-- auto_pcdn.log
|-- scripts/        		# auto_pcdn程序的引导shell脚本
|   |-- init.sh
|-- requirements.txt        # 项目所有依赖的库
|-- README.md               # 项目的README文件，描述项目信息、安装步骤和用法等
```

### 1.4 执行流程

1. 从pcdn控制平台获取当前机器的网络配置信息
2. 检测获取到的网络配置信息是否非空，且判断其网络类型是[pppoe]还是专线，是否带有[vlan]等
3. 开始对当前客户端机器的网络进行初始化配置，在初始化钱会判断之前是否配置过，如果配置过，则不进行配置（如果需要更新在平台更改提交即可）
   - 安装各种拨号环境所需软件(如果是pppoe业务)
   - 修改当前机器系统文件来写入网络配置信息
   - 启用网络，并测试网络的连通性
   - 写入对应网络连接的路由信息

4. 初始化完成，按照网络类型启动相应的线程，并作为当前机器的后台服务持续运行
   - 如果网络类型是pppoe，启动以下线程：
     - 断线重播监控上报
     - 动态策略路由维护
     - 节点配置更新检查
     - 节点信息更新上报
     - 运维监控数据采集

   - 如果网络类型是专线ip，则启动以下线程：
     - 节点配置更新检查
     - 节点信息更新商报
     - 运维监控数据采集




## 二、部署流程

**注意：**AutoPCDN程序必须通过PCDN平台进行下发操作配套使用，因此不再提供手动部署流程，如需要手动部署可以参考引导程序中的shell代码，在第三节我会详细介绍。

### 2.1 准备环境

- 已在PCDN平台添加了节点机器的网络配置

  ![image-20240226160933972](C:\Users\lijin\AppData\Roaming\Typora\typora-user-images\image-20240226160933972.png)

### 2.2 执行命令

- 在PCDN平台的“批量执行”功能中选择需要执行的机器，并选择模板“ AutoPCDN-初始部署”，然后开始执行

  **注意**

  这里执行模板中的代码实际上就是项目scripts下的init.sh文件中的代码，在后面“配置维护”内容会具体介绍

  ![image-20240226162613500](C:\Users\lijin\AppData\Roaming\Typora\typora-user-images\image-20240226162613500.png)



## 二、功能详解

### 2.1 auto_pcdn主程序

- **定义成功初始化部署的信息**：打印初始化部署完成的信息。
- 定义一些辅助函数：包括设置运行标记、检查运行标记、检查专线类型、检查PCDN类型等。

- **定义多个线程函数**：包括动态策略路由维护、断线重拨监控上报、节点信息更新上报、运维监控数据采集上报和节点配置更新检查等。
- **定义启动线程的函数**：用于创建线程对象并启动线程。
- **在主函数中进行初始化和配置网络**：根据从控制节点获取的信息，进行环境初始化和网络配置。
- **启动线程**：根据PCDN类型，启动相应的线程。

### 2.2 init模块

这个模块主要用于PCDN环境部署初始化，包括配置DNS、关闭NetworkManager服务、安装必要的软件包、加载802.1q模块、配置SNMP服务、修改主机名、写入拨号账号密码、创建接口配置文件以及路由表等操作。

- **install_pcdn_runtime_environment函数**：
  - `check_configure_dns`函数：检查并配置DNS。
  - `close_Net_workManager`函数：关闭NetworkManager服务。
  - `install_package`函数：安装软件包。
  - `load_8021q_module`函数：加载802.1q模块。
  - `add_8021q_to_modules_file`函数：将802.1q模块添加到系统模块文件中。
  - `configure_snmpd_conf_and_start_the_service`函数：配置SNMP服务并启动。
- **modify_hostname函数**：修改主机名。
- **write_secrets_to_pppoe_config_file函数**：将拨号账户密码写入到PPPoe配置文件。
- **create_ifconfig_file函数**：创建接口配置文件，包括虚拟网卡、PPPoe连接等。
- **create_routing_tables函数**：创建路由表。
- **get_local_mac_address_list函数**：获取本机的所有MAC地址列表。
- **derivation_mac_address函数**：根据给定的MAC地址生成新的MAC地址，保证其在本机的唯一性。
- **create_pppoe_connection_file_and_routing_tables函数**：创建PPPoE连接文件和路由表。
- **pppoe_dial_up函数**：进行PPPoE拨号连接。
- **create_static_ip_connection_file_and_routing_tables函数**：创建专线IP网络配置文件和路由表。

### 2.3 data_sync模块

这个模块主要功能包括从控制节点获取配置信息、监控拨号连接状态、检测网络连通性、以及将监控信息上报至控制节点或客户端。

- **导入必要的模块**：代码一开始导入了一系列需要使用的模块，如`re`、`os`、`json`、`time`、`requests`等，这些模块用于处理文件操作、JSON数据、时间、HTTP请求等。
- **读取配置信息**：通过打开`config.json`文件读取配置信息，其中包括了一些API的URL和请求头信息等。
- **定义一些工具函数**：
  - `write_to_json_file(value, file)`：将数据写入JSON文件。
  - `read_from_json_file(file)`：从JSON文件中读取数据。
  - `get_local_pppoe_ip(pppoe_ifname)`：通过执行命令获取本地PPPoE连接的IP地址。
  - `update_local_operate_to_control_node(node_status, info, operate)`：将本地操作信息更新到控制节点。
  - `update_pppline_monitor_to_control_node(pppline_monitor_info)`：将PPPoE线路监控信息更新到控制节点。
  - `update_monitor_info_to_control_node(monitor_info)`：将网络和硬件监控信息更新到控制节点。
  - `update_dial_connect_to_control_node(type, node_name, pppoe_ifname, pppoe_user)`：将拨号连接状态更新到控制节点。
  - `get_node_status(ifname)`：检测指定接口的网络连通性。
- **断线重连监测上报**：
  - `set_update_discon_flag(pppoe_ifname)`：设置断线标记。
  - `check_update_discon_flag(pppoe_ifname)`：检查断线标记是否存在。
  - `check_pppoe_connect_process_exists(pppoe_ifname)`：检查PPPoe连接进程是否存在。
  - `check_for_reconnection_and_update_to_crontrol_node()`：检查断线重连状态并更新到控制节点。
- **节点具体信息上报到控制节点或客户端**：
  - `collect_node_spacific_info_update_to_control_node_or_customers(report_on, reportLocalPath, pcdn_basicinfo, pcdn_type, static_with_vlan)`：收集节点特定信息并上报到控制节点或客户端。

### 2.4 monitor模块


这个模块负责网络和硬件监控，主要用于采集系统的各种信息并将其推送到控制平台。

- `get_system_info()`:
  - 获取系统信息，包括操作系统类型和版本。
- `get_uptime()`:
  - 获取系统运行时间，即系统启动后经过的时间。
- `get_cpu_info()`:
  - 获取 CPU 的型号和核心数。
- `get_cpu_usage()`:
  - 获取 CPU 的使用率。
- `get_memory_info()`:
  - 获取内存的总量、已使用量和使用率。
- `get_total_memory_gb()`:
  - 获取总内存量，并转换为 GB 单位。
- `get_disk_io()`:
  - 获取磁盘的读写速率。
- `get_disk_space()`:
  - 获取磁盘空间信息，包括总空间、已使用空间和使用率。
- `get_local_pppoe_ifname(pppoe_ifname)`:
  - 获取本地的 PPPoE 接口名。
- `get_pppline_bandwidth(pcdn_type)`:
  - 获取拨号接口的带宽速率，利用 SNMP 协议采集数据。

- `get_pingloss_and_rtt()`:
  - 获取 ping 丢包率和延迟信息，通过执行 ping 命令获取。

- `network_and_hardware_monitor(pcdn_type)`:
  - 网络和硬件监控的主函数，调用上述函数获取各种信息，然后写入 JSON 文件并推送到控制平台。

### 2.5 route_keeper模块

这是一个路由维护模块，用于管理linux系统中的路由规则，包括删除无效路由、添加新拨号网卡获取的IP路由等功能。以下是详细介绍：

- **`get_current_route_rule_ip()`**:
   - 通过调用`get_ip_rules()`函数获取当前系统中的路由规则信息。
   - 使用正则表达式提取出路由规则中的IP地址列表。

- **`get_ip_address(ifname)`**:
   - 通过套接字和系统调用获取指定接口的IP地址。

- **`del_rules(ip, table)`** 和 **`add_rules(ifname, table, ip)`**:
   - 分别用于删除和添加路由规则。使用`subprocess`模块执行系统命令，实现对路由规则的管理。

- **`get_expired_ip_router_rules(keyword)`**:
   - 通过调用`subprocess`模块执行系统命令`ip rule list`获取当前系统中的路由规则信息。
   - 使用正则表达式提取出包含指定关键字的路由规则，返回相关内容。

- **`get_pppoe_ip_address_list(pppoe_info)`**:
   - 获取PPPoE接口的IP地址列表，并将获取到的IP地址与接口名关联起来。

- **`find_ifnmae_by_ip(pppoe_info, target_ip)`** 和 **`find_ifnmae_by_table(pppoe_info, target_ip)`**:
   - 分别根据IP地址和表名在PPPoE接口信息中查找对应的接口名。

- **`from_route_rules_get_old_ip_table()`**:
   - 通过调用`get_current_route_rule_ip()`获取当前路由规则中的IP地址列表。
   - 遍历路由规则列表，使用正则表达式提取出路由规则中的表名，并构建表名与IP地址的字典关系。

- **`del_duplicate_ip_routing_rules()`**:
   - 获取当前系统中的路由规则列表。
   - 使用正则表达式提取出路由规则中的信息，并统计重复的路由规则。
   - 删除重复的路由规则。

- **`update_routing_table(pppline)`**:
   - 更新路由表。
   - 首先创建当前在线的网卡信息，并获取当前路由表和PPPoE接口的IP地址列表。
   - 删除重复的路由规则，并对比路由表中的IP地址与PPPoE接口的IP地址，确定需要删除的无效路由。
   - 添加新拨号获取的IP路由。

- **`write_routing_rules(net_line_conf)`**:
   - 将固定IP的路由添加到路由表中。

### 2.6 update_checker模块

这个模块实现了检查pcdn控制平台是否存在拨号信息的更新，并根据更新情况执行相应的操作。下面是详细介绍：

- **`check_for_updates_and_config()`函数**:
   - 这是主要的函数，用于检查拨号信息是否有更新，并进行相应的配置。

- **`check_updates(pppline_local, pppline_control_node)`函数**:
   - 检查本地存储的拨号信息和控制平台的拨号信息是否一致。
   - 如果不一致，返回更新的拨号信息，包括新增的、删除的和变更的拨号信息。

- **获取最新拨号信息**:
   - 调用`sync.get_pppoe_basicinfo_from_control_node()`从控制平台获取最新的拨号信息。
   - 调用`sync.read_from_json_file('pppline.json')`读取上次拨号成功的数据。

- **获取差异数据**:
   - 调用`check_updates()`函数获取新增的、删除的和变更的拨号信息。

- **处理新增的拨号信息**:
   - 如果有新增的拨号信息，则创建新增项的拨号前配置，并将其写入本地。

- **处理删除的拨号信息**:
   - 如果有删除的拨号信息，则记录日志。

- **处理变更的拨号信息**:
   - 如果有变更的拨号信息，则创建变更拨号账号的拨号前配置，并将其写入本地。

- **更新本地拨号信息**:
   - 将最新的拨号信息写入本地，以便后续从云控制平台拉取信息与其对比，判断是否有更新。

### 2.7 redial模块

这个模块是一个文件监控程序，主要是服务于客户的重播接口，客户把需要重播的接口写入`redial.info`即可，改模块会实时监听这个文件的改动，当文件内容发生变化时，会读取文件内容并根据内容中的特定格式信息执行相应的重播操作，同时记录相关日志。

### 2.8 logger模块

这个模块是用于配置日志记录器，将日志信息同时输出到控制台和文件中，并使用不同的格式和颜色进行显示。



## 三、配置维护

### 3.1 Agent引导shell脚本（init.sh）

这个脚本就是PCDN平台中执行模板“AutoPCDN-初始部署”里所包含的代码，它的作用是初始化系统环境，为后续运行名为"auto_pcdn"的程序提供所需的环境。如需手动部署，也可以参考这个shell脚本中的内容，这个脚本主要进行了如下的操作：

- **配置DNS**

  检查系统的DNS配置，如果未配置，则将DNS设置为114.114.114.114和8.8.8.8。

- **校准时间**

  安装ntpdate工具，从time.windows.com同步时间，设置系统时区为Asia/Shanghai，并将硬件时钟与系统时间同步。

- **检查是否已经启用BBR**

  检查系统是否启用了BBR拥塞控制算法。没有则安装wget工具，下载并安装ELRepo的RPM包，安装新的内核，更新GRUB配置，设置默认启动内核，并开启BBR。

- **检查服务状态**

  检查名为"auto_pcdn"的服务是否处于活动状态，如果是则输出相关信息并询问是否重新部署，否则返回0。

- **安装Python3环境及外置库**

  函数安装Python3及相关开发环境，然后使用pip3安装requests、pysnmp、psutil和colorlog等外置库。

- **创建系统服务**

  创建名为"auto_pcdn"的系统服务，以自动运行/opt/auto_pcdn/auto_pcdn.py脚本。

- **部署AutoPCDN程序**

  创建/opt/auto_pcdn/目录，下载、解压auto_pcdn.tar.gz程序包，安装yum-fastestmirror插件，安装Python3环境及外置库，创建系统服务，并监视日志。









