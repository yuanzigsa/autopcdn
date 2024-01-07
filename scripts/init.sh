#!/bin/bash
#===============================================================================
# Date：Jan. 7th, 2024
# Author : yuanzi
# Description: 初始化系统，提供auto_pcdn运行环境
#===============================================================================

# 定义日志函数
get_current_time() {
    echo "$(date "+%Y-%m-%d %H:%M:%S")"
}
log_info() {
    echo -e "$(get_current_time) \e[32mINFO\e[0m: $1"
}

log_error() {
    echo -e "$(get_current_time) \e[31mERROR\e[0m: $1"
}

log_warning() {
    echo -e "$(get_current_time) \e[33mWARNING\e[0m: $1"
}

log_info "执行开始..."
# 检查是否以root用户身份运行
if [[ $EUID -ne 0 ]]; then
    log_error "请以root用户身份运行此脚本"
    exit 1
fi

# 配置dns
check_configure_dns() {
    log_info "开始检测和配置DNS..."
    if ! grep -E '^nameserver' '/etc/resolv.conf' &> /dev/null; then
        sudo bash -c 'echo -e "nameserver 114.114.114.114\nnameserver 8.8.8.8" >> /etc/resolv.conf'
        log_info "检测到系统未配置DNS，已将DNS配置为114.114.114.114和8.8.8.8"
    fi
}

# python3环境部署及所需外置库的安装
install_python3_env() {
    log_info "开始安装python3..."
    sudo yum install -y python3 &> /dev/null
    log_info "python3已安装"

    log_info "开始安装gcc..."
    sudo yum install -y gcc python3-devel &> /dev/null
    log_info "gcc已安装"

    log_info "开始安装python所需的外置库..."
    pip3 install requests -i http://pypi.douban.com/simple/ --trusted-host pypi.douban.com &> /dev/null
    pip3 install pysnmp -i http://pypi.douban.com/simple/ --trusted-host pypi.douban.com &> /dev/null
    pip3 install psutil -i http://pypi.douban.com/simple/ --trusted-host pypi.douban.com &> /dev/null
    pip3 install colorlog -i http://pypi.douban.com/simple/ --trusted-host pypi.douban.com &> /dev/null

    log_info "python所需的外置库已全部安装"
}
# 创建服务并运行
create_systemd_service() {
    script_path="/opt/auto_pcdn/auto_pcdn.py"
    log_info "开始创建auto_pcdn.py脚本并写进系统服务运行..."
    service_content="[Unit]\nDescription=AutoPCDN\nAfter=network.target\n\n[Service]\nExecStart=/usr/bin/python3 $script_path\nRestart=always\nKillMode=process\nUser=root\nWorkingDirectory=/opt/auto_pcdn\n\n[Install]\nWantedBy=multi-user.target\n"
    service_file_path='/etc/systemd/system/auto_pcdn.service'
    echo -e "$service_content" > "$service_file_path"

    systemctl daemon-reload &> /dev/null
    systemctl enable auto_pcdn.service &> /dev/null
    systemctl start auto_pcdn.service &> /dev/null
    log_info "AtuoPCDN程序已创建并写进系统服务并设置成开机自启"
}
check_log() {
    log_file="/opt/auto_pcdn/log/auto_pcdn.log"
    search_string="运维监控数据采集"
    timeout=600  # 设置超时时间为600秒
    elapsed_time=0

    while [ $elapsed_time -lt $timeout ]; do
        # 检查日志文件中是否包含特定字符
        if grep -q "$search_string" "$log_file"; then
            sleep 10
            log_info "执行结束！"
            break
        fi
        sleep 1
        ((elapsed_time++))
    done
    sleep 1
    if [ $elapsed_time -ge $timeout ]; then
        log_error "超时退出...请检查！"
    fi
}

# 配置dns确保正确解析域名
check_configure_dns

# 校准时间时区
sudo yum install -y ntpdate &> /dev/null && sudo ntpdate time.windows.com &> /dev/null && sudo timedatectl set-timezone Asia/Shanghai &> /dev/null && sudo hwclock --systohc &> /dev/null
log_info "已校准系统时间"


# 检查服务状态
status=$(service auto_pcdn status > /dev/null 2>&1 && echo "active" || echo "inactive")
if [ "$status" = "active" ]; then
    echo -e "$(date "+%Y-%m-%d %H:%M:%S") 检测到auto_pcdn已经处于Active状态。\n"
    service auto_pcdn status
#    read -p "是否清除之前的所有部署，重新进行部署？ (y/n) 等待10s后退出: " answer
    echo -e "\n$(date "+%Y-%m-%d %H:%M:%S") 重新部署操作已被取消。"
    exit 1
fi

# 下载auto_pcdn脚本程序
mkdir -p /opt/auto_pcdn/
curl -o /opt/auto_pcdn/auto_pcdn.tar.gz -L https://gitee.com/yuanzichaopu/auto_pppoe/releases/download/auto_pcdn_v1.2/auto_pcdn.tar.gz &> /dev/null
log_info "auto_pcdn监管程序下载完成"
# 解压
cd /opt/auto_pcdn/
tar -zxvf  auto_pcdn.tar.gz &> /dev/null
rm -rf auto_pcdn.tar.gz
rm -rf info/*
log_info "已经将监管程序包解压至/opt/auto_pcdn/目录下"

# 写入machineTag到系统内
echo "@@MACHINETAG@@" > /opt/auto_pcdn/info/machineTag.info
log_info "machineTag已写入系统内"

# 安装yum源插件
yum install yum-fastestmirror -y &> /dev/null
log_info "已安装yum源自动选择插件，会自动优先选择最快的yum源"

# 安装基础环境
install_python3_env

# 启动服务并检查日志
touch /opt/auto_pcdn/log/auto_pcdn.log
create_systemd_service
tail -f /opt/auto_pcdn/log/auto_pcdn.log &
TAIL_PID=$!
check_log
kill $TAIL_PID