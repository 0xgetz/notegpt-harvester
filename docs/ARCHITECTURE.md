# Architecture

```
notegpt_harvester/
├── config.py          # TOML + NGH_* env config loader
├── logger.py          # colored structured logging
├── models.py          # Account / RunResult dataclasses
├── email_provider.py  # temp-mail clients (mail.tm, zenvex) + link extraction
├── notegpt.py         # NoteGPT auth API client (register/confirm/login/harvest)
├── router9.py         # 9Router management API connector
├── harvester.py       # orchestration, checkpointing, persistence
└── cli.py             # `ngharvest` entrypoint
```

## Data flow

```
                create_address()
 temp-mail ──────────────────────────────▶ address
     ▲                                      │
     │ wait_for_message()        register() │
     │                                      ▼
 verify link ◀─────────── verification email ── NoteGPT
     │  token_from_link()                    ▲
     ▼                                      │ login()
 confirm(token)  ───────────────────────────┘
     │
     ▼
 access_token ──▶ Account(x_token, nc_token, quota)
     │
     ▼
 NineRouterConnector.import_accounts()
     ├─ ensure_node()          POST /api/provider-nodes
     └─ add_account()          POST /api/providers
```

## Concurrency & reliability

- **Bounded concurrency** via `asyncio.Semaphore` (`run.concurrency`).
- **Retries** per account with a configurable delay (`run.retries`, `run.retry_delay`).
- **Resumable checkpoint** (`harvest.state.json`) records successful emails so an
  interrupted run can be inspected/skipped.
- **Fail-soft 9Router import**: a single bad connection never aborts the batch.

## Provider abstraction

`TempEmailClient.create(cfg)` returns a `BaseEmailClient`:

| Provider | Scriptable | Notes |
| --- | --- | --- |
| `mailtm` | ✅ | Public REST API, recommended default. |
| `zenvex` | ⚠️ | Cloudflare-guarded; pass browser cookies via `extra_headers`. |

Adding a provider = subclass `BaseEmailClient` and register it in the factory.

## 9Router integration

NoteGPT is connected as a custom **`openai-compatible`** node. Each harvested
`access_token` becomes an API-key connection, so 9Router pools all accounts and
exposes them through one OpenAI-compatible endpoint (`http://localhost:20128/v1`).
