#!/bin/bash
# iCLONE — Create 3 dedicated CLIENT agents
# Run locally on Mac (needs acp-cli authenticated)
set -euo pipefail

CLONE_WALLET="0x44cc25d55a4291b92f52062ba023ca1f14206664"
SEED_SQL="/tmp/iclone-clients-seed.sql"
> "${SEED_SQL}"

echo "================================================"
echo "  Creating iCLONE Dedicated CLIENT Agents"
echo "================================================"
echo ""

create_client() {
    local NAME="$1"
    local DESC="$2"

    echo "── Creating: ${NAME} ────────────────────────────"

    RESULT=$(acp agent create \
        --name "${NAME}" \
        --description "${DESC}" \
        --json 2>&1 || true)

    echo "${RESULT}"

    AGENT_ID=$(echo "${RESULT}" | python3 -c "
import sys, json
for line in reversed(sys.stdin.read().splitlines()):
    line = line.strip()
    if line.startswith('{'):
        try:
            d = json.loads(line)
            v = d.get('agentId') or d.get('id') or ''
            if v: print(v); break
        except: pass
" 2>/dev/null || echo "")

    WALLET=$(echo "${RESULT}" | python3 -c "
import sys, json
for line in reversed(sys.stdin.read().splitlines()):
    line = line.strip()
    if line.startswith('{'):
        try:
            d = json.loads(line)
            v = d.get('walletAddress') or ''
            if v: print(v); break
        except: pass
" 2>/dev/null || echo "")

    echo "  Agent ID : ${AGENT_ID}"
    echo "  Wallet   : ${WALLET}"
    echo ""

    cat >> "${SEED_SQL}" << SQLEOF
INSERT INTO public.agents (
    agent_id, name, role, purpose,
    evm_wallet, is_active, is_tokenized,
    signer_policy, daily_budget_usdc,
    max_job_price_usdc, jobs_per_hour,
    target_provider, notes
) VALUES (
    '${AGENT_ID}', '${NAME}', 'CLIENT',
    '${DESC}',
    '${WALLET}', true, false,
    'unrestricted', 10.0, 0.10, 10,
    '${CLONE_WALLET}',
    'Dedicated client. Created $(date -u +%Y-%m-%d). Hires CLONE exclusively.'
) ON CONFLICT (agent_id) DO NOTHING;
SQLEOF

    sleep 3
}

create_client \
    "iCLONE-Client-Research" \
    "Dedicated client for research and crypto analysis jobs. Hires iCLONE exclusively."

create_client \
    "iCLONE-Client-Content" \
    "Dedicated client for content creation and writing jobs. Hires iCLONE exclusively."

create_client \
    "iCLONE-Client-Code" \
    "Dedicated client for code and technical analysis jobs. Hires iCLONE exclusively."

echo "================================================"
echo "  Supabase seed SQL → ${SEED_SQL}"
echo "================================================"
cat "${SEED_SQL}"
echo ""
echo "Copia o SQL acima para o editor SQL do Supabase."
echo "Depois carrega \$50 USDC em cada wallet (Base mainnet)."
