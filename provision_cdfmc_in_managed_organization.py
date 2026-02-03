from argparse import ArgumentParser
from time import sleep

from scc_firewall_manager_sdk import MSPTenantManagementApi, TransactionsApi, \
    EnableCdFmcForTenantRequest

import api_client_factory
import transaction_service

if __name__ == "__main__":
    parser = ArgumentParser()
    parser.add_argument("--tenant-uid", required=True, help="Tenant UID")
    args = parser.parse_args()

    with api_client_factory.build_api_client() as api_client:
        msp_tenant_mgmt_api = MSPTenantManagementApi(api_client)
        transactions_api = TransactionsApi(api_client)
        transaction = msp_tenant_mgmt_api.provision_cd_fmc_for_tenant_in_msp_portal(
            tenant_uid=args.tenant_uid,
            enable_cd_fmc_for_tenant_request=EnableCdFmcForTenantRequest(
                dedicatedCdFmcInstance=True))
        print(
            f"Created transaction with UID {transaction.transaction_uid}. Polling for transaction completion...")

        transaction_service.wait_for_transaction_to_finish(transaction)
