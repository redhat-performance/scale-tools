import argparse
import paramiko
import multiprocessing
import time
import os
import socket
timeout_seconds = 3

def add_ssh_key_to_remote_host(hostname, username, password):
    try:
        # Copy SSH key to remote host
        os.system(f'sshpass -p "{password}" ssh-copy-id -f -i /etc/ceph/ceph.pub {username}@{hostname}')
        return f'SSH key added to {hostname}'
    except Exception as e:
        print(f'Error adding SSH key to {hostname}: {str(e)}')
        return ''

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

        # Skip file copying if the host is the same as the current host
        if host == socket.gethostname():
            print("Skipping file copying for the local host.")
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

   #copy ceph conf file to all the hosts
    file_name = '/etc/ceph/ceph.conf'
    file_path = '/etc/ceph/'
    for host in hosts:
        #print("copying file " + file_name + " to remote host " + host)
        copy_file_to_remote_hosts(host, args.user, args.password, file_name, file_path)

   #copy ceph key file to all the hosts
    file_name = '/etc/ceph/ceph.client.admin.keyring'
    file_path = '/etc/ceph/'
    for host in hosts:
        copy_file_to_remote_hosts(host, args.user, args.password, file_name, file_path)

    # Copy SSH key to each host
    pool = multiprocessing.Pool(processes=len(hosts))
    results = [pool.apply_async(add_ssh_key_to_remote_host, (host, args.user, args.password)) for host in hosts]
    pool.close()
    pool.join()
    for r in results:
        output = r.get()
        print(f'{output} ({r.get()})')
