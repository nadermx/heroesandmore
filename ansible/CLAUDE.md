# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

Ansible deployment automation for HeroesAndMore (Django collectibles marketplace). Manages a single DigitalOcean droplet running Nginx, Gunicorn, Celery, PostgreSQL, Redis, and Postfix.

## Server

- **Host**: `174.138.33.140` (DigitalOcean droplet)
- **SSH user**: `heroesandmore` (passwordless sudo)
- **App user**: `www` (owns app files, runs services)
- **App path**: `/home/www/heroesandmore`
- **Inventory**: `servers` file

## Ansible Binary

Ansible is installed in the project virtualenv, not system-wide:
```bash
/home/john/heroesandmore/venv/bin/ansible-playbook -i servers <playbook>
/home/john/heroesandmore/venv/bin/ansible -i servers all -m shell -a "command" --become
```

## Playbooks

| Playbook | Purpose | Usage |
|----------|---------|-------|
| `gitpull.yml` | Quick deploy: pull code, install deps, migrate, collectstatic, restart | Most common — use for code-only changes |
| `deploy.yml` | Full deploy: includes config.py template from vault | Use when config.py.j2 or vault.yml changed |
| `backup.yml` | Backup PostgreSQL, config.py, and media to `/home/www/backups/` | Auto-cleans backups older than 7 days |
| `setup.yml` | Initial server provisioning (packages, DB, venv, nginx, supervisor) | One-time use on new servers |
| `security.yml` | Security hardening (deploy user, UFW firewall, fail2ban, SSH lockdown) | One-time use on new servers |
| `email_setup.yml` | Postfix + OpenDKIM setup for transactional email | One-time use; outputs DKIM DNS record |

## Quick Reference

```bash
# Deploy code changes (most common)
/home/john/heroesandmore/venv/bin/ansible-playbook -i servers gitpull.yml

# Full deploy with config update
/home/john/heroesandmore/venv/bin/ansible-playbook -i servers deploy.yml

# Run shell command on server as root
/home/john/heroesandmore/venv/bin/ansible -i servers all -m shell -a "command" --become

# Run shell command as www user
/home/john/heroesandmore/venv/bin/ansible -i servers all -m shell -a "command" --become --become-user=www

# Restart services
/home/john/heroesandmore/venv/bin/ansible -i servers all -m shell -a "supervisorctl restart heroesandmore:*" --become

# Copy a file to server
/home/john/heroesandmore/venv/bin/ansible -i servers all -m copy -a "src=files/file dest=/path/on/server" --become
```

## Debug Script

`debug.sh` provides quick SSH-based log access:
```bash
./debug.sh errors       # Last 50 error log entries
./debug.sh stripe       # Stripe/payment logs
./debug.sh celery       # Celery task logs
./debug.sh all          # Quick overview of all logs
./debug.sh tail errors  # Live tail
./debug.sh grep "pattern"  # Search all logs
./debug.sh status       # Service status
./debug.sh restart      # Restart all services
./debug.sh deploy       # Quick deploy (wraps gitpull.yml)
```

## Config & Secrets

### Config Flow
`group_vars/vault.yml` (secrets) + `group_vars/all` (public vars) -> `templates/config.py.j2` -> server's `config.py`

### Files
- **`group_vars/all`** — Public variables (paths, domain, DB name, variable mappings from vault)
- **`group_vars/vault.yml`** — Secrets (DB password, Stripe keys, OAuth secrets, TikTok token). Gitignored.
- **`group_vars/vault.yml.example`** — Template for creating vault.yml
- **`templates/config.py.j2`** — Jinja2 template for Django's config.py

### Adding New Config Values
1. Add `vault_<name>` to `group_vars/vault.yml` with the secret value
2. Add mapping in `group_vars/all`: `<name>: "{{ vault_<name> | default('') }}"`
3. Add `<NAME> = '{{ <name> }}'` to `templates/config.py.j2`
4. Add `<NAME> = getattr(config, '<NAME>', None)` in Django's `app/settings.py`
5. Run `deploy.yml` to push the new config, or manually append to server's config.py and use `gitpull.yml`

### Editing Server Config Directly
For quick config changes without a full deploy (e.g., adding a new API key):
```bash
/home/john/heroesandmore/venv/bin/ansible -i servers all -m shell \
  -a "echo \"NEW_KEY = 'value'\" >> /home/www/heroesandmore/config.py" --become --become-user=www
```
Then restart services. Remember to also update vault.yml so `deploy.yml` won't overwrite it.

## Service Architecture

Three supervisor-managed processes (group: `heroesandmore`):
- **heroesandmore_web** — Gunicorn (3 workers, unix socket at `/tmp/heroesandmore.sock`)
- **heroesandmore_celery** — Celery worker (concurrency=2)
- **heroesandmore_celerybeat** — Celery beat scheduler (file-based, schedules defined in `app/celery.py`)

Config file: `files/heroesandmore.supervisor.conf`

### Updating Supervisor Config
```bash
/home/john/heroesandmore/venv/bin/ansible -i servers all -m copy \
  -a "src=files/heroesandmore.supervisor.conf dest=/etc/supervisor/conf.d/heroesandmore.conf" --become
/home/john/heroesandmore/venv/bin/ansible -i servers all -m shell \
  -a "supervisorctl reread && supervisorctl update && supervisorctl restart heroesandmore:*" --become
```

## Log Locations

| Path | Contents |
|------|----------|
| `/home/www/heroesandmore/logs/` | Django app logs (errors.log, stripe.log, app.log, celery_tasks.log, security.log, api.log, frontend.log, db.log) |
| `/var/log/heroesandmore/` | Supervisor stdout/stderr (heroesandmore.out.log, heroesandmore.err.log, celery.out.log, celery.err.log, celerybeat.out.log, celerybeat.err.log) |

## Email

Self-hosted via Postfix + OpenDKIM (configured by `email_setup.yml`):
- **Sending domain**: `mail.heroesandmore.com` (DKIM-signed)
- **Receiving domain**: `heroesandmore.com` (forwards via `/etc/postfix/virtual`)
- Port 25 open in UFW for inbound mail
- `SRS_EXCLUDE_DOMAINS=mail.heroesandmore.com,heroesandmore.com` must be in `/etc/default/postsrsd` to prevent SPF/DKIM breakage

## Gotchas

- **`gitpull.yml` force-pulls** — it uses `force: yes` on `git`, so any manual server-side edits to tracked files will be overwritten
- **`deploy.yml` overwrites config.py** — any values added directly to server config.py will be lost unless also in vault.yml + config.py.j2
- **Celery Beat uses file-based scheduler** — do NOT add `--scheduler django_celery_beat.schedulers:DatabaseScheduler` to supervisor config; all schedules are in `app/celery.py`'s `beat_schedule` dict
- **Server config.py ownership** — must be `www:www-data` with mode `0640`; use `--become-user=www` when editing
- **Nginx uses unix socket** — Gunicorn binds to `/tmp/heroesandmore.sock`, not a TCP port
