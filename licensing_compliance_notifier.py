import os
from typing import List

from dotenv import load_dotenv
from webexpythonsdk.models.cards import Container, TextBlock, ColumnSet, Column, \
    FontWeight, Colors, FontSize, Spacing, ContainerStyle, AdaptiveCard

import webex_notification_service

load_dotenv()

from scc_firewall_manager_sdk import MSPLicensingApi, MspVirtualAccountDto, \
    MspSmartAccountDto, MspLicenseDto
from webexpythonsdk import WebexAPI

import api_client_factory


# TODO for simplicity, I have not implemented pagination. That is fairly straighforward but I don't want to overcomplicate the demo code

def build_license_card(out_of_compliance_licenses: List[MspLicenseDto]) -> AdaptiveCard:
    card_body: list = [
        TextBlock("⚠️ License Compliance Alert", weight=FontWeight.BOLDER, size=FontSize.LARGE, color=Colors.ATTENTION),
        TextBlock(f"{len(out_of_compliance_licenses)} license(s) out of compliance", spacing=Spacing.NONE, isSubtle=True),
    ]
    
    for license in out_of_compliance_licenses:
        tenants = ", ".join([mt.display_name for mt in license.managed_tenants])
        
        container_items = [
            TextBlock(f"📋 {license.name}", weight=FontWeight.BOLDER, color=Colors.ATTENTION),
            ColumnSet(columns=[
                Column(items=[TextBlock("Purchased", isSubtle=True), TextBlock(str(license.num_purchased), weight=FontWeight.BOLDER)], width="auto"),
                Column(items=[TextBlock("In Use", isSubtle=True), TextBlock(str(license.num_in_use), weight=FontWeight.BOLDER, color=Colors.ATTENTION)], width="auto"),
            ]),
        ]
        if license.type == 'TERM':
            container_items.append(TextBlock(f"Expiry: {license.expiry_date}", isSubtle=True))
        container_items.append(TextBlock(f"**Tenants:** {tenants}", wrap=True))
        
        license_container = Container(
            items=container_items,
            style=ContainerStyle.EMPHASIS,
            separator=True
        )
        card_body.append(license_container)
    
    return AdaptiveCard(body=[item for item in card_body if item is not None])


def notify(out_of_compliance_licenses: List[MspLicenseDto]) -> None:
    if not out_of_compliance_licenses:
        print("No out-of-compliance licenses found.")
        return
    
    card = build_license_card(out_of_compliance_licenses)
    fallback_msg = f"License Compliance Alert: {len(out_of_compliance_licenses)} license(s) out of compliance"
    webex_notification_service.send_card(card, fallback_msg)



def check_msp_smart_licensing() -> None:
    with api_client_factory.build_api_client() as api_client:
        msp_licensing_apis = MSPLicensingApi(api_client)
        customer_smart_accounts: List[
            MspSmartAccountDto] = msp_licensing_apis.get_msp_smart_accounts().items
        customer_virtual_accounts: List[MspVirtualAccountDto] = []
        for customer_smart_account in customer_smart_accounts:
            customer_virtual_accounts.extend(
                msp_licensing_apis.get_msp_virtual_accounts(
                    smart_account_uid=customer_smart_account.uid).items)
        out_of_compliance_licenses: List[MspLicenseDto] = []
        for customer_virtual_account in customer_virtual_accounts:
            out_of_compliance_licenses.extend(
                msp_licensing_apis.get_msp_virtual_account_licenses(
                    smart_account_uid=customer_virtual_account.smart_account_uid,
                    virtual_account_uid=customer_virtual_account.uid,
                    q='complianceStatus:OUT_OF_COMPLIANCE').items)

        notify(out_of_compliance_licenses)


if __name__ == "__main__":
    check_msp_smart_licensing()
