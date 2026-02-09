from typing import List

from dotenv import load_dotenv
load_dotenv()

import questionary
import requests
from scc_firewall_manager_sdk import MspManagedTenantDto, \
    MSPTenantManagementApi, ApiClient, InventoryApi, ZtpOnboardingInput

from factories import api_client_factory
from services import msp_managed_tenant_token_service, transaction_service


def _get_cdfmc_domain_uid(api_client: ApiClient):
    inventory_api = InventoryApi(api_client)
    managers_page = inventory_api.get_device_managers()

    if managers_page.items:
        return managers_page.items[0].fmc_domain_uid
    else:
        return None


def _get_cdfmc_access_policies_in_managed_tenant(tenant: MspManagedTenantDto) -> \
    List[tuple[str, str]]:
    api_token = msp_managed_tenant_token_service.get_token_for_managed_tenant(
        tenant)
    with api_client_factory.build_api_client_for_managed_tenant(tenant,
                                                                api_token) as managed_tenant_api_client:
        domain_uid = _get_cdfmc_domain_uid(managed_tenant_api_client)
        url = (
            f"{managed_tenant_api_client.configuration.host}/v1/cdfmc/api/fmc_config/v1/domain/"
            f"{domain_uid}/policy/accesspolicies"
        )
        headers = {
            "Authorization": f"Bearer {managed_tenant_api_client.configuration.access_token}",
            "Content-Type": "application/json",
        }
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        access_policies = response.json()["items"]

        return [(access_policy['id'], access_policy['name']) for access_policy
                in access_policies]


def _select_access_policy(tenant: MspManagedTenantDto) -> str:
    access_policies = _get_cdfmc_access_policies_in_managed_tenant(tenant)
    policy_choices = [f"{name} ({uid})" for uid, name in access_policies]
    selected = questionary.select(
        "Select an access policy:",
        choices=policy_choices,
        use_search_filter=True,
        use_jk_keys=False
    ).ask()

    if not selected:
        raise ValueError("No access policy selected")

    selected_uid = [uid for uid, name in access_policies
                    if f"{name} ({uid})" == selected][0]
    return selected_uid


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


def _select_tenant(tenants: List[MspManagedTenantDto]) -> MspManagedTenantDto:
    tenant_choices = [
        f"{t.display_name} ({t.name}) - Region: {t.region}"
        for t in tenants
    ]
    selected = questionary.select(
        "Select exactly one tenant:",
        choices=tenant_choices,
        use_search_filter=True,
        use_jk_keys=False
    ).ask()

    if not selected:
        raise ValueError("At least one tenant must be selected")

    return [t for t in tenants if
            f"{t.display_name} ({t.name}) - Region: {t.region}" == selected][0]


def onboard_ftd_using_ztp():
    tenants: List[MspManagedTenantDto] = _get_managed_tenants()
    selected_tenant: MspManagedTenantDto = _select_tenant(tenants)
    device_name = questionary.text("Enter device name:").ask()
    device_serial_number = questionary.text("Enter device serial number:").ask()
    access_policy_uid = _select_access_policy(selected_tenant)
    licenses = questionary.checkbox(
        "Select license types:",
        choices=["BASE", "CARRIER", "THREAT", "MALWARE", "URLFilter"]
    ).ask()
    if not licenses:
        raise ValueError("At least one license must be selected")

    api_token = msp_managed_tenant_token_service.get_token_for_managed_tenant(
        selected_tenant)
    password = 'supersecurepassword!'
    with api_client_factory.build_api_client_for_managed_tenant(selected_tenant,
                                                                api_token) as managed_tenant_api_client:
        inventory_api = InventoryApi(managed_tenant_api_client)
        transaction = inventory_api.onboard_ftd_device_using_ztp(
            ztp_onboarding_input=ZtpOnboardingInput(
                adminPassword=password,
                name=device_name,
                serialNumber=device_serial_number,
                fmcAccessPolicyUid=access_policy_uid,
                licenses=licenses
            ))
        transaction_service.wait_for_transaction_to_finish_with_api_client(
            transaction, managed_tenant_api_client
        )


if __name__ == "__main__":
    onboard_ftd_using_ztp()
