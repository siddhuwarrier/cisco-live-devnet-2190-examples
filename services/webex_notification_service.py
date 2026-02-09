import os

from webexpythonsdk import WebexAPI
from webexpythonsdk.models.cards import AdaptiveCard


def send_card(card: AdaptiveCard, fallback_msg: str | None) -> None:
    webex_api = WebexAPI(access_token=os.getenv('WEBEX_BOT_TOKEN'))
    for room in webex_api.rooms.list():
        webex_api.messages.create(roomId=room.id, text=fallback_msg, attachments=[card])