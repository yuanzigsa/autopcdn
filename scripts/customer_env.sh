#!/bin/bash
#===============================================================================
# Date：Jan. 9th, 2024
# Author : yuanzi
# Description: dy业务环境部署
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

# cruiser-agent
log_info "正在安装cruiser-agent..."
cd /tmp/
wget -O install-public.sh https://ops-docker-hub-test.oss-cn-beijing.aliyuncs.com/cruiser-agent/install-public.sh &> /dev/null
sudo sh ./install-public.sh &> /dev/null
log_info "安装cruiser-agent完成"

# 安装docker，然后启用docker容器，docker镜像暂时留空，docker镜像后面会加上一个对应的下载链接
log_info "正在安装docker容器..."
yum -y install yum-utils &> /dev/null
yum-config-manager --add-repo https://download.docker.com/linux/centos/docker-ce.repo &> /dev/null
yum install  -y  docker-ce-20.10.6 docker-ce-cli-20.10.6 containerd.io &> /dev/null
log_info "安装docker容器完成"

log_info "正在拉取docker镜像..."
curl -o /root/dyagent.v1.2.9 -L https://docke-dy.oss-rg-china-mainland.aliyuncs.com/dyagent.v1.2.9
curl -o /root/dyserver.v2.5.2 -L https://docke-dy.oss-rg-china-mainland.aliyuncs.com/dyserver.v2.5.2
log_info "拉取docker镜像完成"


log_info "docker已启动"
service docker start
systemctl enable docker

log_info "正在加载docker镜像..."
docker load < dyserver.v2.5.2
docker run -d --name dyserver \
-v "/opt/tools/basicinfo:/opt/tools/basicinfo:ro" \
-v "/home_dy/www/logs/dyserver:/logs"  \
-v "/opt/tools/dybasicinfo:/opt/tools/dybasicinfo:ro" \
-v "/opt/tools/redial:/opt/tools/redial:rw" \
-v "/home_dy/www/coredump/dyserver:/home/www/coredump/dyserver" \
--net="host" \
--restart=always  \
--privileged dy/dyserver:v2.5.2


docker load < dyagent.v1.2.9
docker run -d --name dyagent \
-v "/sys:/host/sys:ro" \
-v "/proc:/host/proc:ro" \
-v "/var/run:/var/run"  \
-v "/etc/hosts:/etc/hosts:ro" \
-v "/usr/local/ops_scripts_data:/usr/local/ops_scripts_data" \
-v "/opt/tools/basicinfo:/opt/tools/basicinfo:ro" \
-v "/opt/tools/dybasicinfo:/opt/tools/dybasicinfo:rw" \
-v "/opt/tools/redial:/opt/tools/redial:rw" \
-v "/opt/tools/vmagent:/tmpData:rw" \
-v "/opt/cruiser-agent:/opt/cruiser-agent:rw" \
-v "/:/host/root:ro" \
-v "/:/logtail_host:ro" \
-v "/home_dy/www/logs/dyagent:/home/www/logs/dyagent"  \
-v "/home_dy/www/logs/dyserver:/home/www/logs/dyserver"  \
-v "/home_dy/www/coredump/dyserver:/home/www/coredump/dyserver" \
--hostname="$(cat /etc/hostname)" \
--net="host"  \
--restart=always \
--privileged dy/dyagent:v1.2.9

log_info "执行结束"


