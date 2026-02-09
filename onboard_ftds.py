import argparse
import csv
from typing import List, Dict, Tuple, Optional
from dotenv import load_dotenv

load_dotenv()

import questionary
import requests
from scc_firewall_manager_sdk import InventoryApi, MspManagedTenantDto, \
    MSPTenantManagementApi, ApiClient, FtdCreateOrUpdateInput, \
    FtdRegistrationInput

from factories import api_client_factory
from services import msp_managed_tenant_token_service, transaction_service
from services.ssh_service import SshConnectionInfo, send_cli_key_via_ssh


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


def _get_ssh_info_interactive() -> Optional[SshConnectionInfo]:
    use_ssh = questionary.confirm(
        "Would you like the script to SSH into the FTD to paste the CLI key?"
    ).ask()

    if not use_ssh:
        return None

    connection_type = questionary.select(
        "How would you like to connect?",
        choices=[
            "Use SSH config name (~/.ssh/config)",
            "Provide IP address/FQDN and port"
        ],
        use_jk_keys=False
    ).ask()

    password = questionary.password(
        "Enter the SSH password (leave blank for key-based auth):"
    ).ask()
    if password == '':
        password = None

    if connection_type == "Use SSH config name (~/.ssh/config)":
        ssh_config_name = questionary.text(
            "Enter the SSH config host name:"
        ).ask()
        if not ssh_config_name:
            raise ValueError("SSH config name is required")
        return SshConnectionInfo(ssh_config_name=ssh_config_name,
                                 password=password)
    else:
        hostname = questionary.text(
            "Enter the IP address or FQDN:"
        ).ask()
        if not hostname:
            raise ValueError("Hostname is required")
        port_str = questionary.text(
            "Enter the SSH port:", default="22"
        ).ask()
        return SshConnectionInfo(hostname=hostname, port=int(port_str),
                                 password=password)


def _get_ftd_onboarding_inputs_interactive() -> List[Tuple[
    MspManagedTenantDto, FtdCreateOrUpdateInput, Optional[SshConnectionInfo]]]:
    ftd_inputs: List[Tuple[
        MspManagedTenantDto, FtdCreateOrUpdateInput, Optional[
            SshConnectionInfo]]] = []
    tenants: List[MspManagedTenantDto] = _get_managed_tenants()

    while True:
        selected_tenant: MspManagedTenantDto = _select_tenant(tenants)

        device_name = questionary.text("Enter device name:").ask()
        if not device_name:
            raise ValueError("Device name is required")

        is_virtual = questionary.confirm("Is this a virtual FTD?").ask()

        performance_tier = None
        if is_virtual:
            performance_tier = questionary.select(
                "Select performance tier:",
                choices=["FTDv5", "FTDv10", "FTDv20", "FTDv30", "FTDv50",
                         "FTDv100", "FTDv"],
                use_jk_keys=False
            ).ask()

        licenses = questionary.checkbox(
            "Select license types:",
            choices=["BASE", "CARRIER", "THREAT", "MALWARE", "URLFilter"]
        ).ask()
        if not licenses:
            raise ValueError("At least one license must be selected")

        access_policy_uid = _select_access_policy(selected_tenant)

        ssh_info = _get_ssh_info_interactive()

        ftd_inputs.append((selected_tenant, FtdCreateOrUpdateInput(
            deviceType="CDFMC_MANAGED_FTD",
            name=device_name,
            virtual=is_virtual,
            performanceTier=performance_tier,
            licenses=licenses,
            fmcAccessPolicyUid=access_policy_uid
        ), ssh_info))

        add_another = questionary.confirm(
            "Would you like to add another FTD?").ask()
        if not add_another:
            break

    return ftd_inputs


def _get_tenant_by_name(tenant_name: str) -> MspManagedTenantDto:
    tenants = _get_managed_tenants()
    matching = [t for t in tenants if t.name == tenant_name]
    if not matching:
        raise ValueError(f"Managed tenant '{tenant_name}' not found")
    return matching[0]


def _validate_access_policy_in_tenant(tenant: MspManagedTenantDto,
    access_policy_uid: str) -> None:
    access_policies = _get_cdfmc_access_policies_in_managed_tenant(tenant)
    policy_uids = [uid for uid, name in access_policies]
    if access_policy_uid not in policy_uids:
        raise ValueError(
            f"Access policy '{access_policy_uid}' not found in tenant '{tenant.name}'. "
            f"Available policies: {[f'{name} ({uid})' for uid, name in access_policies]}"
        )


def _parse_ssh_info_from_csv_row(row: Dict[str, str],
    row_num: int) -> SshConnectionInfo:
    ssh_config_name = (row.get('ssh_config_name') or '').strip()
    ssh_hostname = (row.get('ssh_hostname') or '').strip()
    ssh_port = (row.get('ssh_port') or '').strip()
    ssh_password = (row.get('ssh_password') or '').strip() or None

    if ssh_config_name and ssh_hostname:
        raise ValueError(
            f"Row {row_num}: specify either ssh_config_name or "
            f"ssh_hostname+ssh_port, not both")
    if not ssh_config_name and not ssh_hostname:
        raise ValueError(
            f"Row {row_num}: either ssh_config_name or ssh_hostname "
            f"must be provided")

    if ssh_config_name:
        return SshConnectionInfo(ssh_config_name=ssh_config_name,
                                 password=ssh_password)
    else:
        return SshConnectionInfo(
            hostname=ssh_hostname,
            port=int(ssh_port) if ssh_port else 22,
            password=ssh_password
        )


def _get_ftd_onboarding_inputs_from_csv(csv_file: str) -> List[
    Tuple[MspManagedTenantDto, FtdCreateOrUpdateInput, SshConnectionInfo]]:
    ftd_inputs: List[Tuple[
        MspManagedTenantDto, FtdCreateOrUpdateInput, SshConnectionInfo]] = []
    tenant_cache: Dict[str, MspManagedTenantDto] = {}
    validated_policies: set[tuple[str, str]] = set()

    with open(csv_file, 'r') as f:
        reader = csv.DictReader(f)
        for row_num, row in enumerate(reader, start=2):
            tenant_name = row['tenant_name']

            if tenant_name not in tenant_cache:
                print(f"Validating tenant '{tenant_name}'...")
                tenant_cache[tenant_name] = _get_tenant_by_name(tenant_name)

            tenant = tenant_cache[tenant_name]
            access_policy_uid = row['access_policy_uid']

            if (tenant_name, access_policy_uid) not in validated_policies:
                print(
                    f"Validating access policy '{access_policy_uid}' in tenant '{tenant_name}' (row {row_num})...")
                _validate_access_policy_in_tenant(tenant, access_policy_uid)
                validated_policies.add((tenant_name, access_policy_uid))

            ssh_info = _parse_ssh_info_from_csv_row(row, row_num)

            is_virtual = row['virtual'].lower() == 'true'
            performance_tier = row.get('performance_tier') or None
            if performance_tier == '':
                performance_tier = None
            licenses = [l.strip() for l in row['licenses'].split(';') if
                        l.strip()]

            ftd_inputs.append((tenant, FtdCreateOrUpdateInput(
                deviceType="CDFMC_MANAGED_FTD",
                name=row['name'],
                virtual=is_virtual,
                performanceTier=performance_tier,
                licenses=licenses,
                fmcAccessPolicyUid=access_policy_uid
            ), ssh_info))

    return ftd_inputs


def onboard_ftds(ftd_inputs: List[Tuple[
    MspManagedTenantDto, FtdCreateOrUpdateInput, Optional[SshConnectionInfo]]]):
    for tenant, ftd_input, ssh_info in ftd_inputs:
        print(f"Onboarding FTD '{ftd_input.name}' to tenant '{tenant.name}'...")
        api_token = msp_managed_tenant_token_service.get_token_for_managed_tenant(
            tenant)
        with api_client_factory.build_api_client_for_managed_tenant(tenant,
                                                                    api_token) as managed_tenant_api_client:
            inventory_api = InventoryApi(api_client=managed_tenant_api_client)
            creation_transaction = inventory_api.create_ftd_device(ftd_input)
            transaction_service.wait_for_transaction_to_finish_with_api_client(
                creation_transaction, managed_tenant_api_client)
            created_device = inventory_api.get_device(
                creation_transaction.entity_uid)
            cli_key = created_device.cd_fmc_info.cli_key

            if ssh_info:
                print(f"Sending CLI key to FTD '{ftd_input.name}' via SSH...")
                send_cli_key_via_ssh(ssh_info, cli_key)
                print(f"CLI key sent successfully to '{ftd_input.name}'.")
            else:
                questionary.press_any_key_to_continue(
                    f"Please paste the CLI key: {cli_key} into your device, "
                    f"and then press any key to continue..."
                ).ask()

            registration_transaction = inventory_api.finish_onboarding_ftd_device(
                ftd_registration_input=FtdRegistrationInput(
                    ftdUid=created_device.uid))
            transaction_service.wait_for_transaction_to_finish_with_api_client(
                registration_transaction, managed_tenant_api_client)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Onboard FTD devices")
    parser.add_argument("--non-interactive", action="store_true",
                        help="Run in non-interactive mode using a CSV file")
    parser.add_argument("--csv-file", type=str,
                        help="Path to CSV file (required for non-interactive mode)")
    args = parser.parse_args()

    if args.non_interactive:
        if not args.csv_file:
            parser.error("--csv-file is required when using --non-interactive")
        ftd_inputs = _get_ftd_onboarding_inputs_from_csv(args.csv_file)
    else:
        if args.csv_file:
            parser.error(
                '--csv-file should not be specified in interactive mode')
        ftd_inputs = _get_ftd_onboarding_inputs_interactive()

    onboard_ftds(ftd_inputs)
