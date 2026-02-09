import sys
from datetime import datetime
from time import sleep
from typing import List

from dotenv import load_dotenv

load_dotenv()

import questionary
from rich.console import Console
from rich.live import Live
from rich.table import Table
from scc_firewall_manager_sdk import MSPDeviceUpgradesApi, \
    MspCalculateCompatibleUpgradeVersionsInput, CdoTransaction, \
    CompatibleVersionInfoDto, MSPInventoryApi, MspManagedDevice, \
    MspUpgradeFtdDevicesInput

from factories import api_client_factory
from services import transaction_service


def _build_upgrade_status_table(upgrade_run) -> Table:
    status_colors = {
        'PENDING': 'yellow',
        'IN_PROGRESS': 'blue',
        'UPGRADE_STAGED': 'cyan',
        'UPGRADE_COMPLETED': 'green',
        'UPGRADE_FAILED': 'red',
        'UPGRADE_STAGING_FAILED': 'red',
    }
    overall_color = status_colors.get(upgrade_run.upgrade_run_status, 'white')

    table = Table(
        title=f"Upgrade Status: [{overall_color}]{upgrade_run.upgrade_run_status}[/{overall_color}]")
    table.add_column("Device", style="cyan")
    table.add_column("Tenant", style="magenta")
    table.add_column("Status", style="bold")
    table.add_column("Message")

    for device in upgrade_run.metadata.devices:
        device_color = status_colors.get(device.upgrade_run_status, 'white')
        message = "-"
        if device.completion_statuses:
            latest = device.completion_statuses[-1]
            message = latest.message or "-"
        table.add_row(
            device.name or "-",
            device.managed_tenant_display_name or "-",
            f"[{device_color}]{device.upgrade_run_status}[/{device_color}]",
            message
        )
    return table


def _wait_for_upgrade_to_complete(transaction: CdoTransaction) -> None:
    terminal_statuses = [
        'UPGRADE_STAGED', 'UPGRADE_STAGING_FAILED',
        'UPGRADE_COMPLETED', 'UPGRADE_FAILED'
    ]
    with api_client_factory.build_api_client() as api_client:
        msp_device_upgrades_api = MSPDeviceUpgradesApi(api_client)
        upgrade_run = msp_device_upgrades_api.get_msp_device_upgrade_run(
            transaction.entity_uid)

        with Live(_build_upgrade_status_table(upgrade_run),
                  refresh_per_second=1) as live:
            while upgrade_run.upgrade_run_status not in terminal_statuses:
                sleep(5)
                upgrade_run = msp_device_upgrades_api.get_msp_device_upgrade_run(
                    transaction.entity_uid)
                live.update(_build_upgrade_status_table(upgrade_run))

        console = Console()
        if upgrade_run.upgrade_run_status in ['UPGRADE_COMPLETED',
                                              'UPGRADE_STAGED']:
            console.print("[bold green]Upgrade completed successfully!")
        else:
            console.print(
                f"[bold red]Upgrade failed: {upgrade_run.upgrade_run_status}")


def _select_ftds(ftd_devices: List[MspManagedDevice]) -> List[str]:
    device_choices = [
        f"{d.name} (version: {d.software_version}, UID: {d.uid}) - Tenant: {d.managed_tenant_display_name}"
        for d in ftd_devices]
    selected_ftd_devices = questionary.checkbox(
        "Select FTDs to upgrade:", choices=device_choices).ask()
    return [d.uid for d in ftd_devices if
            any(d.uid in choice for choice in selected_ftd_devices)]


def _get_online_cdfmc_managed_ftd_devices() -> List[MspManagedDevice]:
    limit = 200
    offset = 0
    count = None
    online_cdfmc_managed_ftd_devices = []

    with api_client_factory.build_api_client() as api_client:
        msp_inventory_api = MSPInventoryApi(api_client)
        while count is None or len(online_cdfmc_managed_ftd_devices) < count:
            device_page = msp_inventory_api.get_msp_managed_devices(
                q="deviceType:CDFMC_MANAGED_FTD AND connectivityState:ONLINE")
            online_cdfmc_managed_ftd_devices.extend(device_page.items)
            offset += limit
            count = device_page.count

    if not online_cdfmc_managed_ftd_devices:
        print("No online cdFMC-managed FTD devices found.")
        sys.exit(1)
    return online_cdfmc_managed_ftd_devices


def _perform_upgrade(ftd_device_uids: List[str], software_version: str) -> None:
    with api_client_factory.build_api_client() as api_client:
        device_upgrade_api = MSPDeviceUpgradesApi(api_client)
        transaction = device_upgrade_api.upgrade_msp_managed_ftd_devices(
            MspUpgradeFtdDevicesInput(
                name=f"Upgrade FTDs on {datetime.now().isoformat()}",
                deviceUids=ftd_device_uids, softwareVersion=software_version))
        _wait_for_upgrade_to_complete(transaction)


def upgrade_ftds() -> None:
    online_cdfmc_managed_ftd_devices = _get_online_cdfmc_managed_ftd_devices()
    ftd_uids = _select_ftds(online_cdfmc_managed_ftd_devices)

    with api_client_factory.build_api_client() as api_client:
        device_upgrades_api = MSPDeviceUpgradesApi(api_client)
        transaction = device_upgrades_api.calculate_msp_ftd_compatible_upgrade_versions(
            MspCalculateCompatibleUpgradeVersionsInput(
                deviceUids=ftd_uids
            ))
        transaction = transaction_service.wait_for_transaction_to_finish(transaction)

        compatible_versions: List[
            CompatibleVersionInfoDto] = device_upgrades_api.get_msp_ftd_compatible_upgrade_versions(
            transaction.entity_uid).compatible_versions

        version_choices = [
            f"{v.software_version} *" if v.is_suggested_version else v.software_version
            for v in compatible_versions
        ]
        selected_version = questionary.select(
            "Select a version to upgrade to:",
            choices=version_choices
        ).ask()

        selected_version = selected_version.rstrip(" *")
        print(f"Upgrading to version {selected_version}")
        _perform_upgrade(ftd_uids, selected_version)


if __name__ == "__main__":
    upgrade_ftds()
