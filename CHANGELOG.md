# Changelog

## 1.0.0

- Bulk NoteGPT account creation over the verified REST auth flow
  (`/api/v1/auth/email/register`, `/register/confirm`, `/login`).
- Automatic email verification via pluggable temp-mail providers
  (`mail.tm` default, `zenvex` optional).
- Token & session-cookie harvest (`X-Token` / `nc_token`) plus quota.
- 9Router connector: custom `openai-compatible` node + one connection per account.
- Bounded concurrency, retries, resumable checkpoint, JSON/CSV/tokens outputs.
- CLI (`ngharvest`) with `run`, `test-router`, `verify`.
- Local mock-server end-to-end tests.
