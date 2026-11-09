#!/usr/bin/env bash
# Download EuRoC MAV sequences in ASL format (image folders + CSV), as used by ORB-SLAM3.
# Usage: bash scripts/download_euroc.sh [data_dir] [sequences...]   (default: ~/datasets/euroc MH_01_easy V1_01_easy)
#
# Sources, tried in order:
#   1. Old ETH server robotics.ethz.ch  (offline since 2025; kept in case it returns)
#   2. Hugging Face mirror GlowBond/EuRoC_MAV_Dataset: the original per-sequence
#      ASL zips, nested inside machine_hall.zip / vicon_room1.zip. Only the one
#      member we need (~1.5 GB) is fetched with HTTP range requests, and its
#      CRC-32 is checked against the archive's directory.
# Official home today: ETH Research Collection, doi:10.3929/ethz-b-000690084
# (rate-limits scripted downloads; use a browser if you want it from there and put
#  <seq>.zip in data_dir, the script then only unzips).
set -euo pipefail

DATA_DIR="${1:-$HOME/datasets/euroc}"
REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
OLD_BASE="http://robotics.ethz.ch/~asl-datasets/ijrr_euroc_mav_dataset"
HF_BASE="https://huggingface.co/datasets/GlowBond/EuRoC_MAV_Dataset/resolve/main"
declare -A GROUP=( [MH_01_easy]="machine_hall" [V1_01_easy]="vicon_room1" [MH_04_difficult]="machine_hall" )
# expected frame counts (cam0) for a quick integrity check
declare -A FRAMES=( [MH_01_easy]=3682 [V1_01_easy]=2912 [MH_04_difficult]=2033 )

mkdir -p "$DATA_DIR"
cd "$DATA_DIR"
SEQS=("${@:2}"); [ ${#SEQS[@]} -eq 0 ] && SEQS=(MH_01_easy V1_01_easy)
for seq in "${SEQS[@]}"; do
  g="${GROUP[$seq]}"
  if [ -f "$seq/mav0/state_groundtruth_estimate0/data.csv" ]; then
    echo "skip $seq (already extracted)"; continue
  fi
  if [ ! -f "$seq.zip" ]; then
    echo "==> $seq: trying ETH server"
    if ! wget -q --timeout=15 --tries=1 "$OLD_BASE/$g/$seq/$seq.zip" -O "$seq.zip"; then
      rm -f "$seq.zip"
      echo "==> $seq: ETH server down, using Hugging Face mirror (CRC-checked)"
      python3 -I "$REPO_DIR/scripts/remotezip_get.py" "$HF_BASE/$g.zip" "$g/$seq/$seq.zip" "$seq.zip.part" \
        | tee "$seq.download.log"
      grep -q "crc OK" "$seq.download.log" || { echo "CRC mismatch for $seq" >&2; exit 1; }
      mv "$seq.zip.part" "$seq.zip"
    fi
  fi
  mkdir -p "$seq" && unzip -q -o "$seq.zip" -d "$seq" && rm -rf "$seq/__MACOSX"
  n=$(ls "$seq/mav0/cam0/data" | wc -l)
  [ "$n" -eq "${FRAMES[$seq]}" ] || { echo "$seq: $n frames, expected ${FRAMES[$seq]}" >&2; exit 1; }
  echo "OK $seq ($n stereo frames)"
done
echo "Data in $DATA_DIR   ->  export EUROC_DIR=$DATA_DIR"
