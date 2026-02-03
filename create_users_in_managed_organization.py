from argparse import ArgumentParser

from scc_firewall_manager_sdk import MSPUserManagementApi, \
    MspAddUsersToTenantInput, UserInput

import api_client_factory
import transaction_service

if __name__ == "__main__":
    parser = ArgumentParser()
    parser.add_argument("--tenant-uid", required=True, help="Tenant UID")
    parser.add_argument("--user-first-names", required=True,
                        help="User First Names, comma separated")
    parser.add_argument("--user-last-names", required=True,
                        help="User Last Names, comma separated")
    parser.add_argument("--user-roles", required=True,
                        help="User Roles, comma separated")
    parser.add_argument("--user-emails", required=True,
                        help="User email addresses, comma separated")
    args = parser.parse_args()

    user_emails = [e.strip() for e in args.user_emails.split(",") if e.strip()]
    user_first_names = [f.strip() for f in args.user_first_names.split(",") if
                        f.strip()]
    user_last_names = [l.strip() for l in args.user_last_names.split(",") if
                       l.strip()]
    user_roles = [r.strip() for r in args.user_roles.split(",") if r.strip()]
    if len(user_emails) != len(user_first_names) or len(user_emails) != len(
        user_last_names) or len(user_emails) != len(user_roles):
        raise ValueError(
            "User emails, roles, first names, and last names must have the same number of elements")
    user_inputs = []
    for i in range(0, len(user_emails)):
        user_inputs.append(UserInput(firstName=user_first_names[i],
                                     lastName=user_last_names[i],
                                     username=user_emails[i],
                                     role=user_roles[i]))

    with api_client_factory.build_api_client() as api_client:
        msp_user_mgmt_api = MSPUserManagementApi(api_client)
        print("Adding users to tenant...")
        transaction = msp_user_mgmt_api.add_users_to_tenant_in_msp_portal(
            args.tenant_uid,
            MspAddUsersToTenantInput(
                users=user_inputs
            )
        )
        transaction = transaction_service.wait_for_transaction_to_finish(transaction)
        print(
            f"{len(user_emails)} users created in managed organization {args.tenant_uid}. "
            f"Transaction status: {transaction.cdo_transaction_status}")
