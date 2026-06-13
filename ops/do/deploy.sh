#!/bin/bash
# iCLONE — Deploy from Mac to DigitalOcean
# Usage: bash ops/do/deploy.sh <droplet-ip>
# Example: bash ops/do/deploy.sh 167.99.123.45
set -euo pipefail

DROPLET_IP="${1:?Usage: deploy.sh <droplet-ip>}"
DROPLET_USER="root"   # root no primeiro deploy; depois muda para iclone
REMOTE_DIR="/opt/iclone"
LOCAL_DIR="$(cd "$(dirname "$0")/../.." && pwd)"

echo "================================================"
echo "  iCLONE Deploy → ${DROPLET_IP}"
echo "================================================"

# ── 1. Criar directório remoto como root ──────────────
ssh root@${DROPLET_IP} "mkdir -p ${REMOTE_DIR} && chown -R iclone:iclone ${REMOTE_DIR} 2>/dev/null || true"

# ── 2. Sincronizar código ─────────────────────────────
echo ""
echo "── Sincronizando código... ──────────────────────"
rsync -avz --progress \
    --exclude='.git' \
    --exclude='venv312' \
    --exclude='__pycache__' \
    --exclude='*.pyc' \
    --exclude='.DS_Store' \
    --exclude='ops/launchd' \
    --exclude='training_reports' \
    "${LOCAL_DIR}/" \
    "root@${DROPLET_IP}:${REMOTE_DIR}/"
echo "✓ Código sincronizado"

# ── 3. Copiar .env ────────────────────────────────────
if [ -f "${LOCAL_DIR}/.env" ]; then
    scp "${LOCAL_DIR}/.env" "root@${DROPLET_IP}:${REMOTE_DIR}/.env"
    ssh root@${DROPLET_IP} "chmod 600 ${REMOTE_DIR}/.env && chown iclone:iclone ${REMOTE_DIR}/.env"
    echo "✓ .env copiado e protegido (600)"
fi

# ── 4. Copiar config acp-cli (credenciais Privy MPC) ──
ACP_CONFIG="${HOME}/.config/acp/config.json"
if [ -f "${ACP_CONFIG}" ]; then
    ssh root@${DROPLET_IP} "mkdir -p /home/iclone/.config/acp && chown -R iclone:iclone /home/iclone/.config"
    scp "${ACP_CONFIG}" "root@${DROPLET_IP}:/home/iclone/.config/acp/config.json"
    ssh root@${DROPLET_IP} "chown iclone:iclone /home/iclone/.config/acp/config.json && chmod 600 /home/iclone/.config/acp/config.json"
    echo "✓ acp config.json copiada (credenciais Privy)"
else
    echo "⚠ ~/.config/acp/config.json não encontrada — acp configure será necessário no servidor"
fi

# ── 5. Permissões finais ──────────────────────────────
ssh root@${DROPLET_IP} "chown -R iclone:iclone ${REMOTE_DIR}"

echo ""
echo "================================================"
echo "  ✓ Deploy completo."
echo "================================================"
echo ""
echo "PRÓXIMOS PASSOS:"
echo ""
echo "  1. (se primeiro deploy — instalar dependências):"
echo "     ssh root@${DROPLET_IP} 'bash ${REMOTE_DIR}/ops/do/setup.sh'"
echo "     ssh iclone@${DROPLET_IP} 'bash ${REMOTE_DIR}/ops/do/install.sh'"
echo ""
echo "  2. Iniciar os 4 serviços:"
echo "     ssh root@${DROPLET_IP} 'bash ${REMOTE_DIR}/ops/do/start-services.sh'"
echo ""
echo "  3. Verificar logs:"
echo "     ssh root@${DROPLET_IP} 'tail -f /var/log/iclone/server.log'"
echo ""
echo "  Para actualizar (código já instalado):"
echo "     ssh root@${DROPLET_IP} 'systemctl restart iclone-server iclone-supersayatin iclone-doctorwho iclone-matrix'"
