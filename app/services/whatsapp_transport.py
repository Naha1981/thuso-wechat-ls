from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Protocol


class TransportError(RuntimeError):
    pass


@dataclass(frozen=True)
class TransportCapabilities:
    text: bool = True
    buttons: bool = False
    location_request: bool = False
    location_receive: bool = True
    media_send: bool = False
    media_receive: bool = True
    documents: bool = True
    voice_notes: bool = True
    delivery_status: bool = False


class WhatsAppTransport(Protocol):
    name: str

    async def start_account(self, account_key: str) -> dict[str, Any]: ...
    async def status(self, account_key: str) -> dict[str, Any]: ...
    async def reset_account(self, account_key: str) -> dict[str, Any]: ...
    async def send_text(self, account_key: str, to: str, body: str) -> dict[str, Any]: ...
    async def send_buttons(self, account_key: str, to: str, body: str, buttons: list[tuple[str, str]]) -> dict[str, Any]: ...
    async def request_location(self, account_key: str, to: str, body: str) -> dict[str, Any]: ...
    async def capabilities(self, account_key: str) -> TransportCapabilities: ...


class BaileysTransport:
    name = "baileys"

    def __init__(self, client: Any):
        self.client = client

    async def start_account(self, account_key: str) -> dict[str, Any]:
        return await self.client.start(account_key)

    async def status(self, account_key: str) -> dict[str, Any]:
        return await self.client.status(account_key)

    async def reset_account(self, account_key: str) -> dict[str, Any]:
        return await self.client.reset(account_key)

    async def send_text(self, account_key: str, to: str, body: str) -> dict[str, Any]:
        return await self.client.send_text(to, body, account_key=account_key)

    async def send_buttons(self, account_key: str, to: str, body: str, buttons: list[tuple[str, str]]) -> dict[str, Any]:
        return await self.client.send_buttons(to, body, buttons, account_key=account_key)

    async def request_location(self, account_key: str, to: str, body: str) -> dict[str, Any]:
        return await self.client.request_location(to, body, account_key=account_key)

    async def capabilities(self, account_key: str) -> TransportCapabilities:
        return TransportCapabilities(buttons=True, media_send=True, delivery_status=True)


class MetaCloudTransport:
    """Future official Meta transport boundary.

    Kept isolated so switching transports does not touch domain services. It is
    intentionally unavailable until credentials and an explicit transport selection
    are configured. No Baileys internals leak through this interface.
    """
    name = "meta_cloud"

    def __init__(self, settings: Any):
        self.settings = settings

    def _disabled(self) -> None:
        raise TransportError(
            "Meta Cloud transport is not enabled; set WHATSAPP_TRANSPORT=meta_cloud "
            "and configure Meta credentials before using it"
        )

    async def start_account(self, account_key: str) -> dict[str, Any]:
        self._disabled()

    async def status(self, account_key: str) -> dict[str, Any]:
        self._disabled()

    async def reset_account(self, account_key: str) -> dict[str, Any]:
        self._disabled()

    async def send_text(self, account_key: str, to: str, body: str) -> dict[str, Any]:
        self._disabled()

    async def send_buttons(self, account_key: str, to: str, body: str, buttons: list[tuple[str, str]]) -> dict[str, Any]:
        self._disabled()

    async def request_location(self, account_key: str, to: str, body: str) -> dict[str, Any]:
        self._disabled()

    async def capabilities(self, account_key: str) -> TransportCapabilities:
        return TransportCapabilities(buttons=True, media_send=True, delivery_status=True)
