#!/bin/bash
# Wiki.js bootstrap for slop.wiki
# Usage: curl -sSL https://raw.githubusercontent.com/rayistern/slop-wiki-backend/main/bootstrap-wiki.sh | bash

set -e

echo "=== slop.wiki Wiki.js Bootstrap ==="

# Install Node.js if needed
if ! command -v node &> /dev/null; then
    echo "Installing Node.js..."
    curl -fsSL https://deb.nodesource.com/setup_20.x | bash -
    apt install -y nodejs
fi

# Create wiki directory
mkdir -p /var/www/wiki
cd /var/www/wiki

# Download Wiki.js
echo "Downloading Wiki.js..."
wget -q https://github.com/Requarks/wiki/releases/latest/download/wiki-js.tar.gz
tar xzf wiki-js.tar.gz && rm wiki-js.tar.gz

# Configure
cat > config.yml << CONFIG
port: 3000
bindIP: 0.0.0.0

db:
  type: sqlite
  storage: /var/www/wiki/wiki.db

logLevel: info
logFormat: default

ha: false
dataPath: ./data
CONFIG

# Create systemd service
cat > /etc/systemd/system/wiki.service << SERVICE
[Unit]
Description=Wiki.js
After=network.target

[Service]
Type=simple
ExecStart=/usr/bin/node /var/www/wiki/server
Restart=always
RestartSec=5
User=root
WorkingDirectory=/var/www/wiki
Environment=NODE_ENV=production

[Install]
WantedBy=multi-user.target
SERVICE

systemctl daemon-reload
systemctl enable wiki
systemctl start wiki

echo ""
echo "=== Wiki.js Bootstrap Complete ==="
echo ""
echo "Wiki.js running on port 3000"
echo "Visit http://slop.wiki to complete setup"
echo ""
echo "First visit will prompt for:"
echo "  - Admin email & password"
echo "  - Site URL: https://slop.wiki"
echo ""
