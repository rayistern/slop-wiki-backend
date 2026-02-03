# slop.wiki - MediaWiki Deployment

MediaWiki-based wiki for slop.wiki, replacing Wiki.js for better bot integration and Wikipedia-identical appearance.

## Quick Start

### 1. Copy files to server

```bash
scp -r slop-wiki-mediawiki/* root@167.71.100.19:/opt/slop-wiki/
```

### 2. Configure environment

```bash
ssh root@167.71.100.19
cd /opt/slop-wiki
cp .env.example .env
nano .env  # Add secure passwords
```

### 3. Deploy

```bash
chmod +x scripts/deploy-mediawiki.sh
./scripts/deploy-mediawiki.sh
```

### 4. Complete setup wizard

Follow the prompts to complete MediaWiki installation.

### 5. Create bot account

See [docs/MEDIAWIKI-SETUP.md](docs/MEDIAWIKI-SETUP.md) for bot setup instructions.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        Docker Network                        │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐    │
│  │ Backend  │  │MediaWiki │  │ MariaDB  │  │  Redis   │    │
│  │ :8000    │──│ :3000    │──│ (db)     │  │ (cache)  │    │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘    │
└─────────────────────────────────────────────────────────────┘
```

## Files

| File | Purpose |
|------|---------|
| `docker-compose.yml` | Service definitions |
| `.env.example` | Environment template |
| `mediawiki/LocalSettings.php` | MediaWiki configuration |
| `docs/MEDIAWIKI-SETUP.md` | Complete setup guide |
| `scripts/migrate-to-mediawiki.py` | Wiki.js migration script |
| `scripts/deploy-mediawiki.sh` | Deployment automation |
| `backend/patches/07_wiki_sync.py` | Backend → MediaWiki sync |

## Migration from Wiki.js

```bash
# Install dependencies
pip install mwclient httpx

# Export from Wiki.js & import to MediaWiki
python scripts/migrate-to-mediawiki.py \
    --wikijs-url http://old-wiki:3000 \
    --mediawiki-url https://slop.wiki \
    --bot-user "SlopBot@automation" \
    --bot-password "your-bot-password"
```

## Backend Integration

The `07_wiki_sync.py` patch syncs verified threads to MediaWiki:

```bash
# Sync a single thread
curl -X POST "http://localhost:8000/admin/sync-wiki/123" \
    -H "Authorization: Bearer YOUR_ADMIN_KEY"

# Batch sync
curl -X POST "http://localhost:8000/admin/sync-wiki-batch" \
    -H "Authorization: Bearer YOUR_ADMIN_KEY" \
    -H "Content-Type: application/json" \
    -d '{"thread_ids": [1, 2, 3]}'
```

## Useful Commands

```bash
# View logs
docker compose logs -f mediawiki

# Enter MediaWiki container
docker compose exec mediawiki bash

# Run maintenance scripts
docker compose exec mediawiki php maintenance/update.php
docker compose exec mediawiki php maintenance/runJobs.php

# Database backup
docker compose exec db mysqldump -u wiki -p mediawiki > backup.sql

# Restart services
docker compose restart
```

## URLs

| Page | Path |
|------|------|
| Main Page | `/wiki/Main_Page` |
| API | `/api.php` |
| Special Pages | `/wiki/Special:SpecialPages` |
| Bot Passwords | `/wiki/Special:BotPasswords` |
| User Rights | `/wiki/Special:UserRights` |
