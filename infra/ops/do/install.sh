#!/bin/bash
# iCLONE — App install (run as iclone user on the droplet)
# Assumes code is already at /opt/iclone via deploy.sh
# Usage: bash /opt/iclone/ops/do/install.sh
set -euo pipefail

ICLONE_DIR="/opt/iclone"
PYTHON="/usr/bin/python3.12"

# Agent IDs — confirmed 2026-06-12
CLONE_ID="019eae06-96cd-77d0-8f8b-a6abb71f0cd7"
SUPERSAYATIN_ID="019ebb92-7415-7baa-93e9-ee19a7742877"
DOCTORWHO_ID="019ebb92-93e8-7b4e-b2e8-39c3419843c9"
MATRIX_ID="019ebb92-b4be-7660-82d3-4b1647843e6a"

cd ${ICLONE_DIR}

echo "================================================"
echo "  iCLONE — App Install"
echo "================================================"

echo ""
echo "── Creating virtualenv ──────────────────────────"
${PYTHON} -m venv venv312
source venv312/bin/activate

echo "── Installing Python deps ───────────────────────"
pip install --quiet --upgrade pip
pip install --quiet \
    python-dotenv \
    supabase \
    web3 \
    requests \
    httpx \
    anthropic

echo ""
echo "── Configuring acp-cli — CLONE (Provider) ───────"
echo ""
echo "  → Uma URL vai aparecer abaixo."
echo "  → Abre essa URL no teu browser do Mac."
echo "  → Faz login com a mesma conta que usaste para criar o CLONE."
echo "  → Selecciona o agente CLONE quando pedido."
echo ""
read -p "  Pressiona ENTER para começar..."
acp configure
acp agent use --agent-id ${CLONE_ID}
echo "✓ CLONE configurado"

echo ""
echo "── Autenticando SuperSayatin (CLIENT) ───────────"
echo ""
echo "  → Vai aparecer outra URL — abre no Mac browser."
echo "  → Selecciona o agente SuperSayatin."
echo ""
read -p "  Pressiona ENTER..."
acp configure
acp agent use --agent-id ${SUPERSAYATIN_ID}
echo "✓ SuperSayatin configurado"

echo ""
echo "── Autenticando DoctorWHO (CLIENT) ──────────────"
echo ""
read -p "  Pressiona ENTER (URL vai aparecer — abre no Mac)..."
acp configure
acp agent use --agent-id ${DOCTORWHO_ID}
echo "✓ DoctorWHO configurado"

echo ""
echo "── Autenticando MATRIX (CLIENT) ─────────────────"
echo ""
read -p "  Pressiona ENTER (URL vai aparecer — abre no Mac)..."
acp configure
acp agent use --agent-id ${MATRIX_ID}
echo "✓ MATRIX configurado"

echo ""
echo "── Restaurar CLONE como agente activo ───────────"
acp agent use --agent-id ${CLONE_ID}

echo ""
echo "── Verificando autenticação ─────────────────────"
acp agent list
echo ""
acp agent whoami --json

echo ""
echo "================================================"
echo "  ✓ Install completo — 4 agentes autenticados."
echo "================================================"
echo ""
echo "Próximo passo (como root):"
echo "  sudo bash ${ICLONE_DIR}/ops/do/start-services.sh"
