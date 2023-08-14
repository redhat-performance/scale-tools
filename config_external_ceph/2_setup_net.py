import argparse
import paramiko
import multiprocessing
import time
import os
timeout_seconds = 3

def create_network_bond_on_remote_host(host, user, password):
    """
    Creates a network bond on the specified remote host using the NetworkManager command-line tool.

    Parameters:
    host (str): The hostname or IP address of the remote host.
    user (str): The username to use for SSH authentication.
    password (str): The password to use for SSH authentication.

    Returns:
    None
    """
    # Define bond name and options
    bond_name = 'bond0'
    bond_options = 'mode=balance-alb'

    # Get list of network interfaces starting with 'ens'
    command = 'ls /sys/class/net | grep ^ens'
    interfaces = run_command_on_remote_host(host, command, user, password)
    interfaces = interfaces.strip().split('\n')

    # Add bond to NetworkManager
    print(f'nmcli connection add type bond ifname {bond_name} bond.options "{bond_options}"')
    command = f'nmcli connection add type bond ifname {bond_name} bond.options "{bond_options}"'
    output = run_command_on_remote_host(host, command, user, password)
    print(f'{output} ({host})')

    # Add interfaces to bond
    for i, interface in enumerate(interfaces):
        command = f'nmcli connection add type ethernet slave-type bond con-name {bond_name}-port{i+1} ifname {interface} master {bond_name}'
        output = run_command_on_remote_host(host, command, user, password)
        print(f'{output} ({host})')

    # Set primary interface
    command = f'nmcli dev mod {bond_name} +bond.options "primary={interfaces[0]}"'
    output = run_command_on_remote_host(host, command, user, password)
    print(f'{output} ({host})')

    # Set active slave interface and reload NetworkManager
    command = f'nmcli dev mod {bond_name} +bond.options "active_slave={interfaces[1]}"'
    output = run_command_on_remote_host(host, command, user, password)
    print(f'{output} ({host})')

    command = 'nmcli con reload'
    output = run_command_on_remote_host(host, command, user, password)
    print(f'{output} ({host})')

    # Run ifdown on ens interfaces and ifup on bond
    for interface in interfaces:
        command = f'sudo ifdown {interface}'
        output = run_command_on_remote_host(host, command, user, password)
        print(f'{output} ({host})')

    command = f'sudo ifup {bond_name}'
    output = run_command_on_remote_host(host, command, user, password)
    print(f'{output} ({host})')

def copy_file_to_remote_hosts(host, user, password, file_name, file_path):
    """
    Copies a file to a remote host using SSH and SFTP.

    Parameters:
    host (str): The hostname or IP address of the remote host.
    user (str): The username to use for SSH authentication.
    password (str): The password to use for SSH authentication.
    file_name (str): The name of the file to copy.
    file_path (str): The path where the file should be copied to.

    Returns:
    None
    """
    try:
        local_file_path = os.path.abspath(file_name)
        if not os.path.isfile(local_file_path):
            print(f"Source file '{file_name}' does not exist or is not a file.")
            return

        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(host, username=user, password=password)

        # Create the destination directory if it doesn't exist
        ssh.exec_command(f'mkdir -p {file_path}')

        sftp = ssh.open_sftp()
        sftp.put(local_file_path, os.path.join(file_path, os.path.basename(file_name)))
        sftp.close()
        ssh.close()

        print(f"Successfully copied file '{file_name}' to remote host '{host}'")
    except Exception as e:
        print(f"Error copying file '{file_name}' to remote host '{host}': {str(e)}")

def generate_dhcp_record(host, user, password):
    """
    Generates a DHCP record by retrieving the IP address and MAC address from a remote host.

    Parameters:
    host (str): The hostname or IP address of the remote host.
    user (str): The username to use for SSH authentication.
    password (str): The password to use for SSH authentication.

    Returns:
    str: The DHCP record.
    """
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(host, username=user, password=password)

    # Retrieve IP address and MAC address from remote host
    stdin, stdout, stderr = ssh.exec_command("ip -f inet addr show bond0 | awk '/inet / {split($2, a, \"/\"); print a[1]}'")
    ip_address = stdout.read().decode().strip()

    stdin, stdout, stderr = ssh.exec_command("ip -f link addr show bond0 | awk '/link\/ether/ {print $2}'")
    mac_address = stdout.read().decode().strip()

    # Generate DHCP record
    dhcp_record = f"dhcp-host={mac_address},{ip_address},{host},infinite"
    ssh.close()
    return dhcp_record


def run_command_on_remote_host(hostname, command, username, password):
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(hostname, username=username, password=password)
    stdin, stdout, stderr = client.exec_command(command)
    output = stdout.read().decode()
    client.close()
    return output

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Setup Ceph on a set of hosts')
    parser.add_argument('-hf', '--hosts_file', required=True, help='The file containing the hosts to setup')
    parser.add_argument('-u', '--user', required=True, help='The SSH username to use for connecting to the hosts')
    parser.add_argument('-p', '--password', required=True, help='The SSH password to use for connecting to the hosts')
    args = parser.parse_args()

# Read hosts from file
    with open(args.hosts_file) as f:
        hosts = f.read().splitlines()

    # clear uneeded NICs
    for host in hosts:
        print(f'Running on host {host}')
        output = run_command_on_remote_host(host, "for intf in $(nmcli conn show | grep '\.10' | awk '{ print $1 }') ; do nmcli conn down $intf; nmcli conn del $intf ; done", args.user, args.password)
        print(f'{output} ({host})')

    #create network bond
    pool = multiprocessing.Pool(processes=len(hosts))
    results = [pool.apply_async(create_network_bond_on_remote_host, (host , args.user, args.password)) for host in hosts]
    pool.close()
    pool.join()

#prevent ens interfaces to come up after reboot
    pool = multiprocessing.Pool(processes=len(hosts))
    results = [pool.apply_async(run_command_on_remote_host, (host, "sed -i 's/ONBOOT=yes/ONBOOT=no/g' /etc/sysconfig/network-scripts/ifcfg-ens*", args.user, args.password)) for host in hosts]
    pool.close()
    pool.join()

    #install tuned
    pool = multiprocessing.Pool(processes=len(hosts))
    results = [pool.apply_async(run_command_on_remote_host, (host, "dnf install tuned -y; systemctl start tuned; systemctl enable tuned", args.user, args.password)) for host in hosts]
    pool.close()
    pool.join()

   #copy rhcs conf file
    file_name = 'tuned.conf'
    file_path = '/etc/tuned/rhcs'
    for host in hosts:
        copy_file_to_remote_hosts(host, args.user, args.password, file_name, file_path)

    #setup tuned to use rhcs profile
    pool = multiprocessing.Pool(processes=len(hosts))
    results = [pool.apply_async(run_command_on_remote_host, (host, "tuned-adm profile rhcs", args.user, args.password)) for host in hosts]
    pool.close()
    pool.join()

    #sleep before collection dhcp info for DHCP conf
    time.sleep(20)

    #generate dhcp records
    for host in hosts:
        output = generate_dhcp_record(host, args.user, args.password)
        print(f'{output}')
