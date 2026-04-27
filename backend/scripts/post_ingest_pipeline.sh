#!/usr/bin/env bash
# Post-statewide-ingest pipeline — runs after ingest_statewide completes.
# Run from v2/backend with .venv active.
set -euo pipefail

LOG_DIR=/tmp/civo_pipeline
mkdir -p "$LOG_DIR"

echo "====================================================="
echo " Civo post-ingest pipeline — $(date)"
echo "====================================================="

# 1. Precompute constraint flags for all towns
echo ""
echo "[1/4] Precomputing constraint flags..."
python -u -m scripts.precompute_flags --workers 4 2>&1 | tee "$LOG_DIR/precompute_flags.log"
echo "  Done."

# 2. Batch score all new eligible parcels (skip already scored)
echo ""
echo "[2/4] Batch scoring eligible parcels (>=2 acres)..."
python -u -m scripts.batch_score --workers 4 2>&1 | tee "$LOG_DIR/batch_score.log"
echo "  Done."

# 3. Extract ML features for all towns
echo ""
echo "[3/4] Extracting ML features..."
python -u -m scripts.extract_ml_features --workers 4 2>&1 | tee "$LOG_DIR/ml_features.log"
echo "  Done."

# 4. Assign solar irradiance to new parcels
echo ""
echo "[3b] Assigning solar irradiance to new parcels..."
python -u -m ingest.nrel_irradiance 2>&1 | tee "$LOG_DIR/irradiance.log"
echo "  Done."

# 5. Retrain ML ranker on full dataset
echo ""
echo "[4/4] Training ML ranker..."
python -u -m scripts.train_ranker 2>&1 | tee "$LOG_DIR/train_ranker.log"
echo "  Done."

echo ""
echo "====================================================="
echo " Pipeline complete — $(date)"
echo " Logs: $LOG_DIR"
echo "====================================================="
