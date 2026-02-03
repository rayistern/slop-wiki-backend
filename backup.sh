#!/bin/bash
# Daily backup script for slop.wiki
# Add to crontab: 0 4 * * * /var/www/slop-wiki-backend/backup.sh

BACKUP_DIR="/var/www/backups"
DATE=$(date +%Y-%m-%d)
DB_PATH="/var/www/slop-wiki-backend/slop.db"
WIKI_DB="/var/www/wiki/wiki.db"

mkdir -p "$BACKUP_DIR"

# Backup backend DB
if [ -f "$DB_PATH" ]; then
    sqlite3 "$DB_PATH" ".backup '$BACKUP_DIR/slop-$DATE.db'"
    echo "Backend DB backed up: slop-$DATE.db"
fi

# Backup wiki DB
if [ -f "$WIKI_DB" ]; then
    sqlite3 "$WIKI_DB" ".backup '$BACKUP_DIR/wiki-$DATE.db'"
    echo "Wiki DB backed up: wiki-$DATE.db"
fi

# Keep only last 7 days
find "$BACKUP_DIR" -name "*.db" -mtime +7 -delete

echo "Backup complete: $DATE"
