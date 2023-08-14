import argparse
import paramiko
import socket
import os
import multiprocessing
import subprocess
import sys


def reboot_remote_host(host, user, password):
    """
    Reboots a remote host using SSH.

    Parameters:
    host (str): The hostname or IP address of the remote host.
    user (str): The username to use for SSH authentication.
    password (str): The password to use for SSH authentication.

    Returns:
    None
    """
    try:
        # Skip rebooting if the host is the same as the current host
        if host == socket.gethostname():
            print("Skipping reboot for the local host.")
            return

        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(host, username=user, password=password)

        # Execute the reboot command on the remote host
        ssh.exec_command("sudo reboot")

        ssh.close()

        print(f"Successfully initiated reboot for remote host '{host}'")
    except Exception as e:
        print(f"Error rebooting remote host '{host}': {str(e)}")

def run_command_on_remote_host(hostname, command, username, password):
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(hostname, username=username, password=password)
    stdin, stdout, stderr = client.exec_command(command)
    output = stdout.read().decode()
    client.close()
    return output

def add_host_to_known_hosts(hostname):
    try:
        # Add host to local known_hosts file
        os.system(f'ssh-keyscan -H {hostname} >> ~/.ssh/known_hosts')
        return f'{hostname} added to known_hosts file'
    except Exception as e:
        print(f'Error adding {hostname} to known_hosts file: {str(e)}')
        return ''

def add_ssh_key_to_remote_host(hostname, username, password):
    try:
        # Copy SSH key to remote host
        os.system(f'sshpass -p "{password}" ssh-copy-id {username}@{hostname}')
        return f'SSH key added to {hostname}'
    except Exception as e:
        print(f'Error adding SSH key to {hostname}: {str(e)}')
        return ''

def generate_ssh_key_on_remote_host(hostname, username, password):
    try:
        # Generate SSH key on remote host
        os.system(f'sshpass -p "{password}" ssh {username}@{hostname} "if [ ! -f /root/.ssh/id_rsa.pub ]; then ssh-keygen -t rsa -b 2048 -N \'\' -f ~/.ssh/id_rsa ; fi"')
        return f'SSH key generated on {hostname}'
    except Exception as e:
        print(f'Error generating SSH key on {hostname}: {str(e)}')
        return ''

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Setup Ceph on a set of hosts')
    parser.add_argument('-hf', '--hosts_file', required=True, help='The file containing the hosts to setup')
    parser.add_argument('-u', '--user', required=True, help='The SSH username to use for connecting to the hosts')
    parser.add_argument('-p', '--password', required=True, help='The SSH password to use for connecting to the hosts')
    args = parser.parse_args()

# Read hosts from file
    with open(args.hosts_file) as f:
        hosts = f.read().splitlines()

    # Add each host to local known_hosts file
    for host in hosts:
        output = add_host_to_known_hosts(host)
        print(f'{output} ({host})')

    # Copy SSH key to each host
    pool = multiprocessing.Pool(processes=len(hosts))
    results = [pool.apply_async(add_ssh_key_to_remote_host, (host, args.user, args.password)) for host in hosts]
    pool.close()
    pool.join()
    for r in results:
        output = r.get()
        print(f'{output} ({r.get()})')

    # Generate SSH key on each host, if not already present
    for host in hosts:
        output = generate_ssh_key_on_remote_host(host, args.user, args.password)
        print(f'{output} ({host})')

    #register subscription-manager
    pool = multiprocessing.Pool(processes=len(hosts))
    results = [pool.apply_async(run_command_on_remote_host, (host, "subscription-manager register --username user --password password --auto-attach", args.user, args.password)) for host in hosts]
    pool.close()
    pool.join()
    for r in results:
        output = r.get()
        print(f'{output} ({r.get()})')


    #update rhel hosts
    pool = multiprocessing.Pool(processes=len(hosts))
    results = [pool.apply_async(run_command_on_remote_host, (host, "~/./update-latest-rhel-release.sh 8.7;dnf update -y", args.user, args.password)) for host in hosts]
    pool.close()
    pool.join()
    for r in results:
        output = r.get()
        print(f'{output} ({r.get()})')

    #attach needed repos
    pool = multiprocessing.Pool(processes=len(hosts))
    results = [pool.apply_async(run_command_on_remote_host, (host, "subscription-manager repos --enable=rhel-8-for-x86_64-baseos-rpms --enable=ansible-2.9-for-rhel-8-x86_64-rpms --enable=rhceph-5-tools-for-rhel-8-x86_64-rpms --enable rhel-8-for-x86_64-appstream-rpms", args.user, args.password)) for host in hosts]
    pool.close()
    pool.join()
    for r in results:
        output = r.get()
        print(f'{output} ({r.get()})')

    #install required packages
    pool = multiprocessing.Pool(processes=len(hosts))
    results = [pool.apply_async(run_command_on_remote_host, (host, "dnf install podman ansible cephadm-ansible cephadm gdisk -y", args.user, args.password)) for host in hosts]
    pool.close()
    pool.join()
    for r in results:
        output = r.get()
        print(f'{output} ({r.get()})')


    #disable ip tables
    pool = multiprocessing.Pool(processes=len(hosts))
    results = [pool.apply_async(run_command_on_remote_host, (host, "systemctl stop iptables ; systemctl disable iptables", args.user, args.password)) for host in hosts]
    pool.close()
    pool.join()
    for r in results:
        output = r.get()
        print(f'{output} ({r.get()})')


    #login to podman
    pool = multiprocessing.Pool(processes=len(hosts))
    results = [pool.apply_async(run_command_on_remote_host, (host, "podman login -u user -p password registry.redhat.io", args.user, args.password)) for host in hosts]
    pool.close()
    pool.join()
    for r in results:
        output = r.get()
        print(f'{output} ({r.get()})')

    #reboot remote hosts
    pool = multiprocessing.Pool(processes=len(hosts))
    results = [pool.apply_async(reboot_remote_host, (host, args.user, args.password)) for host in hosts]
    pool.close()
    pool.join()
