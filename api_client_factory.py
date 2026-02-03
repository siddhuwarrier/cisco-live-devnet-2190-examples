import os

from scc_firewall_manager_sdk import ApiClient, Configuration, \
    MspManagedTenantDto

# Change this to the region your tenant/MSSP portal is deployed in
region = "int"
base_url = f"https://api.{region}.security.cisco.com/firewall"
# Set the environment variable SCCFM_API_TOKEN to the API token for your tenant/MSSP portal
api_token = os.getenv("SCCFM_API_TOKEN")

def build_api_client():
    return ApiClient(
        Configuration(
            host=base_url,
            access_token=api_token
        )
    )

def build_api_client_for_managed_tenant(msp_managed_tenant: MspManagedTenantDto, api_token: str) -> ApiClient:
    if msp_managed_tenant.region == 'SCALE':
        tenant_base_url = "https://scale.manage.security.cisco.com"
    elif msp_managed_tenant.region == 'STAGING':
        api_region = 'int'
        tenant_base_url = f"https://api.{api_region}.security.cisco.com/firewall"
    else:
        api_region = msp_managed_tenant.region.lower()
        tenant_base_url = f"https://api.{api_region}.security.cisco.com/firewall"
    
    return ApiClient(
        Configuration(
            host=tenant_base_url,
            access_token=api_token
        )
    )
