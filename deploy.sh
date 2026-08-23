#!/bin/bash
# Deploy EfficiencyFinder to Unraid.
#
# Usage (from repo root, in your own terminal):
#   cp deploy.config.example .deploy.config   # once
#   ./deploy.sh
#
# You will be prompted once for the Unraid SSH password (unless SSH_KEY_PATH
# is set). ControlMaster reuses that session for scp + remote docker commands.
#
# Optional:
#   ./deploy.sh --skip-build   # reuse the already-built local image tag

set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

SKIP_BUILD=0
for arg in "$@"; do
  case "$arg" in
    --skip-build) SKIP_BUILD=1 ;;
    -h|--help)
      sed -n '2,14p' "$0"
      exit 0
      ;;
    *)
      echo -e "${RED}Unknown option: $arg${NC}" >&2
      exit 1
      ;;
  esac
done

CONFIG_FILE=".deploy.config"
if [ ! -f "$CONFIG_FILE" ]; then
  echo -e "${RED}Error: $CONFIG_FILE not found.${NC}"
  echo "Copy deploy.config.example to .deploy.config and fill in Unraid settings."
  exit 1
fi
# shellcheck disable=SC1090
source "$CONFIG_FILE"

if [ -z "${UNRAID_HOST:-}" ] || [ -z "${UNRAID_USER:-}" ] || [ -z "${UNRAID_DEPLOY_PATH:-}" ]; then
  echo -e "${RED}Error: UNRAID_HOST, UNRAID_USER, and UNRAID_DEPLOY_PATH are required.${NC}"
  exit 1
fi

IMAGE=efficiencyfinder-webapp
TAR="${IMAGE}-latest.tar"
SSH_TARGET="$UNRAID_USER@$UNRAID_HOST"
CONTROL_PATH="/tmp/ssh-ef-deploy-$$"
VERSION="$(tr -d '[:space:]' < VERSION 2>/dev/null || echo unknown)"

cleanup() {
  ssh -o ControlPath="$CONTROL_PATH" -O exit "$SSH_TARGET" 2>/dev/null || true
  rm -f "$CONTROL_PATH" "$TAR"
}
trap cleanup EXIT INT TERM

# Shared SSH options. Prefer password auth by default so macOS does not burn
# through agent keys and hit "Too many authentication failures" before asking
# for a password. Set SSH_KEY_PATH in .deploy.config to use a key instead.
SSH_OPTS=(
  -o ControlMaster=yes
  -o ControlPath="$CONTROL_PATH"
  -o ControlPersist=180
  -o StrictHostKeyChecking=no
  -o NumberOfPasswordPrompts=1
  -o ServerAliveInterval=30
)
if [ -n "${SSH_KEY_PATH:-}" ]; then
  # Expand ~ if present
  KEY_PATH="${SSH_KEY_PATH/#\~/$HOME}"
  SSH_OPTS+=(-i "$KEY_PATH" -o IdentitiesOnly=yes)
else
  SSH_OPTS+=(
    -o PreferredAuthentications=password,keyboard-interactive
    -o PubkeyAuthentication=no
  )
fi

echo -e "${GREEN}=== EfficiencyFinder webapp deployment ===${NC}"
echo "  Host:    $SSH_TARGET"
echo "  Path:    $UNRAID_DEPLOY_PATH"
echo "  Version: $VERSION"
echo ""

if [ "$SKIP_BUILD" -eq 0 ]; then
  echo -e "${YELLOW}[1/4] Building Docker image for linux/amd64...${NC}"
  docker build --platform linux/amd64 -t "${IMAGE}:latest" .
  echo -e "${GREEN}✓ Build complete${NC}"
else
  echo -e "${YELLOW}[1/4] Skipping build (--skip-build); using local ${IMAGE}:latest${NC}"
  if ! docker image inspect "${IMAGE}:latest" >/dev/null 2>&1; then
    echo -e "${RED}Error: image ${IMAGE}:latest not found. Run without --skip-build.${NC}"
    exit 1
  fi
fi

echo -e "${YELLOW}[2/4] Saving Docker image...${NC}"
docker save "${IMAGE}:latest" -o "$TAR"
echo -e "${GREEN}✓ Image saved ($(du -h "$TAR" | awk '{print $1}'))${NC}"

echo -e "${YELLOW}[3/4] Connecting to Unraid (enter SSH password if prompted)...${NC}"
# Open the master connection once; later ssh/scp reuse it with no re-prompt.
ssh "${SSH_OPTS[@]}" "$SSH_TARGET" "mkdir -p '$UNRAID_DEPLOY_PATH/data'"
echo "  - Transferring image…"
scp "${SSH_OPTS[@]}" "$TAR" "$SSH_TARGET:$UNRAID_DEPLOY_PATH/"
echo -e "${GREEN}✓ Files transferred${NC}"

echo -e "${YELLOW}[4/4] Loading image and restarting container...${NC}"
# shellcheck disable=SC2029
ssh "${SSH_OPTS[@]}" "$SSH_TARGET" bash -s << EOF
set -euo pipefail
cd '$UNRAID_DEPLOY_PATH'
docker load -i '$TAR'
docker stop '$IMAGE' 2>/dev/null || true
docker rm '$IMAGE' 2>/dev/null || true
docker run -d \\
  --name '$IMAGE' \\
  --restart unless-stopped \\
  -p 4322:4322 \\
  -v '$UNRAID_DEPLOY_PATH/data:/data' \\
  '${IMAGE}:latest'
sleep 2
if docker ps --format '{{.Names}}' | grep -qx '$IMAGE'; then
  echo "  - Container is running"
  docker ps --filter "name=$IMAGE" --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}'
else
  echo "  - Container failed to start:"
  docker logs '$IMAGE' 2>&1 | tail -20
  exit 1
fi
echo -n "  - Health: "
curl -sf http://127.0.0.1:4322/health
echo
rm -f '$TAR'
EOF

echo ""
echo -e "${GREEN}Deployment complete (v${VERSION}).${NC}"
echo "Confirm the live site shows v${VERSION} in the header (hard-refresh if needed)."
echo "Tunnel target remains http://localhost:4322 on the Unraid host."
