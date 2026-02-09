from scc_firewall_manager_sdk import MSPUserManagementApi, \
    MspAddUsersToTenantInput, UserInput, UserRole, CdoTransaction, User, \
    MSPTenantManagementApi, MspManagedTenantDto

from factories import api_client_factory
from services import transaction_service

username = 'msp-automation-test-user'


def _get_user(msp_managed_tenant: MspManagedTenantDto) -> User | None:
    with api_client_factory.build_api_client() as api_client:
        msp_user_mgmt_api = MSPUserManagementApi(api_client=api_client)
        user_page = msp_user_mgmt_api.get_api_only_users_in_msp_managed_tenant(
            tenant_uid=msp_managed_tenant.uid, limit='1', offset='0',
            q=f"name:{username}@{msp_managed_tenant.name}")
        if user_page.count == 1:
            return user_page.items[0]
        return None


def _does_user_exist(managed_tenant_uid: str) -> bool:
    return _get_user(managed_tenant_uid) is not None


def _create_user_in_tenant(
    msp_managed_tenant: MspManagedTenantDto
) -> User:
    with api_client_factory.build_api_client() as api_client:
        if not _does_user_exist(msp_managed_tenant):
            msp_user_mgmt_api = MSPUserManagementApi(api_client=api_client)
            transaction = msp_user_mgmt_api.add_users_to_tenant_in_msp_portal(
                tenant_uid=msp_managed_tenant.uid,
                msp_add_users_to_tenant_input=MspAddUsersToTenantInput(
                    users=[
                        UserInput(
                            apiOnlyUser=True,
                            role=UserRole.ROLE_ADMIN,
                            username=username,
                        )
                    ]
                ))
            print(f"Creating user {username}...")
            updated_transaction: CdoTransaction = transaction_service.wait_for_transaction_to_finish(
                transaction)
            if updated_transaction.cdo_transaction_status != "DONE":
                raise Exception(
                    f"Transaction failed with status {updated_transaction.cdo_transaction_status}")
        return _get_user(msp_managed_tenant)


def get_token_for_managed_tenant(
    msp_managed_tenant: MspManagedTenantDto) -> str:
    user = _create_user_in_tenant(msp_managed_tenant)
    with api_client_factory.build_api_client() as api_client:
        tenant_mgmt_api = MSPTenantManagementApi(api_client=api_client)
        api_token_info = tenant_mgmt_api.generate_api_token_for_user_in_tenant(
            tenant_uid=msp_managed_tenant.uid, api_user_uid=user.uid)

    return api_token_info.api_token
