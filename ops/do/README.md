# iCLONE — DigitalOcean Deploy Guide

Mac desligado. 4 agentes 24/7. $6/mês.

---

## Agentes criados (prontos)

| Agente | Role | Wallet | Estado |
|--------|------|--------|--------|
| CLONE | PROVIDER | `0x44cc25d55a4291b92f52062ba023ca1f14206664` | LIVE |
| SuperSayatin | CLIENT | `0x18f3aeadbad9c4b626c114ab14b89e586e4f6df3` | Aguarda $50 USDC |
| DoctorWHO | CLIENT | `0x875242eb5c91270ca80ed7753a87d6e22e4f5acf` | Aguarda $50 USDC |
| MATRIX | CLIENT | `0x07924dea2c8212969d5dc5655785aa5063adb2bc` | Aguarda $50 USDC |

---

## PASSO 1 — Criar conta + Droplet DigitalOcean

1. Vai a **digitalocean.com** → cria conta
2. **Create → Droplet**:
   - Image: **Ubuntu 22.04 LTS**
   - Plan: **Basic → Regular → $6/mês** (1 vCPU · 1 GB · 25 GB SSD)
   - Region: **Frankfurt (fra1)**
   - Auth: **SSH Key** — adiciona a tua chave pública (`cat ~/.ssh/id_rsa.pub`)
   - Hostname: `iclone-prod`
3. **Create Droplet** → aguarda 30s → **copia o IP**

---

## PASSO 2 — Setup do servidor (do Mac)

```bash
# Substituir pelo IP real
export DROPLET_IP="167.99.XX.XX"

# Instala Python 3.12, Node 20, acp-cli, ufw, fail2ban (~5 min)
scp /Users/alexaist1107397/Desktop/AI/iclone/ops/do/setup.sh root@$DROPLET_IP:/tmp/
ssh root@$DROPLET_IP 'bash /tmp/setup.sh'
```

No final: `✓ System setup complete.`

---

## PASSO 3 — Deploy do código (do Mac)

```bash
cd /Users/alexaist1107397/Desktop/AI/iclone
bash ops/do/deploy.sh $DROPLET_IP
```

Faz automaticamente:
- rsync código Mac → servidor
- Copia `.env` (chmod 600)
- Copia `~/.config/acp/config.json` (credenciais Privy dos 4 agentes)

---

## PASSO 4 — Auth acp-cli no servidor

```bash
ssh iclone@$DROPLET_IP 'bash /opt/iclone/ops/do/install.sh'
```

**Interactivo** — autentica 4 agentes em sequência:
- Para cada um: aparece uma URL → **abre no Mac browser** → login → selecciona o agente
- Ordem: CLONE → SuperSayatin → DoctorWHO → MATRIX

> Se o deploy.sh copiou o config.json com sucesso, este passo é mais rápido.

---

## PASSO 5 — Iniciar os 4 serviços (como root)

```bash
ssh root@$DROPLET_IP 'bash /opt/iclone/ops/do/start-services.sh'
```

Instala e arranca:
- `iclone-server` — CLONE provider (sempre activo)
- `iclone-supersayatin` — bootstrapper --agent supersayatin
- `iclone-doctorwho` — bootstrapper --agent doctorwho
- `iclone-matrix` — bootstrapper --agent matrix
- Cron de treino: **07:07 + 19:13 UTC** (2× por dia)

**✓ Mac pode ser desligado.**

---

## PASSO 6 — Funding ($200 USDC, Base mainnet)

Envia para cada wallet na rede **Base mainnet**:

| Agente | Wallet | Valor |
|--------|--------|-------|
| CLONE (buffer fees) | `0x44cc25d55a4291b92f52062ba023ca1f14206664` | $50 |
| SuperSayatin | `0x18f3aeadbad9c4b626c114ab14b89e586e4f6df3` | $50 |
| DoctorWHO | `0x875242eb5c91270ca80ed7753a87d6e22e4f5acf` | $50 |
| MATRIX | `0x07924dea2c8212969d5dc5655785aa5063adb2bc` | $50 |

Token USDC Base: `0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913`

---

## PASSO 7 — Supabase Migrations (SQL Editor)

Vai a: https://supabase.com/dashboard → projecto `drbvnmlwogdxlxfkvgtw` → SQL Editor

Executa por ordem:
1. Conteúdo de `supabase/migrations/001_agents_registry.sql`
2. Conteúdo de `supabase/migrations/002_client_agents_seed.sql`

---

## Verificação final

```bash
# Estado dos 4 serviços
ssh root@$DROPLET_IP 'systemctl status iclone-server iclone-supersayatin iclone-doctorwho iclone-matrix --no-pager'

# Logs em tempo real
ssh root@$DROPLET_IP 'tail -f /var/log/iclone/server.log'

# Ver cron de treino instalado
ssh root@$DROPLET_IP 'crontab -u iclone -l'
```

---

## Gestão contínua

```bash
# Actualizar código
cd /Users/alexaist1107397/Desktop/AI/iclone
bash ops/do/deploy.sh $DROPLET_IP
ssh root@$DROPLET_IP 'systemctl restart iclone-server iclone-supersayatin iclone-doctorwho iclone-matrix'

# Logs
ssh root@$DROPLET_IP 'tail -100 /var/log/iclone/server.log'
ssh root@$DROPLET_IP 'tail -100 /var/log/iclone/training.log'

# Parar/reiniciar individual
ssh root@$DROPLET_IP 'systemctl stop iclone-matrix'
ssh root@$DROPLET_IP 'systemctl restart iclone-server'
```

---

## Troubleshooting

| Problema | Solução |
|----------|---------|
| Serviço não arranca | `journalctl -u iclone-server -n 50` |
| acp auth falha no servidor | Repetir `acp configure` manualmente |
| Bootstrapper parado | Verificar saldo USDC dos clientes |
| Out of memory (1GB) | `free -m` → upgrade para $12/mês se necessário |
| RPC errors | Transientes — o SDK faz retry automático |

---

## Custos

| Item | Custo/mês |
|------|-----------|
| DO Droplet 1GB | $6 |
| Supabase free tier | $0 |
| Base RPC (Alchemy free) | $0 |
| **Total infra** | **$6/mês** |

---

*Actualizado: 2026-06-12 · Scripts prontos · Agentes criados · Aguarda IP do droplet*
