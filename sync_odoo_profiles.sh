#!/bin/bash
# sync_odoo_profiles.sh
# Sincroniza archivos NO-symlink desde odoo/ (fuente de verdad) hacia odoo-nudo/ y odoo-resto/
# TOOLS.md y skills/erp/ YA son symlinks → no necesitan sincronización manual
#
# Uso: ./sync_odoo_profiles.sh [--dry-run]
#
# Archivos sincronizados: SOUL.md, AGENTS.md, CONSTANTS.md
# (TOOLS.md y skills/erp/ son symlinks y se actualizan automáticamente)

set -e
BASE="$(cd "$(dirname "$0")/app/hermes_profiles/contihome/profiles" && pwd)"
SOURCE="$BASE/odoo"
TARGETS="odoo-nudo odoo-resto"
FILES="SOUL.md AGENTS.md CONSTANTS.md"
DRY_RUN=false

[[ "${1:-}" == "--dry-run" ]] && DRY_RUN=true

echo "=== sync_odoo_profiles.sh ==="
echo "Fuente: $SOURCE"
echo "Destinos: $TARGETS"
echo "Archivos: $FILES"
[[ "$DRY_RUN" == true ]] && echo "(DRY RUN — sin cambios reales)"
echo ""

for TARGET in $TARGETS; do
  echo "--- Sincronizando → $TARGET ---"
  for FILE in $FILES; do
    SRC="$SOURCE/$FILE"
    DST="$BASE/$TARGET/$FILE"
    if [[ ! -f "$SRC" ]]; then
      echo "  ⚠️  Fuente no existe: $SRC (saltando)"
      continue
    fi
    if diff -q "$SRC" "$DST" &>/dev/null 2>&1; then
      echo "  ✅ Sin cambios: $FILE"
    else
      if [[ "$DRY_RUN" == true ]]; then
        echo "  🔄 CAMBIARÍA: $FILE"
      else
        cp "$SRC" "$DST"
        echo "  🔄 Actualizado: $FILE"
      fi
    fi
  done
done

echo ""
echo "Nota: TOOLS.md y skills/erp/ son symlinks → se actualizan automáticamente."
echo "Listo."
