<div align="center">

<img src="assets/banner.png" alt="NoteGPT Harvester" width="820"/>

# NoteGPT Harvester

**NoteGPT アカウントを一括作成し、トークンとセッション Cookie を自動収集、各アカウントを [9Router](https://9router.com) に直接接続 — エンドツーエンド。**

[![License: MIT](https://img.shields.io/badge/License-MIT-22c55e.svg?style=for-the-badge)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-3776AB.svg?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![Platform](https://img.shields.io/badge/Platform-Linux%20%7C%20macOS%20%7C%20Windows-0ea5e9.svg?style=for-the-badge)](#)
[![Async](https://img.shields.io/badge/Concurrency-asyncio-6366f1.svg?style=for-the-badge)](#)
[![9Router](https://img.shields.io/badge/Connector-9Router-ef4444.svg?style=for-the-badge)](https://9router.com)

[English](README.md) · [Bahasa Indonesia](README.id.md) · [Español](README.es.md) · [中文](README.zh.md)

</div>

---

## ✨ できること

1. **使い捨てメールアドレスを生成**（Zenvex 互換プロバイダ）。
2. **実際の REST API で NoteGPT アカウントを登録**（`/api/v1/auth/email/register`）。
3. **メール確認を自動化**：受信箱をポーリングしてトークンを抽出。
4. **ログインして資格情報を収集** — `access_token`（サイトが `X-Token` と `nc_token` Cookie に保存するのと同じ値）とクォータ。
5. **各アカウントを 9Router に接続**：管理 API 経由で、全トークンを単一の OpenAI 互換エンドポイントからルーティング可能に。

並行数制限・リトライ・再開可能なチェックポイントに対応し、JSON/CSV/トークン出力を生成します。

## 🚀 クイックスタート

```bash
git clone https://github.com/octra42/notegpt-harvester.git
cd notegpt-harvester
python -m venv .venv && source .venv/bin/activate
pip install -e .
cp config.example.toml config.toml
```

```bash
npx 9router                              # 9Router を起動（ポート 20128）
ngharvest run -n 5 --concurrency 3       # 5 アカウント作成して接続
ngharvest run -n 3 --no-router           # 収集のみ（9Router なし）
```

## 🛠️ コマンド

| コマンド | 用途 |
| --- | --- |
| `ngharvest run` | 一括作成・トークン収集・9Router へインポート |
| `ngharvest test-router` | 9Router の接続確認と接続数表示 |
| `ngharvest verify <email> <pass>` | 既存アカウントにログインしトークンとクォータを表示 |

主なフラグ：`-n/--count`、`-j/--concurrency`、`--proxy`、`--no-router`、`--password`、`--results-dir`、`-v/--verbose`。

## 📂 出力

```text
results/
├── accounts.json   # 完全な記録：トークン、クォータ、Cookie、時刻
├── accounts.csv    # email,password,token,user_id,verified
└── tokens.txt      # 1 行 1 トークン
```

## ⚙️ 設定

`config.example.toml` を `config.toml` にコピー。全項目は環境変数 `NGH_*`（`NGH_COUNT`、`NGH_ROUTER_URL`、`NGH_ROUTER_API_KEY`、`NGH_PROXY` など）でも設定可能です。

## 🔐 セキュリティと倫理

- **`config.toml`・`results/`・`harvest.state.json` は絶対にコミットしない**（.gitignore 済み）。
- 収集したトークンは該当アカウントへのアクセス権を持ちます。パスワード同様に扱ってください。
- 自動化が許可されたサービスにのみ使用し、各サイトの利用規約と現地法を遵守してください。

## 📄 ライセンス

[MIT](LICENSE) © 2026 notegpt-harvester contributors。

<div align="center"><sub>NoteGPT・9Router とは無関係です。責任を持って使用してください。</sub></div>
