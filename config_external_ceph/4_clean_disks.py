import argparse
import paramiko
import multiprocessing

def get_disk_list(host, user, password):
    """
    Retrieves the list of disks on a remote host using SSH and the lsblk command.

    Parameters:
    host (str): The hostname or IP address of the remote host.
    user (str): The username to use for SSH authentication.
    password (str): The password to use for SSH authentication.

    Returns:
    list: A list of disk names on the remote host.
    """
    try:
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(host, username=user, password=password)

        command = "lsblk -nd -I 8,259 -o name"
        stdin, stdout, stderr = ssh.exec_command(command)
        disk_list = stdout.read().decode().split()
        ssh.close()

        return disk_list
    except Exception as e:
        print(f"Error connecting to host '{host}': {str(e)}")
        return []

def wipe_disks_on_remote_hosts(host, user, password):
    """
    Wipes disks on a remote host using SSH and the sgdisk command.

    Parameters:
    host (str): The hostname or IP address of the host.
    user (str): The username to use for SSH authentication.
    password (str): The password to use for SSH authentication.

    Returns:
    None
    """
    try:
        disks = get_disk_list(host, user, password)

        if not disks:
            print(f"No disks found on host '{host}'.")
            return

        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(host, username=user, password=password)

        for disk in disks:
            command = f'sgdisk -Z /dev/{disk}'
            stdin, stdout, stderr = ssh.exec_command(command)
            exit_status = stdout.channel.recv_exit_status()
            if exit_status == 0:
                print(f"Successfully wiped disk '{disk}' on host '{host}'")
            else:
                print(f"Error wiping disk '{disk}' on host '{host}': {stderr.read().decode()}")

        ssh.close()
    except Exception as e:
        print(f"Error connecting to host '{host}': {str(e)}")

def get_lvm_names(host, user, password):
    """
    Retrieves the list of LVM names on a remote host using SSH and the vgdisplay command with awk.

    Parameters:
    host (str): The hostname or IP address of the remote host.
    user (str): The username to use for SSH authentication.
    password (str): The password to use for SSH authentication.

    Returns:
    list: A list of LVM names on the remote host.
    """
    try:
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(host, username=user, password=password)

        command = "vgdisplay -s | awk -F'\"' '/ceph/ { print $2 }'"
        stdin, stdout, stderr = ssh.exec_command(command)
        lvm_names = stdout.read().decode().split()
        ssh.close()

        return lvm_names
    except Exception as e:
        print(f"Error connecting to host '{host}': {str(e)}")
        return []

def remove_lvm_on_remote_hosts(host, user, password):
    """
    Removes LVMs on a remote host using SSH and the lvremove command.

    Parameters:
    host (str): The hostname or IP address of the host.
    user (str): The username to use for SSH authentication.
    password (str): The password to use for SSH authentication.

    Returns:
    None
    """
    try:
        lvm_names = get_lvm_names(host, user, password)

        if not lvm_names:
            print(f"No LVMs found on host '{host}'.")
            return

        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(host, username=user, password=password)

        for lvm_name in lvm_names:
            command = f'lvremove {lvm_name} -y'
            stdin, stdout, stderr = ssh.exec_command(command)
            exit_status = stdout.channel.recv_exit_status()
            if exit_status == 0:
                print(f"Successfully removed LVM '{lvm_name}' on host '{host}'")
            else:
                print(f"Error removing LVM '{lvm_name}' on host '{host}': {stderr.read().decode()}")

        ssh.close()
    except Exception as e:
        print(f"Error connecting to host '{host}': {str(e)}")

def get_pv_names(host, user, password):
    """
    Retrieves the list of PV names on a remote host using SSH and the pvdisplay command with awk.

    Parameters:
    host (str): The hostname or IP address of the remote host.
    user (str): The username to use for SSH authentication.
    password (str): The password to use for SSH authentication.

    Returns:
    list: A list of PV names on the remote host.
    """
    try:
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(host, username=user, password=password)

        command = "pvdisplay|grep -B1 ceph|grep PV|awk '{print $3}'"
        stdin, stdout, stderr = ssh.exec_command(command)
        pv_names = stdout.read().decode().split()
        ssh.close()

        return pv_names
    except Exception as e:
        print(f"Error connecting to host '{host}': {str(e)}")
        return []


def remove_pv_on_remote_hosts(host, user, password):
    """
    Removes PVs on a remote host using SSH and the pvremove command.

    Parameters:
    host (str): The hostname or IP address of the host.
    user (str): The username to use for SSH authentication.
    password (str): The password to use for SSH authentication.

    Returns:
    None
    """
    try:
        pv_names = get_pv_names(host, user, password)

        if not pv_names:
            print(f"No PVs found on host '{host}'.")
            return

        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(host, username=user, password=password)

        for pv_name in pv_names:
            command = f'pvremove {pv_name} --force --force -y'
            stdin, stdout, stderr = ssh.exec_command(command)
            exit_status = stdout.channel.recv_exit_status()
            if exit_status == 0:
                print(f"Successfully removed PV '{pv_name}' on host '{host}'")
            else:
                print(f"Error removing PV '{pv_name}' on host '{host}': {stderr.read().decode()}")

        ssh.close()
    except Exception as e:
        print(f"Error connecting to host '{host}': {str(e)}")




if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Wipe disks on a set of hosts')
    parser.add_argument('-hf', '--hosts_file', required=True, help='The file containing the hosts to wipe disks')
    parser.add_argument('-u', '--user', required=True, help='The SSH username to use for connecting to the hosts')
    parser.add_argument('-p', '--password', required=True, help='The SSH password to use for connecting to the hosts')
    args = parser.parse_args()

    with open(args.hosts_file, 'r') as file:
        hosts = file.read().splitlines()

    # Remove LVMs on each host
    pool = multiprocessing.Pool(processes=len(hosts))
    results = [pool.apply_async(remove_lvm_on_remote_hosts, (host, args.user, args.password)) for host in hosts]
    pool.close()
    pool.join()

    # Remove PVs on each host
    pool = multiprocessing.Pool(processes=len(hosts))
    results = [pool.apply_async(remove_pv_on_remote_hosts, (host, args.user, args.password)) for host in hosts]
    pool.close()
    pool.join()

    # wipe disks on each host
    pool = multiprocessing.Pool(processes=len(hosts))
    results = [pool.apply_async(wipe_disks_on_remote_hosts, (host, args.user, args.password)) for host in hosts]
    pool.close()
    pool.join()
