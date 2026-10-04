"""Pluggable temporary-email clients.

Two providers ship out of the box:

* ``mailtm``  — the public mail.tm REST API. Fully scriptable without a browser,
  so it is the default and the recommended provider.
* ``zenvex``  — https://zenvex.dev. Its REST surface (``/api/emails/{addr}``) is
  guarded by Cloudflare and must be called with a browser-issued session. Use it
  when you already run inside a browser context (see ``session.py``); the helper
  here still accepts the browser's cookies via ``extra_headers``.

Both expose the same interface: :meth:`create_address`, :meth:`fetch_messages`
and :meth:`wait_for_message`.
"""

from __future__ import annotations

import asyncio
import random
import re
import string
import time
from dataclasses import dataclass

import httpx

from .config import EmailConfig
from .logger import log

LINK_PATTERN = r"https?://[^\s\"'<>]+"
VERIFY_HINTS = ("verify", "confirm", "token", "activate", "register")


@dataclass
class EmailMessage:
    subject: str
    sender: str
    body: str
    received_at: float
    raw: dict


class BaseEmailClient:
    """Common interface for temporary email providers."""

    def __init__(self, cfg: EmailConfig, proxy: str = "") -> None:
        self.cfg = cfg
        self._proxy = proxy or None

    async def __aenter__(self):
        await self.start()
        return self

    async def __aexit__(self, *exc) -> None:
        await self.close()

    async def start(self) -> None:
        raise NotImplementedError

    async def close(self) -> None:
        raise NotImplementedError

    async def create_address(self) -> str:
        raise NotImplementedError

    async def fetch_messages(self, address: str) -> list[EmailMessage]:
        raise NotImplementedError

    def random_prefix(self, length: int = 10) -> str:
        alphabet = string.ascii_lowercase + string.digits
        return self.cfg.prefix + "".join(random.choice(alphabet) for _ in range(length))

    async def wait_for_message(
        self,
        address: str,
        *,
        subject_contains: str = "",
        timeout: float | None = None,
    ) -> tuple[EmailMessage, str] | None:
        """Poll until a matching message with a link arrives."""
        deadline = time.time() + (timeout if timeout is not None else self.cfg.poll_timeout)
        seen: set[str] = set()
        while time.time() < deadline:
            for msg in await self.fetch_messages(address):
                key = f"{msg.sender}|{msg.subject}|{msg.received_at}"
                if key in seen:
                    continue
                seen.add(key)
                if subject_contains and subject_contains.lower() not in msg.subject.lower():
                    continue
                link = extract_link(msg.body)
                if link:
                    return msg, link
            await asyncio.sleep(self.cfg.poll_interval)
        log.warning("no verification email for %s within %.0fs", address, timeout or self.cfg.poll_timeout)
        return None


class MailTMClient(BaseEmailClient):
    """Client for the public mail.tm API (https://docs.mail.tm)."""

    def __init__(self, cfg: EmailConfig, proxy: str = "") -> None:
        super().__init__(cfg, proxy)
        self.api = (cfg.api_url if cfg.api_url and "mail.tm" in cfg.api_url else "https://api.mail.tm").rstrip("/")
        self._client = httpx.AsyncClient(
            base_url=self.api,
            timeout=20.0,
            proxy=self._proxy,
            follow_redirects=True,
            headers={"Accept": "application/json"},
        )
        self._account_id: str | None = None
        self._token: str | None = None
        self._password = "Harvest#2026x"
        self._address: str | None = None

    async def start(self) -> None:
        resp = await self._client.get("/domains")
        resp.raise_for_status()
        data = resp.json()
        domains = data if isinstance(data, list) else data.get("hydra:member", [])
        domain = self.cfg.domain if any(d.get("domain") == self.cfg.domain for d in domains) else domains[0]["domain"]
        self._domain = domain

    async def close(self) -> None:
        await self._client.aclose()

    async def _auth_headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._token}"} if self._token else {}

    async def create_address(self) -> str:
        domain = getattr(self, "_domain", self.cfg.domain)
        address = f"{self.random_prefix()}@{domain}"
        resp = await self._client.post("/accounts", json={"address": address, "password": self._password})
        if resp.status_code == 429:
            raise RuntimeError("mail.tm rate limited; slow down or use a proxy")
        resp.raise_for_status()
        self._account_id = resp.json().get("id")
        self._address = address

        token_resp = await self._client.post("/token", json={"address": address, "password": self._password})
        token_resp.raise_for_status()
        self._token = token_resp.json().get("token")
        log.debug("mail.tm created %s", address)
        return address

    async def fetch_messages(self, address: str) -> list[EmailMessage]:
        resp = await self._client.get("/messages", headers=await self._auth_headers())
        if resp.status_code >= 400:
            return []
        payload = resp.json()
        if isinstance(payload, list):
            items = payload
        else:
            items = payload.get("hydra:member") or payload.get("member") or payload.get("messages") or []
        messages: list[EmailMessage] = []
        for item in items:
            full = await self._client.get(f"/messages/{item['id']}", headers=await self._auth_headers())
            if full.status_code >= 400:
                continue
            detail = full.json()
            html = detail.get("html")
            text = detail.get("text")
            if isinstance(html, list):
                html = "\n".join(html)
            if isinstance(text, list):
                text = "\n".join(text)
            body = html or text or ""
            sender = detail.get("from") or {}
            messages.append(
                EmailMessage(
                    subject=detail.get("subject", ""),
                    sender=sender.get("address", "") if isinstance(sender, dict) else str(sender),
                    body=body,
                    received_at=time.time(),
                    raw=detail,
                )
            )
        return messages


class ZenvexClient(BaseEmailClient):
    """Client for zenvex.dev (Cloudflare-guarded; needs browser session headers)."""

    def __init__(self, cfg: EmailConfig, proxy: str = "", extra_headers: dict | None = None) -> None:
        super().__init__(cfg, proxy)
        base = cfg.base_url.rstrip("/") if cfg.base_url else "https://zenvex.dev"
        self._client = httpx.AsyncClient(base_url=base, timeout=20.0, proxy=self._proxy, follow_redirects=True)
        self._extra = extra_headers or {}

    async def start(self) -> None:
        return None

    async def close(self) -> None:
        await self._client.aclose()

    def _headers(self) -> dict[str, str]:
        base = {
            "Origin": "https://zenvex.dev",
            "Referer": "https://zenvex.dev/inbox",
            "Accept": "application/json",
        }
        base.update(self._extra)
        return base

    async def create_address(self) -> str:
        return f"{self.random_prefix()}@{self.cfg.domain}"

    async def fetch_messages(self, address: str) -> list[EmailMessage]:
        resp = await self._client.get(
            f"/api/emails/{address}",
            params={"limit": 100, "offset": 0},
            headers=self._headers(),
        )
        if resp.status_code >= 400:
            return []
        payload = resp.json()
        items = payload.get("data") or payload.get("emails") or []
        return [
            EmailMessage(
                subject=str(item.get("subject", "")),
                sender=str(item.get("from") or item.get("sender", "")),
                body=str(item.get("html") or item.get("body") or item.get("text") or ""),
                received_at=float(item.get("received_at") or item.get("timestamp") or time.time()),
                raw=item,
            )
            for item in items
        ]


class TempEmailClient:
    """Factory that returns the configured provider client."""

    @staticmethod
    def create(cfg: EmailConfig, proxy: str = "", extra_headers: dict | None = None) -> BaseEmailClient:
        provider = (cfg.provider or "mailtm").lower()
        if provider in ("mailtm", "mail.tm"):
            return MailTMClient(cfg, proxy)
        if provider == "zenvex":
            return ZenvexClient(cfg, proxy, extra_headers)
        raise ValueError(f"unsupported email provider: {provider!r} (use 'mailtm' or 'zenvex')")


def extract_link(body: str, pattern: str = LINK_PATTERN) -> str:
    """Pull the first usable verification link from a message body."""
    hrefs = re.findall(r'href=["\']([^"\']+)["\']', body)
    for href in hrefs:
        if any(k in href.lower() for k in VERIFY_HINTS):
            return href.replace("&amp;", "&")
    for match in re.findall(pattern, body):
        if any(k in match.lower() for k in VERIFY_HINTS):
            return match.replace("&amp;", "&")
    return hrefs[0].replace("&amp;", "&") if hrefs else ""
