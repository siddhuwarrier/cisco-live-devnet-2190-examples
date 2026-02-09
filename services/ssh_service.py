from dataclasses import dataclass
from typing import Optional

import pexpect


@dataclass
class SshConnectionInfo:
    ssh_config_name: Optional[str] = None
    hostname: Optional[str] = None
    port: Optional[int] = None
    password: Optional[str] = None

    def __post_init__(self):
        if self.ssh_config_name and (self.hostname or self.port):
            raise ValueError(
                "Specify either ssh_config_name or hostname+port, not both")
        if not self.ssh_config_name and not self.hostname:
            raise ValueError(
                "Either ssh_config_name or hostname must be provided")


def send_cli_key_via_ssh(ssh_info: SshConnectionInfo, cli_key: str) -> None:
    if ssh_info.ssh_config_name:
        ssh_cmd = f"ssh {ssh_info.ssh_config_name}"
    else:
        port = ssh_info.port or 22
        ssh_cmd = f"ssh -p {port} admin@{ssh_info.hostname}"

    child = pexpect.spawn(ssh_cmd, timeout=30, encoding='utf-8')

    try:
        index = child.expect(
            ['[Pp]assword:', '>', '#', pexpect.TIMEOUT], timeout=30)
        if index == 0:
            if not ssh_info.password:
                raise ValueError(
                    "SSH password required but not provided")
            child.sendline(ssh_info.password)
            child.expect(['>', '#'], timeout=15)

        child.sendline(cli_key)
        child.expect(['Manager', '>', '#', pexpect.TIMEOUT], timeout=15)
        print(f"FTD response: {child.before}{child.after}")

        child.sendline("exit")
        child.expect(pexpect.EOF, timeout=10)
    finally:
        child.close()
