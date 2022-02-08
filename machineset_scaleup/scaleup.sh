#!/bin/bash
declare idrac_password
declare idrac_user
declare dnsmasq_file
declare json_inventory
declare power_off="no"
declare existing_worker_nodes=$(( $((`oc get node --no-headers|grep worker|wc -l`)) + 1 ))
function ctrl_c() {
        echo "** CTRL-C detected"
        exit
}

while [ $# -gt 0 ]; do
  case "$1" in
    --dnsmasq-file*|-d*)
      if [[ "$1" != *=* ]]; then shift; fi # Value is next arg if no `=`
      dnsmasq_file="${1#*=}"
      ;;
    --json-inventory-file*|-j*)
      if [[ "$1" != *=* ]]; then shift; fi
      json_inventory="${1#*=}"
      ;;
    --power-off*|-p*)
      if [[ "$1" != *=* ]]; then shift; fi
      power_off="${1#*=}"
      if [ ${power_off} != "yes" ] && [ ${power_off} != "no" ] ; then
	      echo "power-off" only accpet "yes" or "no"
	      exit
      fi
      ;;
    --help|-h)
      echo "--dnsmasq-file   -d   ocp dnsmasq conf file normally found at /etc/dnsmasq.d/ocp4-lab.conf"
      echo "--json-inventory -j   scale lab json inventory file that contains only the nodes you wish to add"
      echo "--power-off -p   power off all new worker nodes before starting yes/no default is no"
      exit 0
      ;;
    *)
      >&2 printf "Error: Invalid argument\n"
      exit 1
      ;;
  esac
  shift
done

declare how_many_new_nodes=(`jq '.[] | length' ${json_inventory}`)

scale_up(){
deployment_name=(`oc get machineset -n openshift-machine-api |grep test|awk '{print $1}'`)
echo "scaling ${deployment_name} up to $(( ${how_many_new_nodes} + `oc get node --no-headers|grep worker|wc -l`)) worker nodes"
oc scale --replicas=$(( ${how_many_new_nodes} + `oc get node --no-headers|grep worker|wc -l`))  machineset ${deployment_name} -n openshift-machine-api
}

function box_out()
{
  local s=("$@") b w
  for l in "${s[@]}"; do
    ((w<${#l})) && { b="$l"; w="${#l}"; }
  done
  tput setaf 1
  echo " -${b//?/-}-
| ${b//?/ } |"
  for l in "${s[@]}"; do
    printf '| %s%*s%s |\n' "$(tput setaf 7)" "-$w" "$l" "$(tput setaf 1)"
  done
  echo "| ${b//?/ } |
 -${b//?/-}-"
  tput sgr 0
}

acceept_new_workers_certificates(){
echo "approving new workers certificates for ${how_many_new_nodes} nodes - note this will keep running in the background"
until [ $(oc get nodes | grep "\bReady\s*worker" | wc -l) == ${json_inventory} ]
do
    csr_output=$(oc get csr -ojson | jq -r '.items[] | select(.status == {} ) | .metadata.name')
    if [ -n "$csr_output" ]
    then
    	echo "$csr_output" | xargs oc adm certificate approve
    fi
    sleep 5
done
}

get_idrac_credentials(){
        if [ -z "${json_inventory}" ];  then
        echo "somthing went wrong with the json file , exiting.."
        exit
fi
        idrac_user=`jq -r '.nodes[0] | .pm_user' ${json_inventory} |xargs echo -n |base64`
        idrac_password=`jq -r '.nodes[0] | .pm_password' ${json_inventory}|xargs echo -n|base64`
}

generate_workers_config(){
if [ -z "${json_inventory}" ];  then
        echo "no inventory file was provided , exiting.."
        exit
fi

ip_offset=15
first_node_to_add=$((1 + `oc get node --no-headers|grep worker|wc -l`))

cleanup(){
        rm -rf workers/
        mkdir workers/
}

add_dns(){
        dnsmasq_mac=$1
        current_node=$2
	worker_name=$3
	last_dhcp_line=$(( $(awk '/dhcp/ { ln = FNR } END { print ln }' ${dnsmasq_file}) ))
	sed -i "$last_dhcp_line a dhcp-host=$dnsmasq_mac,192.168.216.$(( ip_offset + current_node )),${worker_name}" ${dnsmasq_file}
}


add_bmh(){
        provisioning_mac=$1
	worker_name=$2
        ipmi_dns=$3
	sed -e "s/IPMI_ADDRESS/${ipmi_dns}/g" -e "s/WORKER-NAME/${worker_name}/g" -e "s/PROVISIONING-MAC/${provisioning_mac}/g" -e "s/IDRAC-USER/${idrac_user}/g" -e "s/IDRAC-PASSWORD/${idrac_password}/g" template.yml >> workers/${worker_name}.yml
}


cleanup

for (( i=0; i< $(( ${how_many_new_nodes} )); i++ )) ; do
	worker_name=$(echo "worker"$(printf "%.3d" $(( existing_worker_nodes + i ))))
        provisioning_mac=$( jq -r .nodes[$i].mac[1] ${json_inventory} )
        dnsmasq_mac=$( jq -r .nodes[$i].mac[2] ${json_inventory} )
        ipmi_controller_dns=$( jq -r .nodes[$i].pm_addr ${json_inventory} )
        add_dns "$dnsmasq_mac" "$i" "${worker_name}"
        add_bmh "${provisioning_mac}" "${worker_name}" "${ipmi_controller_dns}"
done
}

ipmi_power_off(){
if [ ${power_off} = "yes" ] ; then
	echo "powering off all ${how_many_new_nodes} worker nodes found in ${json_inventory}"
	for ((i=0; i<${how_many_new_nodes}; i++)); do
		echo "powering off `jq -r .nodes[$i].pm_addr ${json_inventory}|sed 's/mgmt-//g'`"
	ipmitool -I lanplus -H `jq -r .nodes[$i].pm_addr ${json_inventory}` -L ADMINISTRATOR -p 623 -U `echo -n "${idrac_user}"|base64 -d` -P `echo -n "${idrac_password}"|base64 -d` chassis power off > /dev/null 2>&1
done
else
	echo "skipping worker nodes shutdown note that workers nodes should be powered off during deployment"
fi
}

start_scaling(){
	box_out "Found `oc get node --no-headers|grep worker|wc -l` worker nodes already exist on the cluster." "There are ${how_many_new_nodes} new nodes in the ${json_inventory} file." "This script will add  workers$( seq -w 000 $(( existing_worker_nodes ))|tail -1 ) to worker$( seq -w 000 $(( how_many_new_nodes + existing_worker_nodes ))|tail -1 )" "Will also update dhcp information in ${dnsmasq_file}" "New workers yamls will be saved to \"workers\" directory"

read -r -p "Are you sure you wish to continue? [y/N] " response
case "$response" in
    [yY][eE][sS]|[yY])
	
        scale_up	
        echo "getting cloud credentials"
	get_idrac_credentials
	echo "generating worker nodes yaml files and adding dns information to ${dnsmasq_file}"
	generate_workers_config
	echo "restarting dnsmasq"
	service dnsmasq restart
	ipmi_power_off
	acceept_new_workers_certificates &
	oc create -f workers
	box_out "you can follow the deployment progress using \"oc get bmh\""



        ;;
    *)
        echo "not so sure arn't we..."
	exit
        ;;
esac
}

start_scaling
