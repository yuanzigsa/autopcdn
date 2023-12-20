


ifconfig_content = f"TYPE=vlan\nPROXY_METHOD=none\nBROWSER_ONLY=no\nBOOTPROTO=static\nDEFROUTE=yes\nIPV4_FAILURE_FATAL=no\nIPV6INIT=yes\nIPV6_AUTOCONF=yes\nIPV6_DEFROUTE=yes\nIPV6_FAILURE_FATAL=no\nIPV6_ADDR_GEN_MODE=stable-privacy\nNAME={ifname}.{vlanid}\nDEVICE={ifname}.{vlanid}\nVLAN_ID={vlanid}\nVLAN=yes\nONBOOT=yes\nMACADDR={macaddr}\n"