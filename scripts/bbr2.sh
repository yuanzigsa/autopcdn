#!/bin/bash

update_kernel_and_open_bbr(){
    # 安装依赖工具
    yum install -y wget
    # 下载ELRepo的RPM包
    wget https://www.elrepo.org/elrepo-release-7.el7.elrepo.noarch.rpm
    # 安装ELRepo的RPM包
    rpm -Uvh elrepo-release-7.el7.elrepo.noarch.rpm
    # 安装新的内核
    yum --enablerepo=elrepo-kernel install -y kernel-ml
    # 更新GRUB配置
    grub2-mkconfig -o /boot/grub2/grub.cfg
    # 设置默认启动内核
    grub2-set-default 0
    # 开启BBR
    echo "net.core.default_qdisc=fq" >> /etc/sysctl.conf
    echo "net.ipv4.tcp_congestion_control=bbr" >> /etc/sysctl.conf
    # 应用sysctl.conf配置
    sysctl -p
}

# 检查是否已经启用BBR
bbr_status=$(sysctl net.ipv4.tcp_congestion_control | awk -F= '{print $2}' | tr -d ' ')

if [ "$bbr_status" == "bbr" ]; then
    echo "BBR已经启用"
else
    echo "BBR未启用"

fi


read -p "内核升级并开启BBR完成，是否要重启系统？ (y/n): " choice
if [ "$choice" == "y" ] || [ "$choice" == "Y" ]; then
    echo "正在重启系统以应用新的内核，预计需要几十秒，重启成功后请再次执行：AutoPCDN-初始部署"
    reboot
else
    echo "请手动重启系统以应用新的内核。"
fi
