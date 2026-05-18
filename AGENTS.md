# AGENTS.md

## Project overview

Python 3.12 monolith: Django 4.2 web app + aiogram 3.4 Telegram bot, managing VPN
subscriptions via Remnawave API.

## Entrypoints

- **Django** — `python gamma/manage.py <command>`
- **Telegram bot** — `python bot.py` (imports `gamma/` via sys.path, calls `django.setup()`)

## Setup

```bash
pip install -r requirements/test.txt
python gamma/manage.py migrate
python gamma/manage.py init_superuser
```

`.env` at repo root is required.  Supports SQLite (default debug) or PostgreSQL.

## Commands

| Action | Command |
|---|---|
| Run dev server | `python gamma/manage.py runserver` |
| Run bot | `python bot.py` |
| Run all tests | `python gamma/manage.py test` |
| Run single app tests | `python gamma/manage.py test connect` (apps: `connect`, `shop`, `user`, `settings`) |
| Run single test | `python gamma/manage.py test user.tests.TestClass.test_method` |
| Format | `black gamma/ bot.py` (line-length 79) |
| Lint | `flake8 gamma/ bot.py` |
| Migrate | `python gamma/manage.py migrate` |
| Collect static | `python gamma/manage.py collectstatic` |

## Django apps

```
gamma/connect/   — proxy management, node status, Remnawave API service
gamma/shop/      — tariffs, orders, payments
gamma/user/      — profiles, Telegram OAuth login
gamma/settings/  — placeholder (empty)
```

## Important details

- **No type checker** configured — do not add type annotations beyond what Django requires.
- **No CI, no pre-commit, no Docker** — manual workflows only.
- **Admin URL** is custom (set via `ADMIN_URL` in `.env`), not `/admin/`.
- **All test files are currently empty stubs** — new tests use `django.test.TestCase`.
- **Test deps** include Flake8 + 15 plugins; formatter is Black only.
- **`.env` contains live secrets** — never commit or expose it.
