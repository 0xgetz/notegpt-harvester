"""Bulk harvest orchestration, checkpointing and result persistence."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

from .config import Config
from .email_provider import BaseEmailClient, TempEmailClient
from .logger import log
from .models import Account, RunResult
from .notegpt import NoteGPTClient, token_from_link
from .router9 import NineRouterConnector, RouterError


class Checkpoint:
    """Append-only JSON state so a long run can resume after interruption."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.done: set[str] = set()
        if self.path.exists():
            try:
                data = json.loads(self.path.read_text(encoding="utf-8"))
                self.done = set(data.get("completed_emails", []))
            except (ValueError, OSError):
                self.done = set()

    def mark(self, account: Account) -> None:
        if account.ok:
            self.done.add(account.email)
        self._flush()

    def _flush(self) -> None:
        self.path.write_text(
            json.dumps({"completed_emails": sorted(self.done)}, indent=2),
            encoding="utf-8",
        )

    def clear(self) -> None:
        self.done.clear()
        self._flush()


class Harvester:
    """Drive account creation + credential harvest for a batch of addresses."""

    def __init__(self, cfg: Config) -> None:
        self.cfg = cfg
        self.results_dir = Path(cfg.run.results_dir)
        self.results_dir.mkdir(parents=True, exist_ok=True)
        self.checkpoint = Checkpoint(cfg.run.checkpoint_file)

    async def create_one(self, index: int) -> Account:
        """Create one account end to end and connect it to 9Router."""
        async with TempEmailClient.create(self.cfg.email, self.cfg.run.proxy) as mail:
            address = await mail.create_address()
            log.info("[%d] address %s", index, address)

            # Register first so the site dispatches the verification email, then
            # poll the inbox for the confirmation link.
            password = self.cfg.notegpt.password or NoteGPTClient.generate_password(self.cfg.notegpt.password_length)
            async with NoteGPTClient(self.cfg.notegpt, self.cfg.run) as ng:
                try:
                    await ng.register(address, password)
                except Exception as exc:  # noqa: BLE001
                    return Account(email=address, password=password, error=f"register failed: {exc}")

            confirm_token = ""
            if self.cfg.notegpt.verify_email:
                link = await self._await_verification_link(mail, address)
                if not link:
                    return Account(email=address, password=password, error="verification email not received")
                confirm_token = token_from_link(link)
                if not confirm_token:
                    return Account(email=address, password=password, error="no token in verification link")

            async with NoteGPTClient(self.cfg.notegpt, self.cfg.run) as ng:
                account = await ng.login_account(address, password, confirm_token=confirm_token)
            if account.ok:
                self.checkpoint.mark(account)
                log.info("[%d] harvested token for %s (quota=%s)", index, address, account.quota)
            else:
                log.warning("[%d] failed %s: %s", index, address, account.error)
            return account

    async def _await_verification_link(self, mail: BaseEmailClient, address: str) -> str | None:
        """Poll the mailbox for a message containing a verification link."""
        found = await mail.wait_for_message(address, subject_contains="")
        return found[1] if found else None

    async def run(self, count: int | None = None) -> RunResult:
        """Create ``count`` accounts with bounded concurrency, then import to 9Router."""
        total = count if count is not None else self.cfg.run.count
        result = RunResult(requested=total)
        log.info("harvesting %d account(s) with concurrency=%d", total, self.cfg.run.concurrency)

        sem = asyncio.Semaphore(max(1, self.cfg.run.concurrency))

        async def task(i: int) -> Account:
            async with sem:
                for attempt in range(1, self.cfg.run.retries + 1):
                    account = await self.create_one(i)
                    if account.ok:
                        return account
                    if attempt < self.cfg.run.retries:
                        log.info(
                            "[%d] retry %d/%d in %.0fs",
                            i, attempt, self.cfg.run.retries, self.cfg.run.retry_delay,
                        )
                        await asyncio.sleep(self.cfg.run.retry_delay)
                return account

        accounts = await asyncio.gather(*(task(i) for i in range(1, total + 1)))
        for account in accounts:
            (result.succeeded if account.ok else result.failed).append(account)

        result.finished_at = None
        if result.succeeded and self.cfg.router9.enabled:
            await self._connect_router(result)
        self._persist(result)
        return result

    async def _connect_router(self, result: RunResult) -> None:
        log.info("connecting %d account(s) to 9Router at %s", len(result.succeeded), self.cfg.router9.base_url)
        try:
            async with NineRouterConnector(self.cfg.router9, self.cfg.run.request_timeout) as conn:
                outcome = await conn.import_accounts(result.succeeded)
            log.info(
                "9Router import: %d connected, %d duplicates, %d failed",
                outcome.imported, outcome.duplicate, outcome.failed,
            )
        except (RouterError, Exception) as exc:  # noqa: BLE001
            log.error("9Router import aborted: %s", exc)

    def _persist(self, result: RunResult) -> None:
        payload = result.to_dict()
        (self.results_dir / "accounts.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")

        lines = ["email,password,token,user_id,verified"]
        for account in result.succeeded:
            lines.append(f"{account.email},{account.password},{account.x_token},{account.user_id},{account.verified}")
        (self.results_dir / "accounts.csv").write_text("\n".join(lines) + "\n", encoding="utf-8")

        tokens = "\n".join(a.x_token for a in result.succeeded if a.x_token)
        (self.results_dir / "tokens.txt").write_text(tokens + ("\n" if tokens else ""), encoding="utf-8")
        log.info("wrote results to %s", self.results_dir.resolve())
