#!/bin/bash
# install-cron.sh — Installe le cron backup quotidien
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
BACKUP_SCRIPT="$SCRIPT_DIR/backup-db.sh"
CRON_LINE="0 3 * * * $BACKUP_SCRIPT >> /tmp/omnistudio-backup.log 2>&1"

# Verifier que le script existe
if [ ! -x "$BACKUP_SCRIPT" ]; then
    echo "[ERREUR] $BACKUP_SCRIPT introuvable ou non executable"
    exit 1
fi

# Verifier que mac-mini est accessible
if ! ssh -o ConnectTimeout=5 mac-mini "echo ok" >/dev/null 2>&1; then
    echo "[ERREUR] mac-mini non accessible via SSH (Tailscale actif ?)"
    exit 1
fi

# Ajouter le cron (sans dupliquer)
(crontab -l 2>/dev/null | grep -v "backup-db.sh"; echo "$CRON_LINE") | crontab -

echo "[OK] Cron backup installe : tous les jours a 3h"
echo "Verifier : crontab -l"
echo "Logs : /tmp/omnistudio-backup.log"
