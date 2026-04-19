#!/bin/bash
# restore-db.sh — Restaurer un backup checkpoint
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"
DB_TARGET="$ROOT_DIR/omnistudio/data/omnistudio_checkpoint.db"
BACKUP_HOST="mac-mini"
BACKUP_DIR="~/backups/omnistudio"

if [ -z "${1:-}" ]; then
    echo "Usage: ./restore-db.sh <date>"
    echo "Exemple: ./restore-db.sh 20260320-0300"
    echo ""
    echo "Backups disponibles :"
    ssh "$BACKUP_HOST" "ls -1t $BACKUP_DIR/checkpoint-*.db 2>/dev/null | head -10"
    exit 1
fi

DATE="$1"
REMOTE_FILE="$BACKUP_DIR/checkpoint-$DATE.db"

echo "Restauration de $REMOTE_FILE..."
echo "ATTENTION : le serveur OmniStudio doit etre arrete."
read -p "Continuer ? (o/N) " confirm
[ "$confirm" = "o" ] || exit 0

cp "$DB_TARGET" "$DB_TARGET.pre-restore" 2>/dev/null || true
rsync -az "$BACKUP_HOST:$REMOTE_FILE" "$DB_TARGET"

echo "[OK] Checkpoint restaure depuis $DATE"
echo "Redemarrer OmniStudio avec ./start.sh"
