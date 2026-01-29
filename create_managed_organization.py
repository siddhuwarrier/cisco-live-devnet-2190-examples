from time import sleep

from scc_firewall_manager_sdk import MSPTenantManagementApi, \
    MspCreateTenantInput, TransactionsApi

import api_client_factory

if __name__ == "__main__":
    with api_client_factory.build_api_client() as api_client:
        msp_api = MSPTenantManagementApi(api_client)
        transactions_api = TransactionsApi(api_client)
        print("Creating tenant...")
        transaction = msp_api.create_tenant(
            MspCreateTenantInput(displayName="Cisco Live EMEA 2026 Example Tenant",
                                 tenantName="cisco-live-emea-2026-example-tenant-2"))
        print(
            f"Created transaction with UID {transaction.transaction_uid}. Polling for transaction completion...")

        while transaction.cdo_transaction_status not in ["DONE", "ERROR",
                                                         "CANCELLED"]:
            sleep(3)
            print(
                f"Current transaction status: {transaction.cdo_transaction_status}")
            transaction = transactions_api.get_transaction(
                transaction.transaction_uid)

        print(
            f"Managed organization created successfully. Transaction status: {transaction.cdo_transaction_status}")
