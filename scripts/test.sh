check_bbr_status() {
    local param=$(sysctl net.ipv4.tcp_congestion_control | awk '{print $3}')
    if [[ x"${param}" == x"bbr" ]]; then
        return 0
    else
        return 1
    fi
}

if check_bbr_status; then
  echo "Enabling BBR..."
else
  echo "BBR is already enabled"

fi