#!/bin/bash
# ============================================
# Install Cloudflare Origin SSL Certificate
# Run on your GCP VM: sudo bash install_ssl.sh
# ============================================

set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${GREEN}============================================${NC}"
echo -e "${GREEN} SSL Certificate Installer${NC}"
echo -e "${GREEN}============================================${NC}"
echo ""

# Get the cert from user
echo -e "${YELLOW}Paste your Cloudflare Origin Certificate below.${NC}"
echo -e "${YELLOW}(starts with -----BEGIN CERTIFICATE-----)${NC}"
echo -e "${YELLOW}When done, type END on a new line and press Enter:${NC}"
echo ""

CERT=""
while IFS= read -r line; do
    [ "$line" = "END" ] && break
    CERT="${CERT}${line}
"
done

echo ""
echo -e "${YELLOW}Now paste your Private Key below.${NC}"
echo -e "${YELLOW}(starts with -----BEGIN PRIVATE KEY-----)${NC}"
echo -e "${YELLOW}When done, type END on a new line and press Enter:${NC}"
echo ""

KEY=""
while IFS= read -r line; do
    [ "$line" = "END" ] && break
    KEY="${KEY}${line}
"
done

# Save certs to host
mkdir -p /etc/letsencrypt/live/aikompute.com
echo "$CERT" > /etc/letsencrypt/live/aikompute.com/fullchain.pem
echo "$KEY" > /etc/letsencrypt/live/aikompute.com/privkey.pem

echo ""
echo -e "${GREEN}Certs saved to host!${NC}"

# Copy into Docker volume
echo -e "${YELLOW}Copying certs into Docker volume...${NC}"

docker run --rm \
  -v aikompute_certbot-etc:/certs \
  -v /etc/letsencrypt:/source:ro \
  alpine sh -c "mkdir -p /certs/live/aikompute.com && cp /source/live/aikompute.com/fullchain.pem /certs/live/aikompute.com/fullchain.pem && cp /source/live/aikompute.com/privkey.pem /certs/live/aikompute.com/privkey.pem"

echo -e "${GREEN}Certs installed in Docker volume!${NC}"

# Restart nginx
echo -e "${YELLOW}Restarting nginx...${NC}"
cd /home/*/aikompute 2>/dev/null || cd ~/aikompute
docker compose -f docker-compose.prod.yml restart nginx

sleep 3

# Check if it worked
if docker ps --filter "name=inference-nginx" --format "{{.Status}}" | grep -q "Up"; then
    echo ""
    echo -e "${GREEN}============================================${NC}"
    echo -e "${GREEN}  ✅ SSL installed! Nginx is running!${NC}"
    echo -e "${GREEN}============================================${NC}"
    echo ""
    echo -e "  Test it: ${GREEN}curl -k https://localhost/health${NC}"
    echo -e "  Browser: ${GREEN}https://aikompute.com${NC}"
else
    echo ""
    echo -e "${YELLOW}Nginx may still be starting. Check with:${NC}"
    echo -e "  docker logs inference-nginx --tail 10"
fi
echo ""
