"""Typed configuration loading (TOML) with environment overrides."""

from __future__ import annotations

import os
from dataclasses import dataclass, field, fields
from pathlib import Path
from typing import Any

import tomllib


@dataclass
class EmailConfig:
    """Temporary email provider settings.

    ``provider`` selects the backend: ``mailtm`` (default, fully scriptable) or
    ``zenvex`` (browser-session required).

    ``domain`` is optional. For ``mailtm`` it overrides the auto-selected active
    domain when available; for ``zenvex`` it is the receiving domain.
    """

    provider: str = "mailtm"
    domain: str = ""
    base_url: str = "https://zenvex.dev"
    api_url: str = "https://api.mail.tm"
    prefix: str = "ng"
    poll_interval: float = 3.0
    poll_timeout: float = 150.0


@dataclass
class NoteGPTConfig:
    """Target site endpoints and registration settings."""

    base_url: str = "https://notegpt.io"
    signup_path: str = "/api/v2/auth/register"
    login_path: str = "/api/v2/auth/login"
    userinfo_path: str = "/api/v1/userinfo"
    quota_path: str = "/api/v2/user/quota?features=ai_chat"
    models_path: str = "/api/v2/ai-chat"
    password: str = ""  # generated when empty
    password_length: int = 12
    verify_email: bool = True


@dataclass
class NineRouterConfig:
    """9Router management API connection + provider import settings."""

    enabled: bool = True
    base_url: str = "http://localhost:20128"
    api_key: str = ""
    provider_id: str = "notegpt"
    provider_name: str = "NoteGPT"
    openai_base_url: str = "https://notegpt.io/api/v2/openai/v1"
    node_type: str = "openai-compatible"
    create_node: bool = True
    prefix: str = "ng"


@dataclass
class RunConfig:
    """Bulk-run orchestration settings."""

    count: int = 1
    concurrency: int = 3
    retries: int = 3
    retry_delay: float = 5.0
    proxy: str = ""
    checkpoint_file: str = "harvest.state.json"
    results_dir: str = "results"
    log_level: str = "INFO"
    request_timeout: float = 30.0
    user_agent: str = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/131.0 Safari/537.36"
    )


@dataclass
class Config:
    """Root configuration aggregate."""

    email: EmailConfig = field(default_factory=EmailConfig)
    notegpt: NoteGPTConfig = field(default_factory=NoteGPTConfig)
    router9: NineRouterConfig = field(default_factory=NineRouterConfig)
    run: RunConfig = field(default_factory=RunConfig)

    @classmethod
    def load(cls, path: str | Path | None = None) -> Config:
        """Load config from TOML, then apply ``NGH_*`` environment overrides."""
        raw: dict[str, Any] = {}
        if path:
            p = Path(path)
            if not p.exists():
                raise FileNotFoundError(f"config file not found: {p}")
            raw = tomllib.loads(p.read_text(encoding="utf-8"))

        cfg = cls(
            email=_build(EmailConfig, raw.get("email", {})),
            notegpt=_build(NoteGPTConfig, raw.get("notegpt", {})),
            router9=_build(NineRouterConfig, raw.get("router9", {})),
            run=_build(RunConfig, raw.get("run", {})),
        )
        _apply_env(cfg)
        return cfg


def _build(dc: type, data: dict[str, Any]):
    valid = {f.name: f for f in fields(dc)}
    kwargs: dict[str, Any] = {}
    for key, value in data.items():
        key = key.replace("-", "_")
        if key in valid:
            kwargs[key] = _coerce(value, valid[key].type)
    return dc(**kwargs)


def _coerce(value: Any, target: Any) -> Any:
    try:
        name = target.__name__
    except AttributeError:
        name = str(target)
    if name == "bool" and not isinstance(value, bool):
        return str(value).strip().lower() in ("1", "true", "yes", "on")
    if name == "int" and not isinstance(value, int):
        return int(value)
    if name == "float" and not isinstance(value, float):
        return float(value)
    return value


_ENV_MAP = {
    "NGH_EMAIL_PROVIDER": ("email", "provider"),
    "NGH_EMAIL_DOMAIN": ("email", "domain"),
    "NGH_EMAIL_API_URL": ("email", "api_url"),
    "NGH_NOTEGPT_BASE_URL": ("notegpt", "base_url"),
    "NGH_NOTEGPT_PASSWORD": ("notegpt", "password"),
    "NGH_ROUTER_URL": ("router9", "base_url"),
    "NGH_ROUTER_API_KEY": ("router9", "api_key"),
    "NGH_ROUTER_ENABLED": ("router9", "enabled"),
    "NGH_COUNT": ("run", "count"),
    "NGH_CONCURRENCY": ("run", "concurrency"),
    "NGH_PROXY": ("run", "proxy"),
    "NGH_RETRIES": ("run", "retries"),
    "NGH_LOG_LEVEL": ("run", "log_level"),
    "NGH_RESULTS_DIR": ("run", "results_dir"),
}


def _apply_env(cfg: Config) -> None:
    for env_key, (section, attr) in _ENV_MAP.items():
        if env_key in os.environ:
            target = getattr(cfg, section)
            setattr(target, attr, _coerce(os.environ[env_key], type(getattr(target, attr))))
