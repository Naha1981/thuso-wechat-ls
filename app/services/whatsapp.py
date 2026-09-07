from __future__ import annotations
import httpx
from app.core.config import get_settings

class WhatsAppClient:
    """Baileys operator client. Domain services should use the transport interface."""
    def __init__(self) -> None:
        self.settings = get_settings()
        self.base = self.settings.operator_url.rstrip('/')
        self.headers = {'x-api-key': self.settings.operator_api_key}

    async def start(self, account_key: str) -> dict:
        async with httpx.AsyncClient(timeout=20) as client:
            r = await client.post(f'{self.base}/start', headers=self.headers, json={'accountKey': account_key})
            r.raise_for_status(); return r.json()

    async def status(self, account_key: str) -> dict:
        async with httpx.AsyncClient(timeout=20) as client:
            r = await client.get(f'{self.base}/status/{account_key}', headers=self.headers)
            r.raise_for_status(); return r.json()

    async def reset(self, account_key: str) -> dict:
        async with httpx.AsyncClient(timeout=20) as client:
            r = await client.post(f'{self.base}/reset', headers=self.headers, json={'accountKey': account_key})
            r.raise_for_status(); return r.json()

    async def capabilities(self, account_key: str) -> dict:
        async with httpx.AsyncClient(timeout=20) as client:
            r = await client.get(f'{self.base}/capabilities/{account_key}', headers=self.headers)
            r.raise_for_status(); return r.json()

    async def _send(self, to: str, payload: dict, account_key: str) -> dict:
        if not account_key: raise ValueError('account_key required')
        async with httpx.AsyncClient(timeout=20) as client:
            r = await client.post(f'{self.base}/send', headers=self.headers, json={'to': to, 'accountKey': account_key, **payload})
            r.raise_for_status(); return r.json()

    async def send_text(self, to: str, body: str, account_key: str) -> dict:
        return await self._send(to, {'type': 'text', 'text': body}, account_key)

    async def send_buttons(self, to: str, body: str, buttons: list[tuple[str, str]], account_key: str) -> dict:
        return await self._send(to, {'type': 'buttons', 'body': body, 'buttons': [{'id': i, 'title': t} for i,t in buttons[:3]]}, account_key)

    async def request_location(self, to: str, body: str = 'Please share your location.', account_key: str = '') -> dict:
        return await self._send(to, {'type': 'location_request', 'body': body}, account_key)
