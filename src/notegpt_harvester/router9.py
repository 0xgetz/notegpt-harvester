"""9Router connector.

9Router (https://9router.com) is a local, OpenAI-compatible AI routing gateway
with a management API. The dashboard normally adds providers by hand; this
module automates that so every harvested NoteGPT token is registered as its own
connection in one shot.

Verified management endpoints (self-hosted instance, default
``http://localhost:20128``):

* ``GET  /api/providers``            list provider connections
* ``POST /api/providers``            create a connection
        body: ``{provider, authType, name, apiKey, providerSpecificData?}``
* ``POST /api/providers/validate``   probe credentials before saving
* ``GET  /api/provider-nodes``       list custom OpenAI/Anthropic nodes
* ``POST /api/provider-nodes``       create a custom compatible node

NoteGPT is not a built-in provider, so the connector registers a custom
``openai-compatible`` node pointing at the NoteGPT gateway and then attaches one
API-key connection per harvested account.
"""

from __future__ import annotations

from dataclasses import dataclass

import httpx

from .config import NineRouterConfig
from .logger import log
from .models import Account


class RouterError(RuntimeError):
    """Raised when the 9Router management API rejects a request."""


@dataclass
class ConnectorResult:
    imported: int
    failed: int
    duplicate: int
    details: list[str]


class NineRouterConnector:
    """Push harvested NoteGPT accounts into a 9Router instance."""

    def __init__(self, cfg: NineRouterConfig, timeout: float = 20.0) -> None:
        self.cfg = cfg
        self._client = httpx.AsyncClient(base_url=cfg.base_url.rstrip("/"), timeout=timeout)

    async def __aenter__(self) -> NineRouterConnector:
        return self

    async def __aexit__(self, *exc) -> None:
        await self.close()

    async def close(self) -> None:
        await self._client.aclose()

    # -- headers ---------------------------------------------------------
    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        if self.cfg.api_key:
            headers["Authorization"] = f"Bearer {self.cfg.api_key}"
        return headers

    async def ping(self) -> bool:
        """Return True when the 9Router management API is reachable."""
        try:
            resp = await self._client.get("/api/providers", headers=self._headers())
            return resp.status_code < 500
        except httpx.HTTPError as exc:
            log.debug("9router ping failed: %s", exc)
            return False

    async def list_providers(self) -> list[dict]:
        resp = await self._client.get("/api/providers", headers=self._headers())
        resp.raise_for_status()
        data = resp.json()
        return data if isinstance(data, list) else data.get("providers") or data.get("data") or []

    async def ensure_node(self) -> None:
        """Create the custom OpenAI-compatible node if it does not exist."""
        if not self.cfg.create_node:
            return
        resp = await self._client.get("/api/provider-nodes", headers=self._headers())
        if resp.status_code == 200:
            nodes = resp.json()
            nodes = nodes if isinstance(nodes, list) else nodes.get("data") or []
            if any(n.get("id") == self.cfg.provider_id or n.get("name") == self.cfg.provider_name for n in nodes):
                log.debug("9router node %s already exists", self.cfg.provider_id)
                return
        payload = {
            "id": self.cfg.provider_id,
            "name": self.cfg.provider_name,
            "type": self.cfg.node_type,
            "baseUrl": self.cfg.openai_base_url,
            "prefix": self.cfg.prefix,
        }
        resp = await self._client.post("/api/provider-nodes", headers=self._headers(), json=payload)
        if resp.status_code >= 400:
            # Some versions only accept nodes created through the UI; a node may
            # already exist under the built-in custom endpoint. Do not abort.
            log.warning("could not create node (%s): %s", resp.status_code, resp.text[:200])
        else:
            log.info("created 9router provider node %s", self.cfg.provider_id)

    async def add_account(self, account: Account) -> str:
        """Create a provider connection for one harvested account."""
        if not account.x_token:
            raise RouterError("account has no token")
        payload = {
            "provider": self.cfg.provider_id,
            "authType": "apikey",
            "name": f"{self.cfg.provider_name} · {account.email}",
            "apiKey": account.openai_api_key(),
            "providerSpecificData": {
                "baseUrl": self.cfg.openai_base_url,
                "prefix": self.cfg.prefix,
                "nodeName": self.cfg.provider_name,
                "email": account.email,
                "cookie": account.cookie_header(),
            },
        }
        resp = await self._client.post("/api/providers", headers=self._headers(), json=payload)
        if resp.status_code >= 400:
            text = resp.text[:300]
            if resp.status_code in (409, 400) and "exist" in text.lower():
                return "duplicate"
            raise RouterError(f"HTTP {resp.status_code}: {text}")
        return "imported"

    async def import_accounts(self, accounts: list[Account]) -> ConnectorResult:
        """Import every successful account, tolerating individual failures."""
        if not self.cfg.enabled:
            return ConnectorResult(0, 0, 0, ["connector disabled"])
        if not await self.ping():
            raise RouterError(
                f"9Router management API not reachable at {self.cfg.base_url}. "
                "Start it with `npx 9router` (default port 20128) or set router9.base_url."
            )
        await self.ensure_node()

        details: list[str] = []
        imported = failed = duplicate = 0
        for account in accounts:
            try:
                status = await self.add_account(account)
                if status == "duplicate":
                    duplicate += 1
                    details.append(f"{account.email}: already present")
                else:
                    imported += 1
                    details.append(f"{account.email}: connected")
            except (RouterError, httpx.HTTPError) as exc:
                failed += 1
                details.append(f"{account.email}: {exc}")
                log.warning("failed to connect %s: %s", account.email, exc)
        return ConnectorResult(imported, failed, duplicate, details)
