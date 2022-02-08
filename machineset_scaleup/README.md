# scaleup
This tool is using machinset to scaleup the number of OpenShift workers at the RedHat Scale Lab environment.

### scaleup.sh -h
```
--dnsmasq-file   -d   ocp dnsmasq conf file normally found at /etc/dnsmasq.d/ocp4-lab.conf
--json-inventory -j   scale lab json inventory file that contains only the nodes you wish to add
--power_off -p   power off all new worker nodes before starting yes/no default is no
```

### how to run
```
./scale_up.sh -j ocpnodeinv.json -d /etc/dnsmasq.d/ocp4-lab.conf

 --------------------------------------------------------------
|                                                              |
| Found 95 worker nodes already exist on the cluster.          |
| There are 94 new nodes in the ocpnodeinv.json file.          |
| This script will add  workers096 to worker190                |
| Will also update dhcp information in ocp4-lab.conf           |
| New workers yamls will be saved to "workers" directory       |
|                                                              |
 --------------------------------------------------------------
Are you sure you wish to continue? [y/N]
```
