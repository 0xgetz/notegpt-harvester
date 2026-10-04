<div align="center">

<img src="assets/banner.png" alt="NoteGPT Harvester" width="820"/>

# NoteGPT Harvester

**Bulk-create NoteGPT accounts, auto-harvest tokens & session cookies, and connect every account straight into [9Router](https://9router.com) — end to end.**

[![License: MIT](https://img.shields.io/badge/License-MIT-22c55e.svg?style=for-the-badge)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-3776AB.svg?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![Platform](https://img.shields.io/badge/Platform-Linux%20%7C%20macOS%20%7C%20Windows-0ea5e9.svg?style=for-the-badge)](#)
[![Async](https://img.shields.io/badge/Concurrency-asyncio-6366f1.svg?style=for-the-badge)](#)
[![httpx](https://img.shields.io/badge/HTTP-httpx-a855f7.svg?style=for-the-badge)](#)
[![OpenAI Compatible](https://img.shields.io/badge/API-OpenAI--compatible-111827.svg?style=for-the-badge)](#)
[![9Router](https://img.shields.io/badge/Connector-9Router-ef4444.svg?style=for-the-badge)](https://9router.com)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg?style=for-the-badge)](#contributing)

[Bahasa Indonesia](README.id.md) · [Español](README.es.md) · [中文](README.zh.md) · [日本語](README.ja.md)

</div>

---

## ✨ What it does

1. **Generate disposable addresses** from a Zenvex-style temp-mail provider.
2. **Register NoteGPT accounts** over the real REST API (`/api/v1/auth/email/register`).
3. **Confirm the email** automatically by polling the inbox and extracting the token.
4. **Log in and harvest credentials** — the `access_token` (the same value the site stores as `X-Token` and the `nc_token` cookie) plus quota.
5. **Connect every account to 9Router** through its management API so all tokens are routable from a single OpenAI-compatible endpoint.

Everything runs with bounded concurrency, retries, a resumable checkpoint and clean JSON/CSV/token outputs.

## 🧭 Flow

```text
 temp mailbox ──▶ register ──▶ confirm (token) ──▶ login ──▶ access_token
      │                                                          │
      └──────────────── verify email ───────────────────┐        ▼
                                                    ┌───┴───────────────┐
                                                    │   9Router API      │
                                                    │ POST /api/providers│
                                                    └────────────────────┘
```

## 🚀 Quick start

```bash
git clone https://github.com/0xgetz/notegpt-harvester.git
cd notegpt-harvester
python -m venv .venv && source .venv/bin/activate    # Windows: .venv\Scripts\activate
pip install -e .
cp config.example.toml config.toml
```

### 1. Start 9Router

```bash
npx 9router
# Dashboard: http://localhost:20128/dashboard
# OpenAI-compatible API: http://localhost:20128/v1
```

### 2. Harvest & connect

```bash
# Create 5 accounts, harvest tokens, push them into 9Router
ngharvest run -n 5 --concurrency 3

# Harvest only (skip 9Router)
ngharvest run -n 3 --no-router

# Point at a remote / authenticated 9Router
ngharvest run -n 10 --router-url http://10.0.0.5:20128 --router-key "$NGH_ROUTER_KEY"
```

### 3. Use the pooled tokens

```bash
curl http://localhost:20128/v1/chat/completions \
  -H "Authorization: Bearer $NGROUTER_KEY" \
  -H "Content-Type: application/json" \
  -d '{"model":"ng/auto","messages":[{"role":"user","content":"hi"}]}'
```

## 🛠️ Commands

| Command | Purpose |
| --- | --- |
| `ngharvest run` | Bulk create accounts, harvest tokens, import into 9Router |
| `ngharvest test-router` | Check 9Router reachability and connection count |
| `ngharvest verify <email> <pass>` | Log in to an existing account and print its token + quota |

Useful flags: `-n/--count`, `-j/--concurrency`, `--proxy`, `--no-router`, `--password`, `--results-dir`, `-v/--verbose`.

## ⚙️ Configuration

Copy `config.example.toml` → `config.toml`. Highlights:

```toml
[email]
provider = "zenvex"        # temp-mail provider
domain   = "souss.dev"     # receiving domain
api_url  = "https://api.zenvex.dev"

[notegpt]
base_url     = "https://notegpt.io"
verify_email = true
password_length = 12

[router9]
enabled        = true
base_url       = "http://localhost:20128"
provider_id    = "notegpt"
openai_base_url = "https://notegpt.io/api/v2/openai/v1"

[run]
count        = 5
concurrency  = 3
retries      = 3
results_dir  = "results"
```

Every field can also be set through environment variables (`NGH_COUNT`, `NGH_CONCURRENCY`, `NGH_ROUTER_URL`, `NGH_ROUTER_API_KEY`, `NGH_PROXY`, …).

## 📂 Output

```text
results/
├── accounts.json   # full records incl. token, quota, cookies, timestamps
├── accounts.csv    # email,password,token,user_id,verified
└── tokens.txt      # one token per line (direct import into routers)
```

## 🔌 How the 9Router connector works

NoteGPT is not a built-in 9Router provider, so the connector:

1. creates a custom **`openai-compatible`** node pointing at the NoteGPT gateway;
2. registers one **API-key connection per account** (`POST /api/providers`) with the harvested `X-Token`;
3. stores `email` and `cookie` in `providerSpecificData` for traceability.

If the management API needs auth, set `router9.api_key`.

## 🔐 Security & ethics

- **Never commit `config.toml`, `results/` or `harvest.state.json`** — they are git-ignored.
- Harvested tokens grant access to the corresponding accounts; treat them like passwords.
- Only use this on services you are permitted to automate. You are responsible for complying with each site's Terms of Service and local law.

## 🧪 Development

```bash
pip install -e ".[dev]"
pytest
ruff check .
```

## 🤝 Contributing

Issues and PRs are welcome. Keep changes focused, run `pytest` and `ruff`, and describe the motivation in the PR.

## 📄 License

[MIT](LICENSE) © 2026 notegpt-harvester contributors.

<div align="center"><sub>Not affiliated with NoteGPT or 9Router. Use responsibly.</sub></div>
