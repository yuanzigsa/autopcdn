#!/usr/bin/env bash
#===============================================================================
#Time : 23-3-14 下午15:18
#Author : tieshou@douyu.tv
#Team:  ops-dev@douyu.tv
#File :
#Software: GoLand
#Project: cruiser-agent
#Date:23-3-14
#Description:
#===============================================================================

if command -v python3.10 >/dev/null 2>&1; then
    distname=`python3.10 -c 'import distro; print(distro.id().lower())'`
    version=`python3.10 -c 'import distro; print(distro.version().lower())'`
    # cat /etc/redhat-release |sed -r 's/.* ([0-9]+)\..*/\1/'
    version=`echo $version|sed -r 's/([0-9]+)\..*/\1/'`
else
    distname=`python -c 'import platform; print(platform.linux_distribution()[0].split()[0].lower())'`
    version=`python -c 'import platform; print(platform.linux_distribution()[1].lower())'`
    # cat /etc/redhat-release |sed -r 's/.* ([0-9]+)\..*/\1/'
    version=`echo $version|sed -r 's/([0-9]+)\..*/\1/'`
fi

case $distname in
debian|ubuntu|devuan)
    case $version in
    14)
        echo "Start install cruiser-agent, current os platform is ubuntu14.04"
        sudo wget -O cruiser-agent-last-stable.14_amd64.deb https://ops-docker-hub-test.oss-cn-beijing.aliyuncs.com/cruiser-agent/cruiser-agent-last-stable-public.14_amd64.deb
        sudo dpkg -i cruiser-agent-last-stable.14_amd64.deb
        sudo rm -f cruiser-agent-last-stable.14_amd64.deb
        sudo sysv-rc-conf cruiser-agent on
        sudo /etc/init.d/cruiser-agent stop
        sudo /etc/init.d/cruiser-agent start
        echo "finish! start cruiser-agent!"
        ;;

    *)
        echo "Start install cruiser-agent, current os platform is ubuntu"
        sudo wget -O cruiser-agent-last-stable_amd64.deb https://ops-docker-hub-test.oss-cn-beijing.aliyuncs.com/cruiser-agent/cruiser-agent-last-stable-public_amd64.deb
        sudo dpkg -i cruiser-agent-last-stable_amd64.deb
        sudo rm -f cruiser-agent-last-stable_amd64.deb
        sudo systemctl daemon-reload
        sudo systemctl enable cruiser-agent
        sudo systemctl restart cruiser-agent
        echo "finish! start cruiser-agent!"
        ;;
    esac
    ;;

centos|fedora|rhel)
    case $version in
    5|6)
        echo "Start install cruiser-agent, current os platform is centos < 7"
        sudo wget -O cruiser-agent-last-stable.el6.x86_64.rpm https://ops-docker-hub-test.oss-cn-beijing.aliyuncs.com/cruiser-agent/cruiser-agent-last-stable-public.el6.x86_64.rpm

        sudo rpm -Uvh cruiser-agent-last-stable.el6.x86_64.rpm
        sudo rm -f cruiser-agent-last-stable.el6.x86_64.rpm
        sudo chkconfig --add cruiser-agent
        sudo /etc/init.d/cruiser-agent stop
        sudo /etc/init.d/cruiser-agent start
        echo "finish! start cruiser-agent!"
        ;;
    7|8)
        echo "Start install cruiser-agent, current os platform is centos = 7"

        sudo wget -O cruiser-agent-last-stable.el7.x86_64.rpm https://ops-docker-hub-test.oss-cn-beijing.aliyuncs.com/cruiser-agent/cruiser-agent-last-stable-public.el7.x86_64.rpm

        sudo rpm -Uvh cruiser-agent-last-stable.el7.x86_64.rpm
        sudo rm -f cruiser-agent-last-stable.el7.x86_64.rpm
        sudo systemctl daemon-reload
        sudo systemctl enable cruiser-agent
        sudo systemctl restart cruiser-agent
        echo "finish! start cruiser-agent!"
        ;;
    *)
        echo "Unkown Centos Version!"
        exit 1
        ;;
    esac
    ;;
*)
    echo "Unkown Platform !"
    exit 1
    ;;
esac
