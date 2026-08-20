#!/bin/bash
# Deploy EfficiencyFinder to Unraid (same flow as the g-force webapp).
# Usage: ./deploy.sh

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

CONFIG_FILE=".deploy.config"
if [ ! -f "$CONFIG_FILE" ]; then
  echo -e "${RED}Error: $CONFIG_FILE not found.${NC}"
  echo "Copy deploy.config.example to .deploy.config and fill in Unraid settings."
  exit 1
fi
# shellcheck disable=SC1090
source "$CONFIG_FILE"

if [ -z "$UNRAID_HOST" ] || [ -z "$UNRAID_USER" ] || [ -z "$UNRAID_DEPLOY_PATH" ]; then
  echo -e "${RED}Error: UNRAID_HOST, UNRAID_USER, and UNRAID_DEPLOY_PATH are required.${NC}"
  exit 1
fi

IMAGE=efficiencyfinder-webapp
TAR="${IMAGE}-latest.tar"
SSH_TARGET="$UNRAID_USER@$UNRAID_HOST"

echo -e "${GREEN}=== EfficiencyFinder webapp deployment ===${NC}"

echo -e "${YELLOW}[1/4] Building Docker image for linux/amd64...${NC}"
docker build --platform linux/amd64 -t "${IMAGE}:latest" .
echo -e "${GREEN}✓ Build complete${NC}"

echo -e "${YELLOW}[2/4] Saving Docker image...${NC}"
docker save "${IMAGE}:latest" -o "$TAR"
echo -e "${GREEN}✓ Image saved${NC}"

SSH_OPTS="-o ControlMaster=yes -o ControlPath=/tmp/ssh-deploy-$$ -o ControlPersist=60 -o StrictHostKeyChecking=no"
if [ -n "$SSH_KEY_PATH" ]; then
  SSH_OPTS="$SSH_OPTS -i $SSH_KEY_PATH"
fi
trap 'ssh -o ControlPath=/tmp/ssh-deploy-$$ -O exit "$SSH_TARGET" 2>/dev/null || true; rm -f /tmp/ssh-deploy-$$ "$TAR"' EXIT INT TERM

echo -e "${YELLOW}[3/4] Transferring image to Unraid...${NC}"
ssh $SSH_OPTS "$SSH_TARGET" "mkdir -p $UNRAID_DEPLOY_PATH/data"
scp $SSH_OPTS "$TAR" "$SSH_TARGET:$UNRAID_DEPLOY_PATH/"
echo -e "${GREEN}✓ Files transferred${NC}"

echo -e "${YELLOW}[4/4] Loading image and restarting container...${NC}"
ssh $SSH_OPTS "$SSH_TARGET" << EOF
cd $UNRAID_DEPLOY_PATH
docker load -i $TAR
docker stop $IMAGE 2>/dev/null || true
docker rm $IMAGE 2>/dev/null || true
docker run -d \
  --name $IMAGE \
  --restart unless-stopped \
  -p 4322:4322 \
  -v $UNRAID_DEPLOY_PATH/data:/data \
  ${IMAGE}:latest
sleep 2
if docker ps | grep -q $IMAGE; then
  echo "  - Container is running"
  docker ps | grep $IMAGE
else
  echo "  - Container failed to start:"
  docker logs $IMAGE 2>&1 | tail -20
  exit 1
fi
rm -f $TAR
EOF

echo -e "${GREEN}Deployment complete.${NC}"
echo "Point a Cloudflare Tunnel public hostname at http://localhost:4322"
