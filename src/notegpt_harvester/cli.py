"""Command line interface for the NoteGPT harvester."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from typing import Any

from . import __version__
from .config import Config, NoteGPTConfig
from .harvester import Harvester
from .logger import setup_logging
from .notegpt import NoteGPTClient
from .router9 import NineRouterConnector


def _add_common(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("-c", "--config", help="path to TOML config file")
    parser.add_argument("--router-url", help="9Router base URL (default http://localhost:20128)")
    parser.add_argument("--router-key", help="9Router management API key, if required")
    parser.add_argument("--no-router", action="store_true", help="harvest only; do not connect to 9Router")
    parser.add_argument("--proxy", help="HTTP/SOCKS proxy URL for outbound requests")
    parser.add_argument("--log-level", default=None, help="DEBUG|INFO|WARNING|ERROR")
    parser.add_argument("-v", "--verbose", action="store_true", help="shortcut for --log-level DEBUG")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ngharvest",
        description="Bulk-create NoteGPT accounts, harvest tokens/cookies and connect them to 9Router.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = parser.add_subparsers(dest="command")

    run = sub.add_parser("run", help="harvest N accounts and import them into 9Router")
    run.add_argument("-n", "--count", type=int, default=None, help="number of accounts to create")
    run.add_argument("-j", "--concurrency", type=int, default=None, help="parallel workers")
    run.add_argument("--email-domain", help="temporary email domain (default souss.dev)")
    run.add_argument("--email-api", help="temporary email provider API base URL")
    run.add_argument("--password", help="fixed password; random when omitted")
    run.add_argument("--results-dir", help="where to write accounts.json/csv/tokens.txt")
    _add_common(run)

    test = sub.add_parser("test-router", help="check 9Router connectivity and list connections")
    _add_common(test)

    verify = sub.add_parser("verify", help="log in to an existing account and print its token/quota")
    verify.add_argument("email")
    verify.add_argument("password")
    _add_common(verify)

    return parser


def _load(args: argparse.Namespace) -> Config:
    cfg = Config.load(args.config)
    if getattr(args, "router_url", None):
        cfg.router9.base_url = args.router_url
    if getattr(args, "router_key", None):
        cfg.router9.api_key = args.router_key
    if getattr(args, "no_router", False):
        cfg.router9.enabled = False
    if getattr(args, "proxy", None):
        cfg.run.proxy = args.proxy
    if getattr(args, "verbose", False):
        cfg.run.log_level = "DEBUG"
    if getattr(args, "log_level", None):
        cfg.run.log_level = args.log_level
    return cfg


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if not args.command:
        build_parser().print_help()
        return 1

    cfg = _load(args)
    if getattr(args, "count", None) is not None:
        cfg.run.count = args.count
    if getattr(args, "concurrency", None) is not None:
        cfg.run.concurrency = args.concurrency
    if getattr(args, "email_domain", None):
        cfg.email.domain = args.email_domain
    if getattr(args, "email_api", None):
        cfg.email.api_url = args.email_api
    if getattr(args, "password", None):
        cfg.notegpt.password = args.password
    if getattr(args, "results_dir", None):
        cfg.run.results_dir = args.results_dir

    setup_logging(cfg.run.log_level)

    try:
        return asyncio.run(_dispatch(args, cfg))
    except KeyboardInterrupt:
        print("\ninterrupted", file=sys.stderr)
        return 130


async def _dispatch(args: argparse.Namespace, cfg: Config) -> int:
    if args.command == "run":
        result = await Harvester(cfg).run()
        summary = result.to_dict()
        print(json.dumps({k: summary[k] for k in ("requested", "succeeded", "failed", "duration_seconds")}, indent=2))
        return 0 if not result.failed else 2

    if args.command == "test-router":
        async with NineRouterConnector(cfg.router9, cfg.run.request_timeout) as conn:
            if not await conn.ping():
                print(f"9Router not reachable at {cfg.router9.base_url}", file=sys.stderr)
                return 1
            providers = await conn.list_providers()
            print(json.dumps({"reachable": True, "connections": len(providers)}, indent=2))
            return 0

    if args.command == "verify":
        ng_cfg = NoteGPTConfig(base_url=cfg.notegpt.base_url)
        async with NoteGPTClient(ng_cfg, cfg.run) as ng:
            data = await ng.login(args.email, args.password)
            token = data.get("access_token", "")
            quota: dict[str, Any] = {}
            if token:
                quota = await ng.quota(token)
            print(json.dumps({"email": args.email, "token": token, "quota": quota}, indent=2))
            return 0

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
