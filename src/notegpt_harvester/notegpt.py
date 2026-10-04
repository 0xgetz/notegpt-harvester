"""HTTP client for the NoteGPT account/auth API.

Flow (verified against the live site):

1. ``POST /api/v1/auth/email/register`` with ``{email, password}``
   -> triggers a verification email; returns ``{"code":100000,...}``.
2. ``POST /api/v1/auth/email/register/confirm`` with ``{token}``
   -> confirms the account. ``token`` is embedded in the email link.
3. ``POST /api/v1/auth/email/login`` with ``{email, password}``
   -> returns ``{data:{access_token, user_name, email, ...}}``.

The returned ``access_token`` is the same value the frontend persists as
``X-Token`` in localStorage and mirrors into the httpOnly ``nc_token`` cookie.
"""

from __future__ import annotations

import asyncio
import random
import re
import string

import httpx

from .config import NoteGPTConfig, RunConfig
from .logger import log
from .models import Account

REGISTER = "/api/v1/auth/email/register"
REGISTER_CONFIRM = "/api/v1/auth/email/register/confirm"
LOGIN = "/api/v1/auth/email/login"
FORGOT = "/api/v1/auth/email/forgot-password"
USERINFO = "/api/v1/userinfo"
QUOTA = "/api/v2/user/quota"


class NoteGPTError(RuntimeError):
    """Raised when a NoteGPT API call fails."""


class NoteGPTClient:
    """Thin async wrapper around the NoteGPT REST API."""

    def __init__(self, cfg: NoteGPTConfig, run: RunConfig) -> None:
        self.cfg = cfg
        self.run = run
        self._client = httpx.AsyncClient(
            base_url=cfg.base_url,
            timeout=run.request_timeout,
            proxy=run.proxy or None,
            follow_redirects=True,
            headers={
                "User-Agent": run.user_agent,
                "Accept": "application/json, text/plain, */*",
                "Origin": cfg.base_url,
                "Referer": f"{cfg.base_url}/ai-chat",
            },
        )

    async def __aenter__(self) -> NoteGPTClient:
        return self

    async def __aexit__(self, *exc) -> None:
        await self.close()

    async def close(self) -> None:
        await self._client.aclose()

    # -- password generation --------------------------------------------
    @staticmethod
    def generate_password(length: int = 12) -> str:
        """Generate a password satisfying NoteGPT's policy (8-16 chars, mixed)."""
        lower = string.ascii_lowercase
        upper = string.ascii_uppercase
        digits = string.digits
        symbols = "!@#$%^&*"
        pools = [lower, upper, digits, symbols]
        chars = [random.choice(p) for p in pools]
        allchars = lower + upper + digits + symbols
        chars += [random.choice(allchars) for _ in range(max(length, 8) - len(chars))]
        random.shuffle(chars)
        return "".join(chars)[:16]

    # -- API calls -------------------------------------------------------
    async def _post(self, path: str, payload: dict) -> dict:
        resp = await self._client.post(path, json=payload)
        try:
            data = resp.json()
        except ValueError as exc:  # non-JSON error page
            raise NoteGPTError(f"{path} -> HTTP {resp.status_code}: {resp.text[:200]}") from exc
        if resp.status_code >= 400 or data.get("code") not in (None, 100000):
            raise NoteGPTError(f"{path} -> {data.get('code')}: {data.get('message')}")
        return data

    async def register(self, email: str, password: str) -> None:
        await self._post(REGISTER, {"email": email, "password": password})
        log.debug("registered %s", email)

    async def confirm(self, token: str) -> None:
        await self._post(REGISTER_CONFIRM, {"token": token})
        log.debug("confirmed token %.12s...", token)

    async def login(self, email: str, password: str) -> dict:
        data = await self._post(LOGIN, {"email": email, "password": password})
        return data.get("data", {})

    async def userinfo(self, token: str) -> dict:
        resp = await self._client.get(USERINFO, headers={"X-Token": token, "Authorization": f"Bearer {token}"})
        return resp.json().get("data", {})

    async def quota(self, token: str) -> dict:
        resp = await self._client.get(
            QUOTA,
            params={"features": "ai_chat"},
            headers={"X-Token": token, "Authorization": f"Bearer {token}"},
        )
        return resp.json().get("data", {})

    # -- high level ------------------------------------------------------
    async def login_account(
        self,
        email: str,
        password: str,
        *,
        confirm_token: str = "",
    ) -> Account:
        """Confirm (when a token is given), log in, and harvest credentials.

        Registration is performed separately by the caller so it can trigger and
        await the verification email first.
        """
        account = Account(email=email, password=password)
        try:
            if confirm_token:
                await self.confirm(confirm_token)
                account.verified = True

            data = await self.login(email, password)
            token = data.get("access_token")
            if not token:
                account.error = "login returned no access_token"
                return account
            account.x_token = token
            account.nc_token = token
            account.user_id = data.get("user_id")
            account.username = data.get("user_name")
            account.verified = True
            account.cookies = {"nc_token": token}
            try:
                info = await self.userinfo(token)
                account.user_id = info.get("user_id", account.user_id)
                account.username = info.get("user_name", account.username)
            except (NoteGPTError, httpx.HTTPError, ValueError) as exc:
                log.debug("userinfo fetch failed for %s: %s", email, exc)
            try:
                account.quota = await self.quota(token)
            except NoteGPTError as exc:
                log.debug("quota fetch failed for %s: %s", email, exc)
            return account
        except NoteGPTError as exc:
            account.error = str(exc)
            return account

    async def create_account(
        self,
        email: str,
        *,
        password: str | None = None,
        confirm_token: str | None = None,
        verify: bool = True,
    ) -> Account:
        """Register, optionally confirm, then log in and harvest credentials.

        Convenience wrapper used by the ``verify`` CLI path and tests. Bulk runs
        use :meth:`register` + :meth:`login_account` so they can await the email.
        """
        password = password or self.cfg.password or self.generate_password(self.cfg.password_length)
        account = Account(email=email, password=password)
        try:
            await self.register(email, password)
        except NoteGPTError as exc:
            account.error = str(exc)
            return account
        return await self.login_account(email, password, confirm_token=confirm_token or "")


TOKEN_RE = re.compile(r"[?&]token=([^&\s]+)")


def token_from_link(link: str) -> str:
    """Extract the ``token`` query parameter from a verification link."""
    match = TOKEN_RE.search(link)
    return match.group(1) if match else ""


async def gather_with_limit(coro_fns, limit: int):
    """Run awaitables with bounded concurrency, preserving order."""
    sem = asyncio.Semaphore(max(1, limit))

    async def runner(fn):
        async with sem:
            return await fn()

    return await asyncio.gather(*(runner(fn) for fn in coro_fns))
