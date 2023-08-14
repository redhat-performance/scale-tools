# About
This is a python based tool which is used to configure an external RHCS cluster

### usage
I've divided the automation process into a step-by-step configuration. It's important to note that, in the context of this internal lab, I've taken the liberty of disabling the firewall. However, I strongly advise against this practice in a live production environment. Please ensure the creation of appropriate firewall rules that are necessary for your specific setup. It's advisable not to follow these steps blindly, as your configuration may differ from the one I've created this for. Some adjustments may be necessary.
```
prerequisite.sh - prerequisite required for the usage of the scripts
```
the files below required the following parameters - -hf/--hosts_file, -u/--user, -p/--password
the user/password reffer to the SSH user for the hosts, and assuming all hosts has the same user and password name
```
1_prepare_hosts.py 
2_setup_net.py
3_setup_ceph.py
4_clean_disks.py
```

### how to run example
```
python3.9 1_prepare_hosts.py -hf hosts_file -u root -p password
```
