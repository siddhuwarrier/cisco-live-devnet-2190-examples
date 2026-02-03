# Cisco Live EMEAR 2026 - DEVNET-2190 Examples

This repository contains example code for the **DEVNET-2190** session at Cisco Live EMEAR 2026 in
Amsterdam.

> **Note:** This README was generated using an LLM. Your mileage may vary (YMMV). Please verify all
> instructions and adapt them to your specific environment.

## ⚠️ Important Notice

**This code is for educational and demonstration purposes only.** It is intentionally written to be
clear and easy to understand for learning purposes, rather than following production-grade best
practices. The code is not as DRY (Don't Repeat Yourself) as it could be, and some patterns are
simplified for pedagogical reasons. **Do not use this code in production environments without
significant refactoring and hardening.**

## Prerequisites

- Python 3.12 or higher
- Access to a Cisco Defense Orchestrator (CDO) MSP Portal
- An API token for your MSP Portal

## Setup Instructions

### 1. Clone the Repository

```bash
git clone <repository-url>
cd cl-emear-2026-examples
```

### 2. Create a Virtual Environment

```bash
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure Environment Variables

Copy the `.env.template` file to `.env`:

```bash
cp .env.template .env
```

Edit the `.env` file and add your MSP Portal API token:

```
SCCFM_API_TOKEN=<your-msp-portal-api-token>
WEBEX_BOT_TOKEN=<your-webex-bot-token>  # Optional, only needed for notifications
```

**Important:** Make sure to obtain an API-only user token from your MSP Portal in CDO.

### 5. Configure Region

Edit `api_client_factory.py` and set the `region` variable to match your MSP Portal deployment:

```python
region = "int"  # Change to: us, eu, apj, aus, in, uae, etc.
```

## Available Examples

### Managed Organization Management

- **`create_managed_organization.py`** - Creates a new managed tenant/organization in your MSP
  Portal
- **`create_users_in_managed_organization.py`** - Adds users to a managed organization
  ```bash
  python create_users_in_managed_organization.py --tenant-uid <tenant-uid> \
    --user-first-names "John,Jane" \
    --user-last-names "Doe,Smith" \
    --user-roles "ROLE_ADMIN,ROLE_READ_ONLY" \
    --user-emails "john@example.com,jane@example.com"
  ```
- **`provision_cdfmc_in_managed_organization.py`** - Provisions a cloud-delivered Firewall
  Management Center (cdFMC) in a managed organization
  ```bash
  python provision_cdfmc_in_managed_organization.py --tenant-uid <tenant-uid>
  ```

### Device Management

- **`upgrade_ftds.py`** - Interactive tool to upgrade Firepower Threat Defense (FTD) devices across
  managed organizations
  ```bash
  python upgrade_ftds.py
  ```
- **`backup_all_msp_managed_ftds.py`** - Creates backups of all FTD devices managed by the MSP
  Portal
  ```bash
  python backup_all_msp_managed_ftds.py
  ```

### Policy Management

- **`create_cdfmc_access_policy.py`** - Creates an access policy in cdFMC and adds a rule to block
  gambling websites
  ```bash
  python create_cdfmc_access_policy.py --tenant-name <tenant-name>
  ```

### Compliance & Notifications

- **`licensing_compliance_notifier.py`** - Checks licensing compliance and sends notifications via
  Webex
  ```bash
  python licensing_compliance_notifier.py
  ```

## Utility Modules

- **`api_client_factory.py`** - Factory for creating API clients for both MSP Portal and managed
  tenants
- **`transaction_service.py`** - Service for polling and waiting on CDO transactions
- **`msp_managed_tenant_token_service.py`** - Service for generating API tokens for managed tenants
- **`webex_notification_service.py`** - Service for sending notifications via Webex

## Project Structure

```
.
├── api_client_factory.py           # API client factory
├── transaction_service.py          # Transaction polling service
├── msp_managed_tenant_token_service.py  # Token generation for managed tenants
├── models/
│   └── fmc.py                      # Data models for FMC API objects
├── create_managed_organization.py
├── create_users_in_managed_organization.py
├── provision_cdfmc_in_managed_organization.py
├── upgrade_ftds.py
├── backup_all_msp_managed_ftds.py
├── create_cdfmc_access_policy.py
├── licensing_compliance_notifier.py
├── webex_notification_service.py
├── requirements.txt
├── .env.template
└── README.md
```

## Common Workflows

### Setting up a New Managed Organization

1. Create the managed organization:
   ```bash
   python create_managed_organization.py
   ```

2. Add users to the organization:
   ```bash
   python create_users_in_managed_organization.py --tenant-uid <tenant-uid> \
     --user-first-names "Admin" \
     --user-last-names "User" \
     --user-roles "ROLE_ADMIN" \
     --user-emails "admin@example.com"
   ```

3. Provision cdFMC:
   ```bash
   python provision_cdfmc_in_managed_organization.py --tenant-uid <tenant-uid>
   ```

4. Create access policies:
   ```bash
   python create_cdfmc_access_policy.py --tenant-name <tenant-name>
   ```

## Troubleshooting

- **Authentication errors**: Verify your API token in `.env` is correct and has not expired
- **Region errors**: Ensure the `region` variable in `api_client_factory.py` matches your MSP Portal
  deployment
- **Transaction timeouts**: Some operations (like provisioning cdFMC) can take several minutes to
  complete

## Resources

- [Security Cloud Control](https://security.cisco.com)
- [CDO API Documentation](https://developer.cisco.com/docs/cisco-security-cloud-control-firewall-manager/getting-started/)
- [Cisco Live EMEAR 2026](https://www.ciscolive.com/emea.html)

## Author & Presenter

**Siddhu Warrier** is a Principal Engineer on the Security Cloud Control Firewall Manager team, based in
London. He is passionate about Test-Driven Development (TDD), and Continuous
Delivery. Siddhu is a recipient of the distinguished speaker award, and has spoken at multiple Cisco
Live events over the years.

- **GitHub:** [siddhuwarrier](https://github.com/siddhuwarrier)
- **LinkedIn:** [siddhuwarrier](https://www.linkedin.com/in/siddhuwarrier/)

## Session Information

**Session:** DEVNET-2190  
**Event:** Cisco Live EMEAR 2026  
**Location:** Amsterdam, Netherlands  
**Time:** 11:00 AM, February 10th, 2026

---

**Remember:** This code is for learning and demonstration purposes. Always follow security best
practices and organizational policies when working with production systems.
