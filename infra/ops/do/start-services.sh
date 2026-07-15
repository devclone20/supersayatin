#!/bin/bash
# iCLONE — Install systemd services and start everything
# Run as root on the droplet
set -euo pipefail

ICLONE_DIR="/opt/iclone"
SYSTEMD_DIR="/etc/systemd/system"

echo "── Installing systemd services ──────────────────"
cp ${ICLONE_DIR}/ops/systemd/iclone-server.service        ${SYSTEMD_DIR}/
cp ${ICLONE_DIR}/ops/systemd/iclone-supersayatin.service  ${SYSTEMD_DIR}/
cp ${ICLONE_DIR}/ops/systemd/iclone-doctorwho.service     ${SYSTEMD_DIR}/
cp ${ICLONE_DIR}/ops/systemd/iclone-matrix.service        ${SYSTEMD_DIR}/

echo "── Installing logrotate ─────────────────────────"
cp ${ICLONE_DIR}/ops/systemd/iclone-logrotate.conf /etc/logrotate.d/iclone

echo "── Enabling services ────────────────────────────"
systemctl daemon-reload
systemctl enable iclone-server
systemctl enable iclone-supersayatin
systemctl enable iclone-doctorwho
systemctl enable iclone-matrix

echo "── Starting services ────────────────────────────"
systemctl start iclone-server
sleep 5
# Stagger client starts to avoid simultaneous acp-cli agent switching
systemctl start iclone-supersayatin
sleep 10
systemctl start iclone-doctorwho
sleep 10
systemctl start iclone-matrix

echo ""
echo "── Status ───────────────────────────────────────"
for svc in iclone-server iclone-supersayatin iclone-doctorwho iclone-matrix; do
    systemctl status ${svc} --no-pager -l | head -5
    echo ""
done

echo "── Instalando cron de treino (2× por dia) ───────"
# Training cron para iclone user: 08:07 e 20:13 Lisboa (UTC+1)
(crontab -u iclone -l 2>/dev/null | grep -v 'iclone.*training'; cat <<'CRONEOF'
# iCLONE — Daily Training 2× dia
7 7 * * * cd /opt/iclone && venv312/bin/python3 -m agent.iclone.training.scheduler >> /var/log/iclone/training.log 2>&1
13 19 * * * cd /opt/iclone && venv312/bin/python3 -m agent.iclone.training.scheduler >> /var/log/iclone/training.log 2>&1
CRONEOF
) | crontab -u iclone -
echo "✓ Cron de treino instalado (07:07 + 19:13 UTC)"

echo ""
echo "================================================"
echo "  ✓ 4 serviços a correr 24/7. Mac pode ser desligado."
echo "================================================"
echo ""
echo "Comandos úteis:"
echo "  tail -f /var/log/iclone/server.log"
echo "  tail -f /var/log/iclone/supersayatin.log"
echo "  tail -f /var/log/iclone/doctorwho.log"
echo "  tail -f /var/log/iclone/matrix.log"
echo "  tail -f /var/log/iclone/training.log"
echo ""
echo "  systemctl status iclone-server"
echo "  systemctl restart iclone-server"
echo "  systemctl stop iclone-supersayatin"
echo ""
echo "  journalctl -u iclone-server -f    # logs em tempo real"
