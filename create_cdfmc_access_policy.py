import argparse
import sys
import uuid

import requests
from dotenv import load_dotenv

load_dotenv()
from scc_firewall_manager_sdk import InventoryApi, MSPUserManagementApi, \
    MspAddUsersToTenantInput, MSPTenantManagementApi, ApiClient

from factories import api_client_factory
from services import msp_managed_tenant_token_service
from models.fmc import CdFmcAccessPolicy, CdFmcAccessRule, \
    UrlCategoryWithReputation, UrlCategory, SourceNetworks, NetworkObject, Urls


def get_cdfmc_domain_uid(api_client: ApiClient):
    inventory_api = InventoryApi(api_client)
    managers_page = inventory_api.get_device_managers(q='deviceType:CDFMC')

    if managers_page.items:
        return managers_page.items[0].fmc_domain_uid
    else:
        return None


def _get_gambling_category_id(api_client: ApiClient,
    cdfmc_domain_uid: str) -> str:
    url = f"{api_client.configuration.host}/v1/cdfmc/api/fmc_config/v1/domain/{cdfmc_domain_uid}/object/urlcategories?limit=200"
    headers = {
        "Authorization": f"Bearer {api_client.configuration.access_token}",
        "Content-Type": "application/json",
    }
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    url_categories = response.json()["items"]

    gambling_categories = [
        category for category in url_categories if
        category["name"] == "Gambling"
    ]
    return gambling_categories[0]["id"]


def _get_any_ipv4_network_object(api_client, cdfmc_domain_uid: str) -> str:
    url = f"{api_client.configuration.host}/v1/cdfmc/api/fmc_config/v1/domain/{cdfmc_domain_uid}/object/networks?filter=nameOrValue%3Aany-ipv4"
    headers = {
        "Authorization": f"Bearer {api_client.configuration.access_token}",
        "Content-Type": "application/json",
    }
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    data = response.json()

    if data["paging"]["count"] != 1:
        raise RuntimeError(
            "Expected exactly one network object with name 'any-ipv4'"
        )

    return data["items"][0]["id"]


def block_gambling(access_policy_uid: str, cdfmc_domain_uid: str,
    api_client: ApiClient):
    gambling_category_id: str = _get_gambling_category_id(api_client,
                                                          cdfmc_domain_uid)
    any_ipv4_obj_id: str = _get_any_ipv4_network_object(api_client,
                                                        cdfmc_domain_uid)

    url = (
        f"{api_client.configuration.host}/v1/cdfmc/api/fmc_config/v1/domain/"
        f"{cdfmc_domain_uid}/policy/accesspolicies/{access_policy_uid}/accessrules"
    )
    headers = {
        "Authorization": f"Bearer {api_client.configuration.access_token}",
        "Content-Type": "application/json",
    }
    access_rule = CdFmcAccessRule(
        name="Block Gambling",
        action="BLOCK",
        enabled=True,
        urls=Urls(
            url_categories_with_reputation=[
                UrlCategoryWithReputation(
                    reputation="TRUSTED_AND_UNKNOWN",
                    category=UrlCategory(
                        name="Gambling",
                        id=gambling_category_id,
                    ),
                )
            ]
        ),
        source_networks=SourceNetworks(
            objects=[
                NetworkObject(
                    type="NetworkGroup",
                    overridable=False,
                    id=any_ipv4_obj_id,
                    name="any-ipv4",
                )
            ]
        ),
    )

    response = requests.post(url, headers=headers, json=access_rule.to_dict())
    response.raise_for_status()

    return response.json()


def _create_cdfmc_access_policy(api_client: ApiClient) -> tuple[str, str]:
    domain_uid = get_cdfmc_domain_uid(api_client)
    if domain_uid is None:
        print("Tenant does not have a cdFMC")
        sys.exit(1)

    policy = CdFmcAccessPolicy(name="MSP Access Policy " + str(uuid.uuid1()),
                               default_action="BLOCK")
    url = (
        f"{api_client.configuration.host}/v1/cdfmc/api/fmc_config/v1/domain/"
        f"{domain_uid}/policy/accesspolicies"
    )
    headers = {
        "Authorization": f"Bearer {api_client.configuration.access_token}",
        "Content-Type": "application/json",
    }
    response = requests.post(url, headers=headers, json=policy.__dict__)
    response.raise_for_status()
    return response.json()["id"], domain_uid


def _create_api_only_user_in_managed_tenant(tenant_uid: str) -> None:
    with api_client_factory.build_api_client() as api_client:
        msp_user_api = MSPUserManagementApi(api_client=api_client)
        msp_user_api.add_users_to_tenant_in_msp_portal(tenant_uid=tenant_uid,
                                                       msp_add_users_to_tenant_input=MspAddUsersToTenantInput())


def create_cdfmc_access_policy_in_managed_tenant(tenant_name: str):
    with api_client_factory.build_api_client() as api_client:
        msp_tenant_mgmt_api = MSPTenantManagementApi(api_client=api_client)
        page = msp_tenant_mgmt_api.get_msp_managed_tenants(
            q=f"name:{tenant_name} OR displayName:{tenant_name}")
        tenants_with_cdfmc = [tenant for tenant in page.items if
                              tenant.cd_fmc_type != 'UNPROVISIONED']
        if len(tenants_with_cdfmc) == 0:
            print("No tenant found by name with cdFMC. Failing...")
        for tenant in tenants_with_cdfmc:
            print("******")
            print(
                f"Generating token for {tenant.display_name} with cdFMC type {tenant.cd_fmc_type}...")
            api_token = msp_managed_tenant_token_service.get_token_for_managed_tenant(
                tenant)
            print(f"Generated token")
            print(f"Creating access policy for {tenant.display_name}...")
            access_policy_uid, domain_uid = _create_cdfmc_access_policy(
                api_client_factory.build_api_client_for_managed_tenant(tenant,
                                                                       api_token))
            print("Created access policy")
            print("Creating access rule to block Gambling...")
            block_gambling(access_policy_uid, domain_uid,
                           api_client_factory.build_api_client_for_managed_tenant(
                               tenant, api_token))
            print("Created access rule to block Gambling")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("-t", "--tenant-name", type=str)
    args = parser.parse_args()
    create_cdfmc_access_policy_in_managed_tenant(args.tenant_name)
