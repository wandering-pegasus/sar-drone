#!/usr/bin/env bash
# Run + evaluate both sequences, then build results/summary.md.
# Usage: bash scripts/run_all.sh [run_tag]     (run1 = main result; run2 = repeatability check)
set -euo pipefail
TAG="${1:-run1}"
REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_DIR"
for seq in MH_01_easy V1_01_easy; do
  bash scripts/run_orbslam3.sh "$seq" "$TAG"
  python3 eval/evaluate.py --seq "$seq" --run "runs/$seq/$TAG" --tag "$TAG"
done
python3 eval/make_summary.py
