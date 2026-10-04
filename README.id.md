<div align="center">

<img src="assets/banner.png" alt="NoteGPT Harvester" width="820"/>

# NoteGPT Harvester

**Buat akun NoteGPT secara massal, panen token & cookie sesi secara otomatis, lalu hubungkan setiap akun langsung ke [9Router](https://9router.com) — end to end.**

[![License: MIT](https://img.shields.io/badge/License-MIT-22c55e.svg?style=for-the-badge)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-3776AB.svg?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![Platform](https://img.shields.io/badge/Platform-Linux%20%7C%20macOS%20%7C%20Windows-0ea5e9.svg?style=for-the-badge)](#)
[![Async](https://img.shields.io/badge/Concurrency-asyncio-6366f1.svg?style=for-the-badge)](#)
[![httpx](https://img.shields.io/badge/HTTP-httpx-a855f7.svg?style=for-the-badge)](#)
[![9Router](https://img.shields.io/badge/Connector-9Router-ef4444.svg?style=for-the-badge)](https://9router.com)

[English](README.md) · [Español](README.es.md) · [中文](README.zh.md) · [日本語](README.ja.md)

</div>

---

## ✨ Apa yang dilakukan

1. **Membuat alamat email sementara** dari provider temp-mail gaya Zenvex.
2. **Mendaftarkan akun NoteGPT** lewat REST API asli (`/api/v1/auth/email/register`).
3. **Verifikasi email otomatis** dengan polling inbox dan mengambil token.
4. **Login & panen kredensial** — `access_token` (nilai yang sama disimpan situs sebagai `X-Token` dan cookie `nc_token`) beserta kuota.
5. **Menghubungkan setiap akun ke 9Router** lewat management API agar semua token bisa dirutekan dari satu endpoint yang kompatibel OpenAI.

Semua berjalan dengan konkurensi terbatas, retry, checkpoint yang bisa dilanjutkan, serta output JSON/CSV/token yang rapi.

## 🚀 Mulai cepat

```bash
git clone https://github.com/octra42/notegpt-harvester.git
cd notegpt-harvester
python -m venv .venv && source .venv/bin/activate
pip install -e .
cp config.example.toml config.toml
```

```bash
npx 9router                              # jalankan 9Router (port 20128)
ngharvest run -n 5 --concurrency 3       # buat 5 akun + hubungkan ke 9Router
ngharvest run -n 3 --no-router           # hanya panen, tanpa 9Router
```

## 🛠️ Perintah

| Perintah | Fungsi |
| --- | --- |
| `ngharvest run` | Buat massal, panen token, impor ke 9Router |
| `ngharvest test-router` | Cek konektivitas 9Router & jumlah koneksi |
| `ngharvest verify <email> <pass>` | Login akun lama, cetak token + kuota |

Flag: `-n/--count`, `-j/--concurrency`, `--proxy`, `--no-router`, `--password`, `--results-dir`, `-v/--verbose`.

## 📂 Output

```text
results/
├── accounts.json   # data lengkap: token, kuota, cookie, waktu
├── accounts.csv    # email,password,token,user_id,verified
└── tokens.txt      # satu token per baris
```

## ⚙️ Konfigurasi

Salin `config.example.toml` → `config.toml`. Semua field juga dapat diatur lewat variabel lingkungan `NGH_*` (`NGH_COUNT`, `NGH_ROUTER_URL`, `NGH_ROUTER_API_KEY`, `NGH_PROXY`, …).

## 🔐 Keamanan & etika

- **Jangan pernah commit `config.toml`, `results/`, atau `harvest.state.json`** (sudah di-gitignore).
- Token hasil panen memberi akses ke akun terkait — perlakukan seperti kata sandi.
- Gunakan hanya pada layanan yang boleh Anda otomatiskan, dan patuhi ToS serta hukum setempat.

## 📄 Lisensi

[MIT](LICENSE) © 2026 notegpt-harvester contributors.

<div align="center"><sub>Tidak berafiliasi dengan NoteGPT atau 9Router. Gunakan dengan bijak.</sub></div>
