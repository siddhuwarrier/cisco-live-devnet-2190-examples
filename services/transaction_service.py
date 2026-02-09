from time import sleep

from rich.console import Console
from scc_firewall_manager_sdk import TransactionsApi, CdoTransaction, ApiClient

from factories import api_client_factory


def wait_for_transaction_to_finish(transaction: CdoTransaction) -> CdoTransaction:
    with api_client_factory.build_api_client() as api_client:
        wait_for_transaction_to_finish_with_api_client(transaction, api_client)

def wait_for_transaction_to_finish_with_api_client(transaction: CdoTransaction, api_client: ApiClient) -> CdoTransaction:
    console = Console()
    transactions_api = TransactionsApi(api_client)
    with console.status(
        f"[bold blue]Transaction {transaction.transaction_uid}: {transaction.cdo_transaction_status}") as status:
        while transaction.cdo_transaction_status not in ["DONE", "ERROR",
                                                         "CANCELLED"]:
            sleep(3)
            transaction = transactions_api.get_transaction(
                transaction.transaction_uid)
            status.update(
                f"[bold blue]Transaction {transaction.transaction_uid}: {transaction.cdo_transaction_status}")
    if transaction.cdo_transaction_status != 'DONE':
        console.print(
            f"[bold red]Transaction failed: {transaction.cdo_transaction_status}")
        raise Exception(
            f"Transaction {transaction.transaction_uid} failed with status {transaction.cdo_transaction_status}")
    console.print(f"[bold green]Transaction completed successfully!")
    return transaction
