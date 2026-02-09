from scc_firewall_manager_sdk import MSPTenantManagementApi, \
    MspCreateTenantInput

from factories import api_client_factory
from services import transaction_service

if __name__ == "__main__":
    with api_client_factory.build_api_client() as api_client:
        msp_api = MSPTenantManagementApi(api_client)
        print("Creating tenant...")
        transaction = msp_api.create_tenant(
            MspCreateTenantInput(displayName="Cisco Live EMEA 2026 Example Tenant",
                                 tenantName="cisco-live-emea-2026-example-tenant-2"))
        transaction = transaction_service.wait_for_transaction_to_finish(transaction)
        print(
            f"Managed organization created successfully. Transaction status: {transaction.cdo_transaction_status}")
