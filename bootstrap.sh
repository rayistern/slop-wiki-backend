#!/bin/bash
# Run this ONCE on a fresh server to set up slop.wiki backend
# Usage: curl -sSL https://raw.githubusercontent.com/rayistern/slop-wiki-backend/main/bootstrap.sh | bash

set -e

echo "=== slop.wiki Backend Bootstrap ==="

# Install dependencies
apt update && apt install -y python3 python3-pip python3-venv nginx git

# Clone repo
mkdir -p /var/www
cd /var/www
git clone https://github.com/rayistern/slop-wiki-backend.git
cd slop-wiki-backend

# Setup Python
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Initialize database
python database.py

# Create .env (EDIT THIS!)
cat > .env << ENV
ADMIN_KEY=CHANGE_ME_TO_YOUR_ADMIN_KEY
GITHUB_REPO=rayistern/slop-wiki-backend
ENV

echo "⚠️  EDIT /var/www/slop-wiki-backend/.env with your ADMIN_KEY!"

# Create systemd service
cat > /etc/systemd/system/slop-backend.service << SERVICE
[Unit]
Description=slop.wiki Backend API
After=network.target

[Service]
User=root
WorkingDirectory=/var/www/slop-wiki-backend
ExecStart=/var/www/slop-wiki-backend/venv/bin/uvicorn main:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
SERVICE

systemctl daemon-reload
systemctl enable slop-backend
systemctl start slop-backend

# Nginx config
cat > /etc/nginx/sites-available/slop.wiki << NGINX
server {
    listen 80;
    server_name api.slop.wiki;
    
    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
    }
}

server {
    listen 80;
    server_name slop.wiki www.slop.wiki;
    
    location / {
        proxy_pass http://localhost:3000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
    }
}
NGINX

ln -sf /etc/nginx/sites-available/slop.wiki /etc/nginx/sites-enabled/
rm -f /etc/nginx/sites-enabled/default
nginx -t && systemctl restart nginx

echo ""
echo "=== Bootstrap Complete ==="
echo "Backend: http://YOUR_IP:8000"
echo "Next steps:"
echo "  1. Point DNS: api.slop.wiki → YOUR_IP"
echo "  2. Point DNS: slop.wiki → YOUR_IP"
echo "  3. Edit /var/www/slop-wiki-backend/.env"
echo "  4. Run: certbot --nginx -d api.slop.wiki -d slop.wiki"
echo "  5. Set up Wiki.js on port 3000"
