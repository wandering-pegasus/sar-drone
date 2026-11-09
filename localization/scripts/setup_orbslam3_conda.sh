#!/usr/bin/env bash
# Install ORB-SLAM3 (stereo-inertial, no ROS) WITHOUT root, using micromamba + conda-forge.
# Use this on HPC / lab machines (tested: NCHC, RHEL 8.7, no sudo, no fakeroot).
# On your own Ubuntu 22.04 laptop with sudo, scripts/setup_orbslam3.sh also works.
#
# Usage: bash scripts/setup_orbslam3_conda.sh [install_dir]   (default: ~/slam)
# Then:  source <install_dir>/activate.sh   (in every new shell / Slurm job)
set -euo pipefail

INSTALL_DIR="$(mkdir -p "${1:-$HOME/slam}" && cd "${1:-$HOME/slam}" && pwd)"
REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
ORB_COMMIT="4452a3c4ab75b1cde34e5505a36ec3f9edcdc4c4"   # UZ-SLAMLab/ORB_SLAM3 v1.0
PANGOLIN_TAG="v0.8"
MAMBA_VER="2.0.5-0"
JOBS="${JOBS:-16}"
cd "$INSTALL_DIR"

echo "==> [1/6] micromamba $MAMBA_VER"
mkdir -p bin
[ -x bin/micromamba ] || {
  curl -sL "https://github.com/mamba-org/micromamba-releases/releases/download/$MAMBA_VER/micromamba-linux-64" -o bin/micromamba
  chmod +x bin/micromamba; }

echo "==> [2/6] conda env (OpenCV 4, Eigen 3.4, Boost, GLEW, GCC 11, Python 3.11)"
export MAMBA_ROOT_PREFIX="$INSTALL_DIR/mamba"
# Pins matter: unpinned conda-forge gives OpenCV 5 + GCC 15, which ORB-SLAM3 does not build with.
[ -d env ] || bin/micromamba create -y -p "$INSTALL_DIR/env" -c conda-forge --override-channels \
  python=3.11 cmake make pkg-config "eigen=3.4" "libopencv>=4.5,<5" libboost-devel \
  glew libglu xorg-libx11 xorg-libxext "gxx_linux-64=11.*" "gcc_linux-64=11.*" numpy matplotlib

cat > activate.sh <<EOF
# source $INSTALL_DIR/activate.sh  -> toolchain + libs for ORB-SLAM3 and evo
export MAMBA_ROOT_PREFIX=$INSTALL_DIR/mamba
eval "\$($INSTALL_DIR/bin/micromamba shell hook -s bash)"
micromamba activate $INSTALL_DIR/env
export CMAKE_PREFIX_PATH=$INSTALL_DIR/local:\$CONDA_PREFIX
export LD_LIBRARY_PATH=$INSTALL_DIR/local/lib:\$CONDA_PREFIX/lib:\${LD_LIBRARY_PATH:-}
export CMAKE_POLICY_VERSION_MINIMUM=3.5   # CMake 4 rejects ORB-SLAM3's old cmake_minimum_required
export ORB_SLAM3_DIR=$INSTALL_DIR/ORB_SLAM3
EOF
set +u; source activate.sh; set -u
pip install -q -r "$REPO_DIR/requirements.txt"

echo "==> [3/6] Pangolin $PANGOLIN_TAG -> $INSTALL_DIR/local"
[ -d Pangolin ] || git clone -q --recursive --branch "$PANGOLIN_TAG" https://github.com/stevenlovegrove/Pangolin.git
cmake -S Pangolin -B Pangolin/build -DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_PREFIX="$INSTALL_DIR/local" \
  -DBUILD_EXAMPLES=OFF -DBUILD_TESTS=OFF -DBUILD_TOOLS=OFF -DBUILD_PANGOLIN_PYTHON=OFF \
  -DBUILD_PANGOLIN_FFMPEG=OFF -DBUILD_PANGOLIN_LIBREALSENSE=OFF -DBUILD_PANGOLIN_LIBREALSENSE2=OFF >/dev/null
cmake --build Pangolin/build -j"$JOBS" >/dev/null
cmake --install Pangolin/build >/dev/null

echo "==> [4/6] ORB-SLAM3 @ $ORB_COMMIT"
[ -d ORB_SLAM3 ] || git clone -q https://github.com/UZ-SLAMLab/ORB_SLAM3.git
cd ORB_SLAM3
git checkout -q "$ORB_COMMIT"

echo "==> [5/6] Patches (build only + per-frame timing log; algorithm unchanged)"
sed -i 's/++11/++14/g' CMakeLists.txt
sed -i "s/make -j4/make -j$JOBS/; s/^make -j\$/make -j$JOBS/" build.sh
python3 "$REPO_DIR/scripts/patch_orbslam3_timing.py" Examples/Stereo-Inertial/stereo_inertial_euroc.cc
python3 "$REPO_DIR/scripts/patch_orbslam3_eventlog.py" .   # timestamps on VIBA / loop / merge prints (log only)
[ -f Vocabulary/ORBvoc.txt ] || tar -xzf Vocabulary/ORBvoc.txt.tar.gz -C Vocabulary

echo "==> [6/6] Build (~5 min with 16 jobs)"
bash build.sh > "$INSTALL_DIR/orb_build.log" 2>&1 || { tail -30 "$INSTALL_DIR/orb_build.log"; exit 1; }

BIN="$INSTALL_DIR/ORB_SLAM3/Examples/Stereo-Inertial/stereo_inertial_euroc"
[ -x "$BIN" ] && echo "OK: $BIN" && echo "Next: source $INSTALL_DIR/activate.sh"
