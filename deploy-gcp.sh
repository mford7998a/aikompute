#!/bin/bash
# ============================================
# AI Inference Gateway — GCP Deployment Script
# Run this on a fresh GCP VM (Ubuntu 22.04+)
# ============================================

set -e

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${GREEN}============================================${NC}"
echo -e "${GREEN} AI Inference Gateway — GCP Setup${NC}"
echo -e "${GREEN}============================================${NC}"
echo ""

# ---- Check if running as root ----
if [ "$EUID" -ne 0 ]; then
    echo -e "${RED}Please run as root: sudo bash deploy-gcp.sh${NC}"
    exit 1
fi

# ---- Get domain from user ----
read -p "Enter your domain name (e.g., api.yourdomain.com): " DOMAIN
read -p "Enter your email for SSL certificate: " EMAIL
read -p "Enter a strong database password: " DB_PASS
read -p "Enter a master API key (for admin): " MASTER_KEY

if [ -z "$DOMAIN" ] || [ -z "$EMAIL" ]; then
    echo -e "${RED}Domain and email are required!${NC}"
    exit 1
fi

# ---- Step 1: System updates ----
echo -e "\n${YELLOW}[1/8] Updating system...${NC}"
apt-get update -y
apt-get upgrade -y

# ---- Step 2: Install Docker ----
echo -e "\n${YELLOW}[2/8] Installing Docker...${NC}"
if ! command -v docker &> /dev/null; then
    curl -fsSL https://get.docker.com | sh
    systemctl enable docker
    systemctl start docker
    echo -e "${GREEN}Docker installed!${NC}"
else
    echo "Docker already installed."
fi

# Install Docker Compose plugin
if ! docker compose version &> /dev/null; then
    apt-get install -y docker-compose-plugin
fi

# ---- Step 3: Install Certbot standalone (for initial cert) ----
echo -e "\n${YELLOW}[3/8] Installing Certbot...${NC}"
apt-get install -y certbot

# ---- Step 4: Configure firewall ----
echo -e "\n${YELLOW}[4/8] Configuring firewall...${NC}"
ufw allow 22/tcp    # SSH
ufw allow 80/tcp    # HTTP
ufw allow 443/tcp   # HTTPS
ufw allow 8085:8087/tcp   # OAuth callbacks (Gemini, Antigravity, iFlow)
ufw allow 1455/tcp        # Codex OAuth
ufw allow 19876:19880/tcp # Kiro OAuth
ufw --force enable
echo -e "${GREEN}Firewall configured!${NC}"

# ---- Step 5: Create .env file ----
echo -e "\n${YELLOW}[5/8] Creating environment config...${NC}"
JWT_SECRET=$(openssl rand -hex 32)
AICLIENT2API_KEY=$(openssl rand -hex 16)
REDIS_PASS=$(openssl rand -hex 16)

cat > .env << EOF
# Generated on $(date)
DB_PASSWORD=${DB_PASS}
REDIS_PASSWORD=${REDIS_PASS}
AICLIENT2API_KEY=${AICLIENT2API_KEY}
MASTER_API_KEY=${MASTER_KEY}
JWT_SECRET=${JWT_SECRET}

# Stripe (add when ready)
STRIPE_SECRET_KEY=
STRIPE_WEBHOOK_SECRET=

# Domain
DOMAIN=${DOMAIN}
EMAIL=${EMAIL}
EOF

echo -e "${GREEN}.env created!${NC}"

# ---- Step 6: Configure nginx with actual domain ----
echo -e "\n${YELLOW}[6/8] Configuring nginx for ${DOMAIN}...${NC}"
sed -i "s/YOUR_DOMAIN.com/${DOMAIN}/g" nginx/app.conf

# Also update AIClient-2-API key in config
sed -i "s/\"PLACEHOLDER_KEY\"/\"${AICLIENT2API_KEY}\"/g" aiclient2api-configs/config.json

# Update dashboard API base URL to use the domain
sed -i "s|http://localhost:4000|https://${DOMAIN}|g" dashboard/app.js

echo -e "${GREEN}Nginx configured for ${DOMAIN}!${NC}"

# ---- Step 7: Get SSL certificate ----
echo -e "\n${YELLOW}[7/8] Getting SSL certificate from Let's Encrypt...${NC}"
echo ""
echo -e "${YELLOW}IMPORTANT: Make sure your domain ${DOMAIN} points to this server's IP!${NC}"
echo -e "${YELLOW}Set an A record: ${DOMAIN} → $(curl -s ifconfig.me)${NC}"
echo ""
read -p "Press Enter when DNS is configured (or Ctrl+C to do it later)..."

# Stop anything on port 80
docker compose -f docker-compose.prod.yml down 2>/dev/null || true

certbot certonly \
    --standalone \
    --non-interactive \
    --agree-tos \
    --email "${EMAIL}" \
    -d "${DOMAIN}"

echo -e "${GREEN}SSL certificate obtained!${NC}"

# ---- Step 8: Start services ----
echo -e "\n${YELLOW}[8/8] Starting all services...${NC}"
docker compose -f docker-compose.prod.yml up -d --build

echo ""
echo -e "${GREEN}============================================${NC}"
echo -e "${GREEN}  🚀 Deployment Complete!${NC}"
echo -e "${GREEN}============================================${NC}"
echo ""
echo -e "  Dashboard:     ${GREEN}https://${DOMAIN}${NC}"
echo -e "  API endpoint:  ${GREEN}https://${DOMAIN}/v1/chat/completions${NC}"
echo -e "  Admin panel:   ${GREEN}https://${DOMAIN}/admin/${NC}"
echo -e "  API docs:      ${GREEN}https://${DOMAIN}/docs${NC}"
echo ""
echo -e "  Master API key: ${YELLOW}${MASTER_KEY}${NC}"
echo ""
echo -e "${YELLOW}Next steps:${NC}"
echo -e "  1. Open ${GREEN}https://${DOMAIN}/admin/${NC} to add provider credentials"
echo -e "     (default password: ADMIN_PASSWORD)"
echo -e "  2. Open ${GREEN}https://${DOMAIN}${NC} to create a user account"
echo -e "  3. Use your API key with any OpenAI SDK:"
echo ""
echo -e "     ${GREEN}from openai import OpenAI${NC}"
echo -e "     ${GREEN}client = OpenAI(api_key='sk-inf-xxx', base_url='https://${DOMAIN}/v1')${NC}"
echo ""
echo -e "${YELLOW}SSL auto-renewal is configured. Certificates renew automatically.${NC}"
echo ""
