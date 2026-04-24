#!/bin/bash

# ==============================================================================
# OJT Journal Maker - EC2 Deployment Script (Ubuntu 22.04 / 24.04)
# ==============================================================================
# This script configures your EC2 instance to run the FastAPI backend using
# Gunicorn, Uvicorn, Systemd, and Nginx.
#
# USAGE: 
#   1. SSH into your EC2 instance.
#   2. Clone your repository: git clone https://github.com/your-username/OJT-maker.git
#   3. cd OJT-maker/backend
#   4. chmod +x ../deploy_ec2.sh
#   5. sudo ../deploy_ec2.sh
# ==============================================================================

set -e

# Ensure script is run as root
if [ "$EUID" -ne 0 ]; then
  echo "Please run as root (use sudo)"
  exit 1
fi

echo "🚀 Starting Deployment Setup..."

# 1. Update and install dependencies
echo "📦 Installing system dependencies..."
apt-get update
apt-get install -y python3 python3-pip python3-venv nginx curl certbot python3-certbot-nginx

# 2. Set up Python Virtual Environment
# Navigate to the backend directory where requirements.txt is located
cd "$(dirname "$0")/backend"
APP_DIR=$(pwd)
echo "🐍 Setting up Python Virtual Environment in $APP_DIR..."

if [ ! -d "venv" ]; then
    python3 -m venv venv
fi

# Activate venv and install requirements
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

# 3. Create Systemd Service File
echo "⚙️ Creating Systemd service for FastAPI..."

SERVICE_FILE="/etc/systemd/system/ojt-backend.service"

cat <<EOF > $SERVICE_FILE
[Unit]
Description=Gunicorn instance to serve OJT Journal Maker Backend
After=network.target

[Service]
User=ubuntu
Group=www-data
WorkingDirectory=$APP_DIR
Environment="PATH=$APP_DIR/venv/bin"
ExecStart=$APP_DIR/venv/bin/gunicorn main:app --workers 4 --worker-class uvicorn.workers.UvicornWorker --bind 127.0.0.1:8000 --timeout 120 -m 007

[Install]
WantedBy=multi-user.target
EOF

# Start and enable the service
systemctl daemon-reload
systemctl start ojt-backend
systemctl enable ojt-backend

echo "✅ Systemd service started!"

# 4. Configure Nginx
echo "🌐 Configuring Nginx Reverse Proxy..."

NGINX_CONF="/etc/nginx/sites-available/ojt-backend"

cat <<EOF > $NGINX_CONF
server {
    listen 80;
    server_name ojl-backend.tasknest.tech;

    client_max_body_size 100M; # Allow large PDF uploads

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }
}
EOF

# Enable the Nginx site
ln -sf $NGINX_CONF /etc/nginx/sites-enabled/
rm -f /etc/nginx/sites-enabled/default

# Test and restart Nginx
nginx -t
systemctl restart nginx

# 5. Configure SSL
echo "🔒 Configuring SSL with Let's Encrypt..."
certbot --nginx -n --agree-tos --email arpitbabu802@gmail.com -d ojl-backend.tasknest.tech

echo "🎉 Deployment Complete!"
echo "Your API is now securely running at https://ojl-backend.tasknest.tech"
echo "Don't forget to update your frontend's API_BASE_URL to point to this secure URL!"
