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

# Дать пользователю locus права на vault и data
chown -R locus:locus "$VAULT" /app/data 2>/dev/null || true
mkdir -p /app/data && chown locus:locus /app/data

# Скопировать git config для пользователя locus
cp /root/.gitconfig /home/locus/.gitconfig 2>/dev/null || true
chown locus:locus /home/locus/.gitconfig 2>/dev/null || true

echo "[entrypoint] запускаю LOCUS bridge (user=locus)"
exec gosu locus python3 /app/bridge/main.py
