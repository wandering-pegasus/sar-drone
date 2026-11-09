#!/usr/bin/env bash
# Install ORB-SLAM3 (stereo-inertial, no ROS) on Ubuntu 22.04.
# Usage: bash scripts/setup_orbslam3.sh [install_dir]   (default: ~/slam)
set -euo pipefail

INSTALL_DIR="${1:-$HOME/slam}"
REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
ORB_COMMIT="4452a3c4ab75b1cde34e5505a36ec3f9edcdc4c4"   # UZ-SLAMLab/ORB_SLAM3 master, v1.0 (Feb 2022)
PANGOLIN_TAG="v0.8"
JOBS="${JOBS:-$(( $(nproc) > 1 ? $(nproc) - 1 : 1 ))}"

mkdir -p "$INSTALL_DIR"
cd "$INSTALL_DIR"

echo "==> [1/5] System packages"
sudo apt-get update
sudo apt-get install -y build-essential cmake git pkg-config \
    libeigen3-dev libopencv-dev libboost-serialization-dev libssl-dev \
    libgl1-mesa-dev libglew-dev libepoxy-dev libpython3-dev python3-pip

echo "==> [2/5] Pangolin $PANGOLIN_TAG"
if [ ! -d Pangolin ]; then
  git clone --recursive --branch "$PANGOLIN_TAG" https://github.com/stevenlovegrove/Pangolin.git
fi
cmake -S Pangolin -B Pangolin/build -DCMAKE_BUILD_TYPE=Release -DBUILD_EXAMPLES=OFF -DBUILD_TESTS=OFF
cmake --build Pangolin/build -j"$JOBS"
sudo cmake --install Pangolin/build
sudo ldconfig

echo "==> [3/5] ORB-SLAM3 source @ $ORB_COMMIT"
if [ ! -d ORB_SLAM3 ]; then
  git clone https://github.com/UZ-SLAMLab/ORB_SLAM3.git
fi
cd ORB_SLAM3
git checkout -q "$ORB_COMMIT"

echo "==> [4/5] Patches (build fixes + per-frame timing log)"
# Ubuntu 22.04 compilers need C++14 for this code base
sed -i 's/++11/++14/g' CMakeLists.txt
# make -j4 -> use our job count (ORB-SLAM3 build can run out of RAM with too many jobs)
sed -i "s/make -j4/make -j$JOBS/; s/^make -j$/make -j$JOBS/" build.sh
python3 "$REPO_DIR/scripts/patch_orbslam3_timing.py" Examples/Stereo-Inertial/stereo_inertial_euroc.cc
python3 "$REPO_DIR/scripts/patch_orbslam3_eventlog.py" .   # timestamps on VIBA / loop / merge prints (log only)

echo "==> [5/5] Build (takes 10-30 min)"
bash build.sh

BIN="$INSTALL_DIR/ORB_SLAM3/Examples/Stereo-Inertial/stereo_inertial_euroc"
if [ -x "$BIN" ]; then
  echo
  echo "OK: $BIN"
  echo "Next: export ORB_SLAM3_DIR=$INSTALL_DIR/ORB_SLAM3"
else
  echo "Build finished but binary not found: $BIN" >&2
  exit 1
fi
