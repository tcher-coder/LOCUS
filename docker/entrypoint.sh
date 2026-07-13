#!/usr/bin/env bash
set -euo pipefail

VAULT=/app/vault

# Первый запуск: развернуть vault из шаблона (vault — bind-mount, живёт на хосте)
if [ ! -f "$VAULT/AGENTS.md" ]; then
    echo "[entrypoint] vault пуст — разворачиваю из vault.template"
    mkdir -p "$VAULT"
    cp -rn /app/vault.template/. "$VAULT/"
fi

# Git-идентичность и репозиторий vault (коммит после каждого ingest)
git config --global user.name  "LOCUS Agent"
git config --global user.email "locus@local"
git config --global --add safe.directory "$VAULT"
if [ ! -d "$VAULT/.git" ]; then
    echo "[entrypoint] git init в vault"
    git -C "$VAULT" init -q
    git -C "$VAULT" add -A
    git -C "$VAULT" commit -qm "Initial vault" || true
fi

echo "[entrypoint] запускаю LOCUS bridge"
exec python3 /app/bridge/main.py
