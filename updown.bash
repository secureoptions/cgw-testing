#!/bin/bash
# This is the updown script has been adapted from the solution found here (Credits: http://end.re/2015-01-06_vti-tunnel-interface-with-strongswan.html)
# 
while [[ $# > 1 ]]; do
    case ${1} in
        -ln|--link-name)
            TUNNEL_NAME="${2}"
            TUNNEL_PHY_INTERFACE="${PLUTO_INTERFACE}"
            shift # past argument
            ;;
        -ll|--link-local)
            TUNNEL_LOCAL_ADDRESS="${2}"
            TUNNEL_LOCAL_ENDPOINT="${PLUTO_ME}"
			      TUNNEL_REAL_ENDPOINT=$(curl --retry 3 --silent http://169.254.169.254/latest/meta-data/local-ipv4)
            shift # past argument
        ;;
        -lr|--link-remote)
            TUNNEL_REMOTE_ADDRESS="${2}"
            TUNNEL_REMOTE_ENDPOINT="${PLUTO_PEER}"
            shift # past argument
        ;;
        -m|--mark)
            TUNNEL_MARK="${2}"
            shift # past argument
        ;;
        -t|--type)
            TYPE="${2}"
            shift #past argument
        ;;
        *)
            # unknown option
        echo "${0}: Unknown argument \\"${1}\\"" >&2
        ;;
    esac
    shift # past argument or value
done

#import any needed variables from user data
IP_TARGET=$(echo "$TUNNEL_REMOTE_ADDRESS" | grep -oP "[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}")
PID_FILE=/etc/cloudshroud/.PID_${TUNNEL_NAME}
BGPDCONF=/etc/quagga/bgpd.conf

command_exists() {
    type "$1" >&2 2>&2
}

create_interface() {
	sudo ip link add ${TUNNEL_NAME} type vti local ${TUNNEL_REAL_ENDPOINT} remote ${TUNNEL_REMOTE_ENDPOINT} key ${TUNNEL_MARK}
	sudo ip addr add ${TUNNEL_LOCAL_ADDRESS} remote ${TUNNEL_REMOTE_ADDRESS} dev ${TUNNEL_NAME}
	sudo ip link set ${TUNNEL_NAME} up mtu 1436
}

enable_kernel() {
	sudo sysctl -w net.ipv4.ip_forward=1 
	sudo sysctl -w net.ipv4.conf.${TUNNEL_NAME}.rp_filter=2 
	sudo sysctl -w net.ipv4.conf.${TUNNEL_NAME}.disable_policy=1 
	sudo sysctl -w net.ipv4.conf.${TUNNEL_PHY_INTERFACE}.disable_xfrm=1 
	sudo sysctl -w net.ipv4.conf.${TUNNEL_PHY_INTERFACE}.disable_policy=1
}
add_route() {
	if [ "${TYPE}" == "dynamic" ]
	then
		sudo service zebra restart
		sudo service bgpd restart
	else
		# if not using BGP, create a static route. ASN here is the CIDR really
		sudo ip route add ${TYPE} dev ${TUNNEL_NAME}
    fi
	sudo iptables -t mangle -A FORWARD -o ${TUNNEL_NAME} -p tcp --tcp-flags SYN,RST SYN -j TCPMSS --clamp-mss-to-pmtu
	sudo iptables -t mangle -A INPUT -p esp -s ${TUNNEL_REMOTE_ENDPOINT} -d ${TUNNEL_LOCAL_ENDPOINT} -j MARK --set-xmark ${TUNNEL_MARK}
	sudo ip route flush table 220
}
ping_up() {
	nohup ping -i 5 -W 1 ${IP_TARGET} > /dev/null 2>&1 &
	echo $! > $PID_FILE
}
ping_down() {
	PID=$(cat $PID_FILE)
	kill -9 "$PID"
	rm -f $PID_FILE
}

cleanup_settings() {
    iptables -t mangle -D FORWARD -o ${TUNNEL_NAME} -p tcp --tcp-flags SYN,RST SYN -j TCPMSS --clamp-mss-to-pmtu
	iptables -t mangle -D INPUT -p esp -s ${TUNNEL_REMOTE_ENDPOINT} -d ${TUNNEL_LOCAL_ENDPOINT} -j MARK --set-xmark ${TUNNEL_MARK}
	ip route flush cache
}
delete_interface() {
	sudo ip link set ${TUNNEL_NAME} down mtu 1436
	sudo ip link del ${TUNNEL_NAME}
}
command_exists ip || echo "ERROR: ip command is required to execute the script, check if you are running as root, mostly to do with path, /sbin/" >&2 2>&2
command_exists iptables || echo "ERROR: iptables command is required to execute the script, check if you are running as root, mostly to do with path, /sbin/" >&2 2>&2
command_exists sysctl || echo "ERROR: sysctl command is required to execute the script, check if you are running as root, mostly to do with path, /sbin/" >&2 2>&2

case "${PLUTO_VERB}" in
    up-client)
        create_interface
        enable_kernel
        add_route
		ping_up
        ;;
    down-client)
		ping_down
        cleanup_settings
        delete_interface
        ;;
esac
