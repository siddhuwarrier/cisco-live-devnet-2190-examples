# Device Health Metrics with Telegraf, InfluxDB & Grafana

This stack collects health metrics from Security Cloud Control Firewall Manager (SCCFM) across **multiple tenants** and visualizes them using Grafana.

## Components

- **Telegraf** - Polls the SCCFM health metrics API every minute for all configured tenants
- **InfluxDB** - Time-series database for storing metrics
- **Grafana** - Visualization and dashboarding with tenant filtering

## Prerequisites

- Docker and Docker Compose installed
- SCCFM API access with valid Bearer tokens for each tenant
- FMC UIDs for each tenant

## Setup

1. **Copy the environment template:**
   ```bash
   cp .env.template .env
   ```

2. **Edit `.env` with your InfluxDB token:**
   ```
   INFLUXDB_TOKEN=my-secret-influx-token
   ```

3. **Copy and configure tenants:**
   ```bash
   cp tenants.json.tpl tenants.json
   ```

   Edit `tenants.json` with your tenant details:
   ```json
   [
     {
       "name": "Production",
       "region": "us",
       "fmc_uid": "your-fmc-uid-1",
       "bearer_token": "your-bearer-token-1"
     },
     {
       "name": "Staging",
       "region": "eu",
       "fmc_uid": "your-fmc-uid-2",
       "bearer_token": "your-bearer-token-2"
     }
   ]
   ```

   Each tenant requires:
   - **name** - Display name for the tenant (shown in Grafana dropdown)
   - **region** - API region: `us`, `eu`, `apj`, `aus`, `uae`, or `int`
   - **fmc_uid** - The FMC unique identifier
   - **bearer_token** - API Bearer token for authentication

4. **Build and start the stack:**
   ```bash
   docker compose up -d --build
   ```

5. **Access the services:**
   - **Grafana**: http://localhost:3000 (admin / admin)
   - **InfluxDB**: http://localhost:8086 (admin / adminpass)

6. **Use the Tenant dropdown** in Grafana to filter metrics by tenant.

## Metrics Collected

The following metrics are collected for each managed device across all tenants:

| Category | Metrics |
|----------|---------|
| **CPU** | Lina usage, Snort usage, System usage |
| **Memory** | Lina usage, Snort usage, System usage |
| **Disk** | Total disk usage |

## Adding/Removing Tenants

1. Edit `tenants.json` to add or remove tenant entries
2. Restart Telegraf: `docker compose restart telegraf`
3. The new tenants will appear in the Grafana dropdown after data is collected

## Troubleshooting

**Reset InfluxDB (if you need to change the token):**
```bash
docker compose down -v
docker compose up -d --build
```

**Check Telegraf logs:**
```bash
docker logs telegraf
```

**Test the Python collection script:**
```bash
docker compose exec telegraf python3 /etc/telegraf/collect_metrics.py
```
