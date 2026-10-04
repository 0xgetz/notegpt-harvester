"""Data models for harvested accounts and run results."""

from __future__ import annotations

import time
from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class Account:
    """A created NoteGPT account with its harvested credentials."""

    email: str
    password: str
    user_id: int | None = None
    username: str | None = None
    x_token: str | None = None
    nc_token: str | None = None
    cookies: dict[str, str] = field(default_factory=dict)
    quota: dict[str, Any] = field(default_factory=dict)
    verified: bool = False
    created_at: float = field(default_factory=time.time)
    error: str | None = None

    @property
    def ok(self) -> bool:
        return not self.error and bool(self.x_token)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def openai_api_key(self) -> str:
        """Token 9Router stores as the connection key."""
        return self.x_token or ""

    def cookie_header(self) -> str:
        return "; ".join(f"{k}={v}" for k, v in self.cookies.items())


@dataclass
class RunResult:
    """Aggregate outcome of a bulk run."""

    requested: int
    succeeded: list[Account] = field(default_factory=list)
    failed: list[Account] = field(default_factory=list)
    started_at: float = field(default_factory=time.time)
    finished_at: float | None = None

    @property
    def duration(self) -> float:
        end = self.finished_at or time.time()
        return end - self.started_at

    def to_dict(self) -> dict[str, Any]:
        return {
            "requested": self.requested,
            "succeeded": len(self.succeeded),
            "failed": len(self.failed),
            "duration_seconds": round(self.duration, 2),
            "accounts": [a.to_dict() for a in self.succeeded],
            "errors": [a.to_dict() for a in self.failed],
        }
