# MediaWiki Setup Guide for slop.wiki

## Overview

This guide covers setting up MediaWiki to replace Wiki.js on slop.wiki. MediaWiki provides superior bot integration, Wikipedia-identical appearance, and a mature API.

**Server:** 167.71.100.19  
**Port:** 3000 (mapped from container port 80)  
**URL:** https://slop.wiki

---

## 1. Prerequisites

Ensure the server has:
- Docker & Docker Compose installed
- At least 2GB RAM
- 10GB+ free disk space

## 2. Initial Deployment

### 2.1 Clone/Copy Files

```bash
# On the server
cd /opt/slop-wiki  # or your deployment directory

# Copy the new docker-compose.yml and mediawiki/ directory
```

### 2.2 Create Environment File

```bash
cp .env.example .env
nano .env
```

Generate secure passwords:
```bash
# Generate database passwords
openssl rand -hex 16  # MYSQL_PASSWORD
openssl rand -hex 16  # MYSQL_ROOT_PASSWORD
```

### 2.3 First-Time Database & Container Startup

```bash
# Start only the database first
docker compose up -d db

# Wait for it to be healthy
docker compose ps

# Start MediaWiki (without LocalSettings.php mounted initially)
docker compose up -d mediawiki
```

### 2.4 Run Installation Wizard

1. Open browser: `http://167.71.100.19:3000/mw-config/`
2. Follow the installation wizard:
   - **Language:** English
   - **Database:** MySQL/MariaDB
   - **Database host:** `db`
   - **Database name:** `mediawiki`
   - **Database user:** `wiki`
   - **Database password:** (from .env MYSQL_PASSWORD)
   - **Wiki name:** slop.wiki
   - **Admin username:** Choose one (e.g., `SlopAdmin`)
   - **Admin password:** Generate secure password

3. Complete wizard - it will generate `LocalSettings.php`

### 2.5 Configure LocalSettings.php

1. Download the generated `LocalSettings.php`
2. Merge with our template at `mediawiki/LocalSettings.php`:
   - Copy the `$wgSecretKey` and `$wgUpgradeKey` values
   - Keep our custom configuration (Redis, permissions, namespaces)

3. Upload the final `LocalSettings.php` to the server

### 2.6 Restart with Full Configuration

```bash
docker compose down
docker compose up -d
```

### 2.7 Verify Installation

```bash
# Test API
curl "http://localhost:3000/api.php?action=query&meta=siteinfo&format=json"

# Should return wiki info JSON
```

---

## 3. Admin Account Setup

### 3.1 Create Main Admin Account

The admin account was created during installation. Login at:
`https://slop.wiki/wiki/Special:UserLogin`

### 3.2 Secure Admin Account

1. Go to `Special:ChangePassword` - ensure strong password
2. Consider creating a separate everyday account for non-admin tasks

---

## 4. Bot Account Setup

### 4.1 Create Bot User Account

1. Login as admin
2. Go to `Special:CreateAccount`
3. Create account:
   - **Username:** `SlopBot`
   - **Password:** Generate secure password
   - **Email:** Optional but recommended

### 4.2 Add Bot to Bot Group

1. Go to `Special:UserRights`
2. Enter username: `SlopBot`
3. Add to group: `bot`
4. Save

### 4.3 Create Bot Password (Recommended)

Bot passwords are safer than using the main account password:

1. Login as `SlopBot`
2. Go to `Special:BotPasswords`
3. Click "Create"
4. **Bot name:** `automation`
5. **Grants:** Select required permissions:
   - ✅ Basic rights (read pages, etc.)
   - ✅ High-volume editing
   - ✅ Edit existing pages
   - ✅ Create, edit, and move pages
   - ✅ Upload new files
   - ✅ Upload, replace, and move files
   - ✅ Delete pages, revisions, and log entries
6. Click "Create"
7. **SAVE THE GENERATED PASSWORD** - it's shown only once!

The bot credentials will be:
- **Username:** `SlopBot@automation`
- **Password:** (the generated password)

### 4.4 Update Environment

Add to `.env`:
```
MEDIAWIKI_BOT_USER=SlopBot@automation
MEDIAWIKI_BOT_PASSWORD=<generated-password>
```

---

## 5. API Authentication Test

### 5.1 Test Login

```bash
# Get login token
curl -c cookies.txt -b cookies.txt \
  "https://slop.wiki/api.php?action=query&meta=tokens&type=login&format=json"

# Login (replace with your token and credentials)
curl -c cookies.txt -b cookies.txt \
  -d "action=login&lgname=SlopBot@automation&lgpassword=YOUR_PASSWORD&lgtoken=YOUR_TOKEN&format=json" \
  "https://slop.wiki/api.php"
```

### 5.2 Test Edit

```bash
# Get CSRF token
curl -c cookies.txt -b cookies.txt \
  "https://slop.wiki/api.php?action=query&meta=tokens&format=json"

# Create test page
curl -c cookies.txt -b cookies.txt \
  -d "action=edit&title=User:SlopBot/Test&text=Bot test page&token=YOUR_CSRF_TOKEN%2B%5C&format=json" \
  "https://slop.wiki/api.php"
```

---

## 6. Python Bot Setup

### 6.1 Using mwclient (Recommended for Simple Bots)

```bash
pip install mwclient
```

```python
import mwclient

# Connect
site = mwclient.Site('slop.wiki', path='/')

# Login with bot password
site.login('SlopBot@automation', 'YOUR_BOT_PASSWORD')

# Create/edit a page
page = site.pages['Thread:Example']
page.save('Page content in wikitext', summary='Bot: Created page')

# Read a page
print(page.text())
```

### 6.2 Using Pywikibot (For Complex Bots)

```bash
pip install pywikibot
```

Create `user-config.py`:
```python
family = 'slop'
mylang = 'en'
usernames['slop']['en'] = 'SlopBot'
password_file = 'user-password.py'
```

Create `user-password.py`:
```python
('SlopBot@automation', 'YOUR_BOT_PASSWORD')
```

---

## 7. Maintenance Commands

### Run from within container:

```bash
# Enter container
docker compose exec mediawiki bash

# Update database schema
php maintenance/update.php

# Run queued jobs
php maintenance/runJobs.php

# Rebuild search index
php maintenance/rebuildall.php

# Clear caches
php maintenance/rebuildLocalisationCache.php
```

### Backup:

```bash
# Database backup
docker compose exec db mysqldump -u wiki -p mediawiki > backup.sql

# Files backup
tar -czf images-backup.tar.gz mediawiki/images/
```

---

## 8. Troubleshooting

### MediaWiki shows "LocalSettings.php not found"
- Ensure the file is mounted correctly in docker-compose.yml
- Check file permissions: `chmod 644 mediawiki/LocalSettings.php`

### Database connection errors
- Verify `db` container is healthy: `docker compose ps`
- Check database credentials match between docker-compose.yml and LocalSettings.php

### API returns "readonly" error
- Bot might not have edit permissions
- Check `Special:UserRights` for the bot account
- Verify bot password grants include edit permissions

### "Token mismatch" on edits
- CSRF tokens expire; fetch a new one before each edit
- Ensure cookies are being sent with requests

---

## 9. Production Checklist

- [ ] Strong passwords for all accounts
- [ ] HTTPS configured (via reverse proxy)
- [ ] Regular database backups scheduled
- [ ] MediaWiki version updates planned
- [ ] Rate limiting configured appropriately
- [ ] Error logging enabled but details hidden from public
- [ ] Public account creation disabled
- [ ] Bot account created and tested
- [ ] Redis caching working

---

## 10. Useful URLs

| Page | URL |
|------|-----|
| Main Page | `/wiki/Main_Page` |
| All Pages | `/wiki/Special:AllPages` |
| Recent Changes | `/wiki/Special:RecentChanges` |
| User Rights | `/wiki/Special:UserRights` |
| Bot Passwords | `/wiki/Special:BotPasswords` |
| API Sandbox | `/wiki/Special:ApiSandbox` |
| Version | `/wiki/Special:Version` |
