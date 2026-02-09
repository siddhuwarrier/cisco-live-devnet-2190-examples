from dataclasses import dataclass
from time import sleep
from typing import Optional

import requests
from rich.console import Console


TERMINAL_STATUSES = ["SUCCEEDED", "SUCCESS", "COMPLETED", "Deployed", "FAILED"]


@dataclass
class FmcTask:
    id: str
    task_type: Optional[str]
    message: Optional[str]
    status: str


def _parse_task_response(response_json: dict) -> FmcTask:
    return FmcTask(
        id=response_json.get("id"),
        task_type=response_json.get("taskType"),
        message=response_json.get("message"),
        status=response_json.get("status")
    )


def get_task(host: str, domain_uid: str, task_id: str,
             api_token: str) -> FmcTask:
    url = f"{host}/v1/cdfmc/api/fmc_config/v1/domain/{domain_uid}/job/taskstatuses/{task_id}"
    headers = {
        "Authorization": f"Bearer {api_token}",
        "Content-Type": "application/json",
    }

    response = requests.get(url, headers=headers)
    response.raise_for_status()
    return _parse_task_response(response.json())


def wait_for_task_completion(host: str, domain_uid: str, task_id: str,
                             api_token: str,
                             poll_interval_seconds: int = 5) -> FmcTask:
    console = Console()
    task = get_task(host, domain_uid, task_id, api_token)

    with console.status(
        f"[bold blue]Task {task_id}: {task.status}") as status:
        while task.status not in TERMINAL_STATUSES:
            sleep(poll_interval_seconds)
            task = get_task(host, domain_uid, task_id, api_token)
            status.update(f"[bold blue]Task {task_id}: {task.status}")

    if task.status == "FAILED":
        console.print(f"[bold red]Task failed: {task.message}")
    else:
        console.print(f"[bold green]Task completed: {task.status}")

    return task
