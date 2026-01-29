#!/usr/bin/env python3
"""
Collects FMC health metrics from multiple tenants and outputs in InfluxDB line protocol format.
"""

import json
import sys
import time
from typing import List, Dict, Tuple

from dataclasses import dataclass
from pathlib import Path

from scc_firewall_manager_sdk import ApiClient, Configuration, InventoryApi, \
    FmcHealthMetrics, DeviceHealthApi, Device, MetricsItem

TENANTS_FILE = Path("/etc/telegraf/tenants.json")


@dataclass(frozen=True)
class Tenant:
    name: str
    region: str
    api_token: str


def fetch_asa_devices(tenant: Tenant) -> List[Device]:
    return _fetch_asa_devices(tenant, 0, [])


def _fetch_asa_devices(tenant: Tenant, offset: int, devices: List[Device]) -> \
    List[Device]:
    with ApiClient(
        Configuration(
            host=f"https://api.{tenant.region}.security.cisco.com/firewall",
            access_token=tenant.api_token
        )
    ) as api_client:
        inventory_api = InventoryApi(api_client)
        device_page = inventory_api.get_devices(q="deviceType:ASA",
                                                offset=str(offset),
                                                limit=str(200))
        devices.extend(device_page.items)
        if device_page.count > len(devices):
            return _fetch_asa_devices(tenant, offset + 200, devices)
        return devices


def fetch_asa_metrics(tenant: Tenant) -> List[MetricsItem]:
    """Fetch ASA metrics and return (metrics, uid_to_name mapping)."""
    all_metrics: List[MetricsItem] = []
    with ApiClient(
        Configuration(
            host=f"https://api.{tenant.region}.security.cisco.com/firewall",
            access_token=tenant.api_token
        )
    ) as api_client:
        device_health_api = DeviceHealthApi(api_client)
        total = -1
        offset = 0
        limit = 50
        while total < 0 or limit + offset < total:
            metrics_response = device_health_api.get_asa_health_metrics(
                time_range="10m", metrics="cpu,mem,disk",
                limit=str(limit), offset=str(offset))
            all_metrics.extend(metrics_response.items)
            total = metrics_response.total
            offset += limit
    return all_metrics


def asa_metrics_to_line_protocol(tenant_name: str, metrics_item: MetricsItem,
    uid_to_name: Dict[str, str]) -> List[str]:
    """Convert ASA MetricsItem to InfluxDB line protocol format."""
    lines = []
    device_uid = metrics_item.uid or "unknown"
    device_name = uid_to_name.get(device_uid, "unknown")

    tags = f"tenant={escape_tag_value(tenant_name)},deviceName={escape_tag_value(device_name)},deviceUid={escape_tag_value(device_uid)}"

    metrics = metrics_item.metrics
    if not metrics:
        return lines

    # Collect all timestamps from series data
    timestamps = set()
    cpu = metrics.get('cpu')
    mem = metrics.get('mem')
    disk = metrics.get('disk')

    if cpu and cpu.series:
        for s in cpu.series:
            timestamps.add(s.timestamp)
    if mem and mem.series:
        for s in mem.series:
            timestamps.add(s.timestamp)
    if disk and disk.series:
        for s in disk.series:
            timestamps.add(s.timestamp)

    # Build lookup dicts for each metric type
    cpu_values = {s.timestamp: s.value for s in cpu.series} if cpu and cpu.series else {}
    mem_values = {s.timestamp: s.value for s in mem.series} if mem and mem.series else {}
    disk_values = {s.timestamp: s.value for s in disk.series} if disk and disk.series else {}

    # Output a line for each timestamp
    for ts in sorted(timestamps):
        fields = []
        if ts in cpu_values:
            fields.append(f"cpu_pct={cpu_values[ts]}")
        if ts in mem_values:
            fields.append(f"memory_pct={mem_values[ts]}")
        if ts in disk_values:
            fields.append(f"disk_pct={disk_values[ts]}")
        if fields:
            timestamp_ns = int(ts.timestamp() * 1_000_000_000)
            lines.append(
                f"asa_health_metrics,{tags} {','.join(fields)} {timestamp_ns}")

    return lines


def fetch_fmc_metrics(tenant: Tenant) -> List[FmcHealthMetrics]:
    """Fetch health metrics for a single tenant."""
    with ApiClient(
        Configuration(
            host=f"https://api.{tenant.region}.security.cisco.com/firewall",
            access_token=tenant.api_token
        )
    ) as api_client:
        inventory_api = InventoryApi(api_client)
        fmc_uid = inventory_api.get_device_managers(limit=str(1),
                                                    q="deviceType:CDFMC").items[
            0].uid
        return inventory_api.get_fmc_health(fmc_uid=fmc_uid, time_range="5m")


def escape_tag_value(value: str) -> str:
    """Escape special characters in InfluxDB tag values."""
    return value.replace(" ", "\\ ").replace(",", "\\,").replace("=", "\\=")


def fmc_metrics_to_line_protocol(tenant_name: str,
    device_health_metric: FmcHealthMetrics) -> List[str]:
    """Convert FmcHealthMetrics to InfluxDB line protocol format."""
    lines = []
    timestamp = int(time.time() * 1_000_000_000)

    device_uid = device_health_metric.device_uid or "unknown"
    device_name = device_health_metric.device_name or "unknown"

    tags = f"tenant={escape_tag_value(tenant_name)},deviceName={escape_tag_value(device_name)},deviceUid={escape_tag_value(device_uid)}"

    # CPU metrics
    cpu = device_health_metric.cpu_health_metrics
    if cpu:
        fields = []
        if cpu.lina_usage_avg is not None:
            fields.append(f"cpu_lina_pct={cpu.lina_usage_avg}")
        if cpu.snort_usage_avg is not None:
            fields.append(f"cpu_snort_pct={cpu.snort_usage_avg}")
        if cpu.system_usage_avg is not None:
            fields.append(f"cpu_system_pct={cpu.system_usage_avg}")
        if fields:
            lines.append(
                f"fmc_health_metrics,{tags} {','.join(fields)} {timestamp}")

    # Memory metrics
    memory = device_health_metric.memory_health_metrics
    if memory:
        fields = []
        if memory.lina_usage_avg is not None:
            fields.append(f"memory_lina_pct={memory.lina_usage_avg}")
        if memory.snort_usage_avg is not None:
            fields.append(f"memory_snort_pct={memory.snort_usage_avg}")
        if memory.system_usage_avg is not None:
            fields.append(f"memory_system_pct={memory.system_usage_avg}")
        if fields:
            lines.append(
                f"fmc_health_metrics,{tags} {','.join(fields)} {timestamp}")

    # Disk metrics
    disk = device_health_metric.disk_health_metrics
    if disk:
        fields = []
        if disk.total_disk_usage_avg is not None:
            fields.append(f"disk_total_pct={disk.total_disk_usage_avg}")
        if fields:
            lines.append(
                f"fmc_health_metrics,{tags} {','.join(fields)} {timestamp}")

    return lines


def main():
    if not TENANTS_FILE.exists():
        print(f"Tenants file not found: {TENANTS_FILE}", file=sys.stderr)
        sys.exit(1)

    with open(TENANTS_FILE) as f:
        tenants = [Tenant(**t) for t in json.load(f)]

    all_lines = []

    for tenant in tenants:
        # Collect FMC-managed FTD metrics
        fmc_health_metrics = fetch_fmc_metrics(tenant)
        for device_health_metric in fmc_health_metrics:
            lines = fmc_metrics_to_line_protocol(tenant.name,
                                                 device_health_metric)
            all_lines.extend(lines)

        # Collect ASA metrics
        devices = fetch_asa_devices(tenant)
        uid_to_name = {device.uid: device.name for device in devices}
        asa_metrics = fetch_asa_metrics(tenant)
        for metrics_item in asa_metrics:
            lines = asa_metrics_to_line_protocol(tenant.name, metrics_item,
                                                 uid_to_name)
            all_lines.extend(lines)

        # Rate limit: wait between tenant API calls
        if tenant != tenants[-1]:
            time.sleep(1)

    for line in all_lines:
        print(line)


if __name__ == "__main__":
    main()
