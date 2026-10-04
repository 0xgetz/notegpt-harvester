"""Example: harvest 3 accounts and connect them to 9Router from Python.

Run with:  python examples/harvest.py
Requires a local 9Router on http://localhost:20128 or set NGH_ROUTER_URL.
"""

import asyncio
import json

from notegpt_harvester.config import Config
from notegpt_harvester.harvester import Harvester
from notegpt_harvester.logger import setup_logging


async def main() -> None:
    cfg = Config()
    cfg.run.count = 3
    cfg.run.concurrency = 2
    cfg.run.results_dir = "results"
    cfg.router9.enabled = True
    cfg.router9.base_url = "http://localhost:20128"
    setup_logging("INFO")

    result = await Harvester(cfg).run()
    print(json.dumps(result.to_dict(), indent=2))


if __name__ == "__main__":
    asyncio.run(main())
