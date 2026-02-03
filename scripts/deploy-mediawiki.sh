#!/bin/bash
# Deploy MediaWiki on slop.wiki server
# Run on the target server (167.71.100.19)

set -e

DEPLOY_DIR="/opt/slop-wiki"
BACKUP_DIR="/opt/slop-wiki-backup-$(date +%Y%m%d-%H%M%S)"

echo "=== MediaWiki Deployment Script for slop.wiki ==="
echo ""

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo "Please run as root (sudo)"
    exit 1
fi

# Backup existing installation
if [ -d "$DEPLOY_DIR" ]; then
    echo "Backing up existing installation to $BACKUP_DIR..."
    cp -r "$DEPLOY_DIR" "$BACKUP_DIR"
    echo "Backup complete."
fi

cd "$DEPLOY_DIR"

# Check for .env file
if [ ! -f ".env" ]; then
    echo "ERROR: .env file not found!"
    echo "Copy .env.example to .env and configure it first."
    exit 1
fi

# Load environment
source .env

# Check required variables
if [ -z "$MYSQL_PASSWORD" ] || [ -z "$MYSQL_ROOT_PASSWORD" ]; then
    echo "ERROR: Database passwords not set in .env"
    exit 1
fi

echo ""
echo "=== Step 1: Stop existing services ==="
docker compose down || true

echo ""
echo "=== Step 2: Pull latest images ==="
docker compose pull

echo ""
echo "=== Step 3: Create required directories ==="
mkdir -p mediawiki/images
chmod 755 mediawiki/images

echo ""
echo "=== Step 4: Start database ==="
docker compose up -d db

echo "Waiting for database to be healthy..."
sleep 10
for i in {1..30}; do
    if docker compose exec db healthcheck.sh --connect 2>/dev/null; then
        echo "Database is ready!"
        break
    fi
    echo "Waiting... ($i/30)"
    sleep 2
done

echo ""
echo "=== Step 5: Start MediaWiki ==="

# Check if LocalSettings.php exists
if [ -f "mediawiki/LocalSettings.php" ]; then
    echo "LocalSettings.php found, starting with full configuration..."
    docker compose up -d mediawiki
else
    echo "LocalSettings.php NOT found."
    echo ""
    echo "Starting MediaWiki without LocalSettings for initial setup..."
    echo "The installation wizard will be available."
    
    # Start without LocalSettings mount
    docker compose up -d mediawiki
    
    echo ""
    echo "======================================"
    echo "IMPORTANT: Complete the setup wizard!"
    echo "======================================"
    echo ""
    echo "1. Open http://$(hostname -I | awk '{print $1}'):3000/mw-config/"
    echo "2. Follow the installation wizard"
    echo "3. Download the generated LocalSettings.php"
    echo "4. Copy secret keys to mediawiki/LocalSettings.php"
    echo "5. Run this script again"
    echo ""
    exit 0
fi

echo ""
echo "=== Step 6: Start remaining services ==="
docker compose up -d redis backend

echo ""
echo "=== Step 7: Verify services ==="
sleep 5
docker compose ps

echo ""
echo "=== Step 8: Test API ==="
API_TEST=$(curl -s "http://localhost:3000/api.php?action=query&meta=siteinfo&format=json" | head -c 100)
if echo "$API_TEST" | grep -q "sitename"; then
    echo "✓ MediaWiki API is responding!"
else
    echo "✗ API test failed. Check logs with: docker compose logs mediawiki"
fi

echo ""
echo "=== Deployment Complete ==="
echo ""
echo "MediaWiki is now running on port 3000"
echo ""
echo "Next steps:"
echo "1. Set up DNS to point slop.wiki to this server"
echo "2. Configure HTTPS (nginx/caddy reverse proxy)"
echo "3. Create bot account (see docs/MEDIAWIKI-SETUP.md)"
echo "4. Run migration script if needed"
echo ""
echo "Useful commands:"
echo "  docker compose logs -f mediawiki  # View logs"
echo "  docker compose exec mediawiki bash  # Enter container"
echo "  docker compose down  # Stop all services"
echo ""
