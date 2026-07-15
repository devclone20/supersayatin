#!/bin/bash
# iCLONE — DigitalOcean Droplet Setup
# Run once as root on a fresh Ubuntu 22.04 droplet:
#   bash setup.sh
set -euo pipefail

ICLONE_USER="iclone"
ICLONE_DIR="/opt/iclone"
LOG_DIR="/var/log/iclone"
NODE_VERSION="20"
PYTHON_VERSION="3.12"

echo "================================================"
echo "  iCLONE Cloud Setup — Ubuntu 22.04"
echo "================================================"

# ── System packages ──────────────────────────────────
apt-get update -qq
apt-get install -y -qq \
    curl wget git build-essential \
    software-properties-common \
    ufw fail2ban \
    python3-pip python3-venv

# ── Python 3.12 ──────────────────────────────────────
add-apt-repository -y ppa:deadsnakes/ppa
apt-get install -y -qq python${PYTHON_VERSION} python${PYTHON_VERSION}-venv python${PYTHON_VERSION}-dev

# ── Node.js 20 LTS ───────────────────────────────────
curl -fsSL https://deb.nodesource.com/setup_${NODE_VERSION}.x | bash -
apt-get install -y -qq nodejs
npm install -g @virtuals-protocol/acp-cli@latest

echo "acp version: $(acp --version 2>/dev/null || echo 'installed')"

# ── Dedicated user ───────────────────────────────────
id -u ${ICLONE_USER} &>/dev/null || useradd -m -s /bin/bash ${ICLONE_USER}

# ── Directories ──────────────────────────────────────
mkdir -p ${ICLONE_DIR} ${LOG_DIR}
chown -R ${ICLONE_USER}:${ICLONE_USER} ${ICLONE_DIR} ${LOG_DIR}

# ── Firewall ─────────────────────────────────────────
ufw --force enable
ufw allow ssh
ufw allow 80/tcp
ufw allow 443/tcp
ufw default deny incoming
ufw default allow outgoing

# ── fail2ban (SSH brute-force protection) ────────────
systemctl enable fail2ban
systemctl start fail2ban

echo ""
echo "✓ System setup complete."
echo ""
echo "Next: run as '${ICLONE_USER}' user:"
echo "  su - ${ICLONE_USER}"
echo "  bash /opt/iclone/ops/do/install.sh"
