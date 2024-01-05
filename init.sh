#!/bin/bash

# 初始化系统，提供auto_pcdn运行环境

echo "$(date "+%Y-%m-%d %H:%M:%S") 执行开始..."
# python3环境部署及所需外置库的安装
install_python3_env() {
    check_configure_dns() {
        echo "$(date "+%Y-%m-%d %H:%M:%S") 开始检测和配置DNS..."
        if ! grep -E '^nameserver' '/etc/resolv.conf' &> /dev/null; then
            sudo bash -c 'echo "$(date "+%Y-%m-%d %H:%M:%S") nameserver 114.114.114.114\nnameserver 8.8.8.8" >> /etc/resolv.conf'
            echo "$(date "+%Y-%m-%d %H:%M:%S") 检测到系统未配置DNS，已将DNS配置为114.114.114.114和8.8.8.8"
        fi
    }
    check_configure_dns
    echo "$(date "+%Y-%m-%d %H:%M:%S") 开始安装python3..."
    sudo yum install -y python3 &> /dev/null
    echo "$(date "+%Y-%m-%d %H:%M:%S") python3已安装"

    echo "$(date "+%Y-%m-%d %H:%M:%S") 开始安装gcc..."
    sudo yum install -y gcc &> /dev/null
    echo "$(date "+%Y-%m-%d %H:%M:%S") gcc已安装"

    echo "$(date "+%Y-%m-%d %H:%M:%S") 开始安装python所需的外置库..."
    pip3 install requests -i http://pypi.douban.com/simple/ --trusted-host pypi.douban.com &> /dev/null
    pip3 install pysnmp -i http://pypi.douban.com/simple/ --trusted-host pypi.douban.com &> /dev/null
    pip3 install psutil -i http://pypi.douban.com/simple/ --trusted-host pypi.douban.com &> /dev/null
    echo "$(date "+%Y-%m-%d %H:%M:%S") python所需的外置库已全部安装"
}
# 创建服务并运行
create_ystemd_service() {
    script_path="/opt/auto_pcdn/auto_pcdn.py"
    echo "$(date "+%Y-%m-%d %H:%M:%S") 开始创建auto_pcdn.py脚本并写进系统服务运行..."
    service_content="[Unit]\nDescription=AutoPCDN\nAfter=network.target\n\n[Service]\nExecStart=/usr/bin/python3 $script_path\nRestart=always\nUser=root\nWorkingDirectory=/opt/auto_pcdn\n\n[Install]\nWantedBy=multi-user.target\n"
    service_file_path='/etc/systemd/system/auto_pcdn.service'
    echo -e "$service_content" > "$service_file_path"

    systemctl daemon-reload &> /dev/null
    systemctl enable auto_pcdn.service &> /dev/null
    systemctl start auto_pcdn.service &> /dev/null
    echo "$(date "+%Y-%m-%d %H:%M:%S") AtuoPCDN程序已创建并写进系统服务并设置成开机自启"
}
check_log() {
    log_file="/opt/auto_pcdn/log/auto_pcdn.log"
    search_string="程序实时日志"
    timeout=600  # 设置超时时间为600秒
    elapsed_time=0

    while [ $elapsed_time -lt $timeout ]; do
        # 检查日志文件中是否包含特定字符
        if grep -q "$search_string" "$log_file"; then
            sleep 3
            echo "$(date "+%Y-%m-%d %H:%M:%S") 执行结束！"
            break
        fi
        sleep 1
        ((elapsed_time++))
    done
    sleep 1
    if [ $elapsed_time -ge $timeout ]; then
        echo "$(date "+%Y-%m-%d %H:%M:%S") 超时退出...请检查！"
    fi
}

# 检查服务状态
status=$(service auto_pcdn status > /dev/null 2>&1 && echo "active" || echo "inactive")
if [ "$status" = "active" ]; then
    echo -e "$(date "+%Y-%m-%d %H:%M:%S") 检测到auto_pcdn已经处于Active状态。\n"
    service auto_pcdn status
    echo -e "\n$(date "+%Y-%m-%d %H:%M:%S") 操作已取消。"
    exit 1
fi

# 校准时间时区
sudo yum install -y ntpdate &> /dev/null && sudo ntpdate time.windows.com &> /dev/null && sudo timedatectl set-timezone Asia/Shanghai &> /dev/null && sudo hwclock --systohc &> /dev/null
# 写入machineTag到系统内
mkdir -p /opt/auto_pcdn/info && echo "@@MACHINETAG@@" > /opt/auto_pcdn/info/machineTag.info
echo "$(date "+%Y-%m-%d %H:%M:%S") machineTag已写入系统内"

# 下载auto_pcdn脚本程序
curl -o /opt/auto_pcdn/auto_pcdn.tar.gz -L https://gitee.com/yuanzichaopu/auto_pppoe/releases/download/auto_pcdn_v1.2/auto_pcdn.tar.gz
echo "$(date "+%Y-%m-%d %H:%M:%S") auto_pcdn监管程序下载完成"
cd /opt/auto_pcdn/
tar -zxvf  auto_pcdn.tar.gz &> /dev/null
rm -rf auto_pcdn.tar.gz
echo "$(date "+%Y-%m-%d %H:%M:%S") 已经将监管程序包解压至/opt/auto_pppoe/目录下"

# 安装yum源插件
yum install yum-fastestmirror -y &> /dev/null
echo "$(date "+%Y-%m-%d %H:%M:%S") 已安装yum源自动选择插件，会自动优先选择最快的yum源"

# 安装基础环境
install_python3_env

# 启动服务并检查日志
touch /opt/auto_pcdn/log/auto_pcdn.log
create_systemd_service
tail -f /opt/auto_pcdn/log/auto_pcdn.log &
TAIL_PID=$!
check_log
kill $TAIL_PID