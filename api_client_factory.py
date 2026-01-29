import os

from scc_firewall_manager_sdk import ApiClient, Configuration

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
