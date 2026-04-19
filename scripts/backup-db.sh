#!/bin/bash
# backup-db.sh — Backup quotidien (checkpoint SQLite + sessions + Keycloak H2)
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"
DB_SOURCE="$ROOT_DIR/omnistudio/data/omnistudio_checkpoint.db"
SESSIONS_SOURCE="$ROOT_DIR/omnistudio/data/omnistudio_dsfr_sessions.db"
KEYCLOAK_DIR="$HOME/Claude/keycloak"

BACKUP_HOST="mac-mini"
BACKUP_DIR="~/backups/omnistudio"
DATE=$(date +%Y%m%d-%H%M)

if [ ! -f "$DB_SOURCE" ]; then
    echo "[ERREUR] $DB_SOURCE introuvable"
    exit 1
fi

ssh "$BACKUP_HOST" "mkdir -p $BACKUP_DIR"

TEMP_BACKUP="/tmp/omnistudio_checkpoint_backup.db"
sqlite3 "$DB_SOURCE" ".backup '$TEMP_BACKUP'"

rsync -az "$TEMP_BACKUP" "$BACKUP_HOST:$BACKUP_DIR/checkpoint-$DATE.db"
rsync -az "$SESSIONS_SOURCE" "$BACKUP_HOST:$BACKUP_DIR/sessions-$DATE.db" 2>/dev/null || true

rm -f "$TEMP_BACKUP"

# Backup Keycloak H2 (realm harmonia, utilisateurs, config)
KEYCLOAK_CONTAINER="keycloak-keycloak-1"
if docker ps --format '{{.Names}}' 2>/dev/null | grep -q "$KEYCLOAK_CONTAINER"; then
    TEMP_H2="/tmp/keycloak_h2_backup.tar.gz"
    docker cp "$KEYCLOAK_CONTAINER:/opt/keycloak/data/h2" - 2>/dev/null | gzip > "$TEMP_H2"
    rsync -az "$TEMP_H2" "$BACKUP_HOST:$BACKUP_DIR/keycloak-h2-$DATE.tar.gz"
    rm -f "$TEMP_H2"
    echo "[OK] Keycloak H2 sauvegarde"
else
    echo "[WARN] Conteneur $KEYCLOAK_CONTAINER non actif, backup H2 ignore"
fi

# Retention : garder 30 derniers backups par type
ssh "$BACKUP_HOST" "ls -t $BACKUP_DIR/checkpoint-*.db 2>/dev/null | tail -n +31 | xargs rm -f 2>/dev/null || true"
ssh "$BACKUP_HOST" "ls -t $BACKUP_DIR/sessions-*.db 2>/dev/null | tail -n +31 | xargs rm -f 2>/dev/null || true"
ssh "$BACKUP_HOST" "ls -t $BACKUP_DIR/keycloak-h2-*.tar.gz 2>/dev/null | tail -n +31 | xargs rm -f 2>/dev/null || true"

echo "[OK] Backup $DATE envoye sur $BACKUP_HOST:$BACKUP_DIR"
