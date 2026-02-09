import json
from typing import List

import questionary
import requests
from dotenv import load_dotenv

load_dotenv()

from datetime import date

from models.fmc import DeviceBackupRequest

from scc_firewall_manager_sdk import MSPTenantManagementApi, \
    MspManagedTenantDto, InventoryApi, ApiClient, Configuration

from factories import api_client_factory
from services import msp_managed_tenant_token_service, fmc_task_service


def _get_cdfmc_domain_uid(tenant_api_token: str, host: str):
    inventory_api = InventoryApi(
        ApiClient(Configuration(host=host, access_token=tenant_api_token)))
    managers_page = inventory_api.get_device_managers()

    if managers_page.items:
        return managers_page.items[0].fmc_domain_uid
    else:
        return None


def _get_online_cdfmc_managed_ftds(tenant_api_token: str, host: str) -> List:
    inventory_api = InventoryApi(
        ApiClient(Configuration(host=host, access_token=tenant_api_token)))
    limit = 200
    offset = 0
    count = None
    all_devices = []

    while count is None or len(all_devices) < count:
        device_page = inventory_api.get_devices(
            limit=str(limit), offset=str(offset),
            q="deviceType:CDFMC_MANAGED_FTD AND connectivityState:ONLINE AND redundancyMode:STANDALONE")
        all_devices.extend(device_page.items)
        offset += limit
        count = device_page.count

    return all_devices


def _create_device_backup(tenant_api_token: str, host: str,
    cdfmc_domain_uid: str, fmc_device_uids: List[str]):
    current_date = date.today().isoformat()
    url = (f"{host}/v1/cdfmc/api/fmc_config/v1/domain/{cdfmc_domain_uid}/backup/"
           f"operational/devicebackup")
    headers = {
        "Authorization": f"Bearer {tenant_api_token}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    payload = json.dumps(DeviceBackupRequest(
        name=f"backup-{current_date}",
        description=f"Backup on {current_date}",
        device_ids=fmc_device_uids,
    ).to_dict())

    response = requests.post(url, headers=headers, data=payload)
    response.raise_for_status()
    return response.json()


def _create_device_backup_for_all_online_cdfmc_managed_ftds(
    managed_tenant: MspManagedTenantDto, tenant_api_token: str, host: str):
    cdfmc_domain_uid = _get_cdfmc_domain_uid(tenant_api_token, host)
    if not cdfmc_domain_uid:
        print(f"  No cdFMC found for tenant {managed_tenant.display_name}")
        return

    online_ftds = _get_online_cdfmc_managed_ftds(tenant_api_token, host)
    if not online_ftds:
        print(
            f"  No online cdFMC-managed FTDs found for tenant {managed_tenant.display_name}")
        return

    print(f"  Found {len(online_ftds)} online cdFMC-managed FTD(s)")
    fmc_device_uids = [device.device_record_on_fmc.uid for device in
                       online_ftds]
    backup_response = _create_device_backup(tenant_api_token, host,
                                            cdfmc_domain_uid,
                                            fmc_device_uids)
    task_id = backup_response.get("metadata", {}).get("task", {}).get("id")
    if task_id:
        print(f"    Waiting for backup task {task_id} to complete...")
        task = fmc_task_service.wait_for_task_completion(
            host, cdfmc_domain_uid, task_id, tenant_api_token)
        if task.status == "FAILED":
            print(f"    Backup failed: {task.message}")
        else:
            print(f"    Backup completed: {task.status}")


def _get_managed_tenants() -> List[MspManagedTenantDto]:
    limit = 200
    offset = 0
    count = None
    all_tenants: List[MspManagedTenantDto] = []

    with api_client_factory.build_api_client() as api_client:
        msp_tenant_api = MSPTenantManagementApi(api_client)
        while count is None or len(all_tenants) < count:
            tenant_page = msp_tenant_api.get_msp_managed_tenants(
                limit=str(limit), offset=str(offset))
            all_tenants.extend(tenant_page.items)
            offset += limit
            count = tenant_page.count

    return [tenant for tenant in all_tenants if
            tenant.cd_fmc_type != 'UNPROVISIONED']


def _select_tenants(tenants: List[MspManagedTenantDto]) -> List[
    MspManagedTenantDto]:
    tenant_choices = [
        f"{t.display_name} ({t.name}) - Region: {t.region}"
        for t in tenants
    ]
    selected = questionary.checkbox(
        "Select one or more tenants:",
        choices=tenant_choices,
        use_search_filter=True,
        use_jk_keys=False
    ).ask()

    if not selected:
        return []

    return [t for t in tenants if
            f"{t.display_name} ({t.name}) - Region: {t.region}" in selected]


if __name__ == "__main__":
    all_tenants = _get_managed_tenants()
    print(f"Found {len(all_tenants)} managed tenants")

    selected_tenants = _select_tenants(all_tenants)
    if selected_tenants:
        print(f"\nSelected {len(selected_tenants)} tenant(s):")
        for tenant in selected_tenants:
            print(f"  - {tenant.display_name} (UID: {tenant.uid})")

        print("\nBacking up FTDs for selected tenants...")
        for tenant in selected_tenants:
            print(f"\nProcessing tenant: {tenant.display_name}")
            token = msp_managed_tenant_token_service.get_token_for_managed_tenant(
                tenant)
            host = api_client_factory.build_api_client_for_managed_tenant(
                tenant, token).configuration.host
            _create_device_backup_for_all_online_cdfmc_managed_ftds(tenant,
                                                                    token, host)
    else:
        print("No tenants selected.")
