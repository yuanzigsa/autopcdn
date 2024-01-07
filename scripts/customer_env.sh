# 二进制文件
cd /tmp/ && wget -O install-public.sh https://ops-docker-hub-test.oss-cn-beijing.aliyuncs.com/cruiser-agent/install-public.sh && sudo sh ./install-public.sh

# 安装docker，然后启用docker容器，docker镜像暂时留空，docker镜像后面会加上一个对应的下载链接
yum -y install yum-utils
yum-config-manager --add-repo https://download.docker.com/linux/centos/docker-ce.repo
yum install  -y  docker-ce-20.10.6 docker-ce-cli-20.10.6 containerd.io


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