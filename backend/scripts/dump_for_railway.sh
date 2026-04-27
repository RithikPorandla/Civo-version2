#!/usr/bin/env bash
# Dump local Civo DB for Railway import.
#
# Skips raw constraint layer data (flood_zones, wetlands, biomap, etc.)
# since those flags are already precomputed on the parcels table.
#
# Usage:
#   ./scripts/dump_for_railway.sh                      # dumps to civo_railway.dump
#   ./scripts/dump_for_railway.sh RAILWAY_DATABASE_URL # dumps + restores directly
#
# Estimated compressed size: 1.5–2.5 GB
# Estimated restore time on Railway: 10–20 min

set -euo pipefail

LOCAL_URL="${LOCAL_DATABASE_URL:-postgresql://civo:civo@localhost:5432/civo}"
DUMP_FILE="${DUMP_FILE:-civo_railway.dump}"
RAILWAY_URL="${1:-}"

# Tables whose DATA we skip — geometry already baked into parcels.flag_* columns
SKIP_DATA=(
  habitat_biomap_core
  habitat_biomap_cnl
  habitat_nhesp_priority
  habitat_nhesp_estimated
  flood_zones
  wetlands
  article97
  prime_farmland
)

echo "Building exclude flags..."
EXCLUDES=""
for tbl in "${SKIP_DATA[@]}"; do
  EXCLUDES="$EXCLUDES --exclude-table-data=$tbl"
done

echo "Dumping $LOCAL_URL → $DUMP_FILE"
echo "(skipping raw geometry data for: ${SKIP_DATA[*]})"
echo ""

pg_dump "$LOCAL_URL" \
  --format=custom \
  --compress=9 \
  --no-owner \
  --no-privileges \
  $EXCLUDES \
  --file="$DUMP_FILE"

SIZE=$(du -h "$DUMP_FILE" | cut -f1)
echo ""
echo "Dump complete: $DUMP_FILE ($SIZE)"

if [ -n "$RAILWAY_URL" ]; then
  echo ""
  echo "Restoring to Railway: $RAILWAY_URL"
  echo "(this takes 10–20 min on first run)"
  pg_restore \
    --dbname="$RAILWAY_URL" \
    --no-owner \
    --no-privileges \
    --jobs=4 \
    "$DUMP_FILE"
  echo "Restore complete."
else
  echo ""
  echo "To restore to Railway, run:"
  echo "  pg_restore --dbname=\"<RAILWAY_DATABASE_URL>\" --no-owner --no-privileges --jobs=4 $DUMP_FILE"
fi
