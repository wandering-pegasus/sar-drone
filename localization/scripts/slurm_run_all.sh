#!/usr/bin/env bash
# Run scripts/run_all.sh on a Slurm compute node (dedicated cores -> clean timing numbers).
# Install + download first ON THE LOGIN NODE (compute nodes have no internet).
# Usage: sbatch -A <your_account> scripts/slurm_run_all.sh [run_tag]
#    or: srun -p development -A <account> -c 16 -t 40 bash scripts/slurm_run_all.sh run1
#SBATCH --job-name=cs1-orbslam3
#SBATCH --partition=development
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=16
#SBATCH --time=00:40:00
#SBATCH --output=slurm-%j.log
set -euo pipefail
SLAM_DIR="${SLAM_DIR:-$HOME/slam}"
set +u; source "$SLAM_DIR/activate.sh"; set -u
cd "${SLURM_SUBMIT_DIR:-$(dirname "$0")/..}"
echo "node: $(hostname)"
bash scripts/run_all.sh "${1:-run1}"
