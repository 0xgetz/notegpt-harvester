<div align="center">

<img src="assets/banner.png" alt="NoteGPT Harvester" width="820"/>

# NoteGPT Harvester

**批量创建 NoteGPT 账号，自动采集 Token 与会话 Cookie，并将每个账号直接接入 [9Router](https://9router.com) —— 端到端全流程。**

[![License: MIT](https://img.shields.io/badge/License-MIT-22c55e.svg?style=for-the-badge)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-3776AB.svg?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![Platform](https://img.shields.io/badge/Platform-Linux%20%7C%20macOS%20%7C%20Windows-0ea5e9.svg?style=for-the-badge)](#)
[![Async](https://img.shields.io/badge/Concurrency-asyncio-6366f1.svg?style=for-the-badge)](#)
[![9Router](https://img.shields.io/badge/Connector-9Router-ef4444.svg?style=for-the-badge)](https://9router.com)

[English](README.md) · [Bahasa Indonesia](README.id.md) · [Español](README.es.md) · [日本語](README.ja.md)

</div>

---

## ✨ 功能

1. **生成临时邮箱地址**（兼容 Zenvex 风格）。
2. **通过真实 REST API 注册 NoteGPT 账号**（`/api/v1/auth/email/register`）。
3. **自动完成邮箱验证**：轮询收件箱并提取验证 token。
4. **登录并采集凭证** —— `access_token`（即站点保存于 `X-Token` 与 `nc_token` Cookie 的同一值）及额度信息。
5. **将每个账号接入 9Router**：通过其管理 API，使所有 Token 可从单一 OpenAI 兼容端点路由。

全程支持有限并发、重试、可续跑检查点，并输出整洁的 JSON/CSV/Token 文件。

## 🚀 快速开始

```bash
git clone https://github.com/octra42/notegpt-harvester.git
cd notegpt-harvester
python -m venv .venv && source .venv/bin/activate
pip install -e .
cp config.example.toml config.toml
```

```bash
npx 9router                              # 启动 9Router（端口 20128）
ngharvest run -n 5 --concurrency 3       # 创建 5 个账号并接入
ngharvest run -n 3 --no-router           # 仅采集，不接入 9Router
```

## 🛠️ 命令

| 命令 | 用途 |
| --- | --- |
| `ngharvest run` | 批量创建、采集 Token、导入 9Router |
| `ngharvest test-router` | 检测 9Router 连通性与连接数 |
| `ngharvest verify <email> <pass>` | 登录既有账号并输出 Token 与额度 |

常用参数：`-n/--count`、`-j/--concurrency`、`--proxy`、`--no-router`、`--password`、`--results-dir`、`-v/--verbose`。

## 📂 输出

```text
results/
├── accounts.json   # 完整记录：Token、额度、Cookie、时间
├── accounts.csv    # email,password,token,user_id,verified
└── tokens.txt      # 每行一个 Token
```

## ⚙️ 配置

复制 `config.example.toml` → `config.toml`。所有字段均可通过 `NGH_*` 环境变量覆盖（`NGH_COUNT`、`NGH_ROUTER_URL`、`NGH_ROUTER_API_KEY`、`NGH_PROXY` 等）。

## 🔐 安全与合规

- **切勿提交 `config.toml`、`results/` 或 `harvest.state.json`**（已在 .gitignore 中）。
- 采集到的 Token 可访问对应账号，请视同密码妥善保管。
- 仅在你被允许自动化的服务上使用，并遵守其服务条款与当地法律。

## 📄 许可证

[MIT](LICENSE) © 2026 notegpt-harvester contributors。

<div align="center"><sub>本项目与 NoteGPT、9Router 无隶属关系，请负责任地使用。</sub></div>
