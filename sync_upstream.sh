#!/bin/bash

# Script para sincronizar conti-backend con orquestador-contamela
# Uso: ./sync_upstream.sh

set -euo pipefail

cd /contenedores/conti-backend

echo "🔄 Sincronizando con orquestador-contamela...
"

# Fetch y merge con upstream/main
git fetch upstream
git merge upstream/main --no-ff -m "sync: sincronizar con orquestador-contamela"

# Push a upstream/main
git push upstream main

echo "✅ Sincronización completada. Último commit:"
git log --oneline upstream/main -1