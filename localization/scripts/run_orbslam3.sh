#!/usr/bin/env bash
# Run ORB-SLAM3 stereo-inertial on one EuRoC sequence with the DEFAULT config.
# Usage: bash scripts/run_orbslam3.sh <MH_01_easy|V1_01_easy|MH_04_difficult> [run_tag]
# Env:   ORB_SLAM3_DIR (default ~/slam/ORB_SLAM3), EUROC_DIR (default ~/datasets/euroc)
#        ORB_CFG   optional settings file instead of the default EuRoC.yaml
#                  (only used for configs/EuRoC_noLC.yaml = default + loop closure off)
# Output: runs/<seq>/<run_tag>/{f_*.txt, kf_*.txt, times_*.txt, log.txt, machine.txt}
set -euo pipefail

SEQ="${1:?usage: run_orbslam3.sh <sequence> [run_tag]}"
TAG="${2:-run1}"
ORB="${ORB_SLAM3_DIR:-$HOME/slam/ORB_SLAM3}"
EUROC="${EUROC_DIR:-$HOME/datasets/euroc}"
REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"

case "$SEQ" in
  MH_01_easy) TS=MH01 ;;
  V1_01_easy) TS=V101 ;;
  MH_04_difficult) TS=MH04 ;;
  *) echo "unknown sequence $SEQ" >&2; exit 1 ;;
esac

BIN="$ORB/Examples/Stereo-Inertial/stereo_inertial_euroc"
VOC="$ORB/Vocabulary/ORBvoc.txt"
CFG="${ORB_CFG:-$ORB/Examples/Stereo-Inertial/EuRoC.yaml}"
TIMES="$ORB/Examples/Stereo-Inertial/EuRoC_TimeStamps/$TS.txt"
DATA="$EUROC/$SEQ"
for f in "$BIN" "$VOC" "$CFG" "$TIMES" "$DATA/mav0/cam0/data.csv"; do
  [ -e "$f" ] || { echo "missing: $f" >&2; exit 1; }
done

OUT="$REPO_DIR/runs/$SEQ/$TAG"
mkdir -p "$OUT"
cd "$OUT"

# Record machine + versions next to the numbers (required by the task rules)
{
  echo "date: $(date -Iseconds)"
  echo "algorithm: ORB-SLAM3 stereo-inertial"
  echo "config: $CFG"
  echo "config_sha1: $(sha1sum "$CFG" | cut -c1-12)"
  echo "orbslam3_commit: $(git -C "$ORB" rev-parse HEAD)"
  echo "cpu: $(lscpu | sed -n 's/^Model name:[[:space:]]*//p' | head -1)"
  echo "cores: $(nproc)"
  echo "ram: $(free -h | awk '/^Mem:/{print $2}')"
  echo "gpu: $(command -v nvidia-smi >/dev/null && nvidia-smi --query-gpu=name --format=csv,noheader | head -1 || echo 'none (ORB-SLAM3 is CPU-only)')"
  echo "os: $(. /etc/os-release; echo "$PRETTY_NAME")"
} > machine.txt
cat machine.txt

NAME="${SEQ}_${TAG}"
echo "==> running ORB-SLAM3 on $SEQ (plays at real-time speed, ~3 min)"
"$BIN" "$VOC" "$CFG" "$DATA" "$TIMES" "$NAME" 2>&1 | tee log.txt

[ -f "f_$NAME.txt" ] || { echo "no trajectory written" >&2; exit 1; }
MAPS=$(grep -o "There are [0-9]* maps" log.txt | tail -1 | grep -o "[0-9]*" || echo "?")
echo
echo "trajectory: $OUT/f_$NAME.txt"
echo "maps in atlas: $MAPS   (1 = no tracking loss; >1 = tracking was lost and a new map started)"
