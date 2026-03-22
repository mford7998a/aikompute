#!/bin/bash
# ============================================
# AI Inference Gateway — GCP VM Resume Setup
# Run this on your GCP VM after the deploy-gcp.sh
# script was interrupted at step 6.
#
# Usage: sudo bash vm_setup.sh
# ============================================

set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${GREEN}============================================${NC}"
echo -e "${GREEN} AI Inference Gateway — Resume Setup${NC}"
echo -e "${GREEN}============================================${NC}"
echo ""

if [ "$EUID" -ne 0 ]; then
    echo -e "${RED}Please run as root: sudo bash vm_setup.sh${NC}"
    exit 1
fi

DOMAIN="aikompute.com"

# ---- Generated Keys ----
# These are random keys generated for your deployment
DB_PASS="Xk9mP4vR7nQ2wL5j"
REDIS_PASS="bT3yH8cF6dN1sW4a"
AICLIENT2API_KEY="a7f3e2d918b4c6509e1d"
ANTIGRAVITY2API_KEY="c4b8a1f6d3e7920548bc"
MASTER_KEY="sk-admin-Mv8Kp3Rq7YnT2Ws5"
JWT_SECRET="e9a4b7d1c8f3254067e2d5a8f1b4c7093d6e9a2b5c8f1d4e7a0b3c6f9d2e5a8b"

echo -e "${YELLOW}[1/5] Creating .env file...${NC}"
cat > .env << EOF
# Generated on $(date)
DB_PASSWORD=${DB_PASS}
REDIS_PASSWORD=${REDIS_PASS}
AICLIENT2API_KEY=${AICLIENT2API_KEY}
ANTIGRAVITY2API_KEY=${ANTIGRAVITY2API_KEY}
MASTER_API_KEY=${MASTER_KEY}
JWT_SECRET=${JWT_SECRET}

# Stripe (add when ready)
STRIPE_SECRET_KEY=
STRIPE_WEBHOOK_SECRET=

# GitHub token for GitHub Models free tier (optional)
GITHUB_TOKEN=

# Domain
DOMAIN=${DOMAIN}
EOF
echo -e "${GREEN}.env created!${NC}"

# ---- Create aiclient2api config ----
echo -e "${YELLOW}[2/5] Creating aiclient2api config...${NC}"
mkdir -p aiclient2api-configs
cat > aiclient2api-configs/config.json << EOF
{
  "REQUIRED_API_KEY": "${AICLIENT2API_KEY}"
}
EOF
echo -e "${GREEN}aiclient2api config created!${NC}"

# ---- Create antigravity2api .env ----
echo -e "${YELLOW}[3/5] Configuring antigravity and nginx...${NC}"

# Update antigravity .env with matching key
if [ -d "antigravity2api-nodejs" ]; then
    cat > antigravity2api-nodejs/.env << EOF
# API key — must match ANTIGRAVITY2API_KEY in root .env
API_KEY=${ANTIGRAVITY2API_KEY}

# Web admin panel credentials
ADMIN_USERNAME=admin
ADMIN_PASSWORD=Rk7mQ4vX9nL2p

# JWT secret for admin panel sessions
JWT_SECRET=$(openssl rand -hex 32 2>/dev/null || echo "ag-jwt-f8c3d7a1e9b4520634d")

# External base URL (set to your domain in prod)
IMAGE_BASE_URL=https://${DOMAIN}
EOF
    echo -e "${GREEN}antigravity2api .env created!${NC}"
fi

# Update nginx config with domain
sed -i "s/YOUR_DOMAIN.com/${DOMAIN}/g" nginx/app.conf
echo -e "${GREEN}Nginx configured for ${DOMAIN}!${NC}"

# ---- SSL Certificate ----
echo -e "${YELLOW}[4/5] Getting SSL certificate...${NC}"
echo ""
SERVER_IP=$(curl -s ifconfig.me)
echo -e "${YELLOW}==============================================${NC}"
echo -e "${YELLOW}  Your server IP: ${GREEN}${SERVER_IP}${NC}"
echo -e "${YELLOW}==============================================${NC}"
echo ""
echo -e "${YELLOW}Before continuing, set this DNS record:${NC}"
echo -e "  Type:  ${GREEN}A${NC}"
echo -e "  Name:  ${GREEN}@${NC}"
echo -e "  Value: ${GREEN}${SERVER_IP}${NC}"
echo ""
read -p "Press Enter when DNS is configured (or Ctrl+C to do it later)..."

# Stop anything on port 80
docker compose -f docker-compose.prod.yml down 2>/dev/null || true

certbot certonly \
    --standalone \
    --non-interactive \
    --agree-tos \
    --email "mford7998a@gmail.com" \
    -d "${DOMAIN}"

echo -e "${GREEN}SSL certificate obtained!${NC}"

# ---- Start Services ----
echo -e "${YELLOW}[5/5] Building and starting all services...${NC}"
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
echo -e "  ${YELLOW}Master API key:${NC}  ${MASTER_KEY}"
echo -e "  ${YELLOW}Admin password:${NC}  Rk7mQ4vX9nL2p"
echo ""
echo -e "${YELLOW}SAVE THESE CREDENTIALS SOMEWHERE SAFE!${NC}"
echo ""
echo -e "${YELLOW}Next steps:${NC}"
echo -e "  1. Open ${GREEN}https://${DOMAIN}/admin/${NC} to add provider credentials"
echo -e "  2. Open ${GREEN}https://${DOMAIN}${NC} to create a user account"
echo -e "  3. Use your API key with any OpenAI SDK:"
echo ""
echo -e "     ${GREEN}from openai import OpenAI${NC}"
echo -e "     ${GREEN}client = OpenAI(api_key='YOUR_USER_KEY', base_url='https://${DOMAIN}/v1')${NC}"
echo ""
echo -e "${YELLOW}To authenticate GitHub Copilot (optional):${NC}"
echo -e "  docker exec -it copilot-api npx copilot-api start"
echo ""
echo -e "${GREEN}SSL auto-renewal is configured via Certbot container.${NC}"
echo ""
