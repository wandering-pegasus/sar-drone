# localization (CS1): VI-SLAM on EuRoC

Owner: Kevin. Part of the team repo `sar-drone`; everything below runs from this folder.

Runs **ORB-SLAM3 (stereo-inertial, default config)** on two EuRoC MAV sequences
(`MH_01_easy`, `V1_01_easy`) and computes the metrics promised in the plan:
ATE (SE(3)-aligned RMSE), RPE over 1 m, drift % of distance, and per-frame
processing time (mean, p95). Everything below reruns from a clean Ubuntu 22.04
machine; no ROS, drone or camera needed.

Owner: Kevin (CS1). Results go to Thu Hang by **12:00, Sun 8 Nov 2026**.

## Why ORB-SLAM3

Runs without ROS, ships EuRoC examples, and is a standard VI-SLAM baseline.
The task sheet allows it as the fallback if ROS 2 installation stalls; it is
used here from the start to secure numbers before the Wednesday checkpoint.
An OpenVINS (ROS 2) run can be added later with the same evaluation scripts
(`evaluate.py --est <file> --est-format tum`).

## Layout

```
scripts/setup_orbslam3_conda.sh  install without root (micromamba): Pangolin + ORB-SLAM3 + evo
scripts/setup_orbslam3.sh        install on Ubuntu 22.04 with sudo (apt)
scripts/patch_orbslam3_timing.py make the EuRoC example save per-frame tracking time + tracking state
scripts/download_euroc.sh        download MH_01_easy, V1_01_easy (ASL format, CRC-checked)
scripts/remotezip_get.py         extract one file from a remote zip (used by download_euroc.sh)
scripts/slurm_run_all.sh         run_all.sh on a Slurm compute node
scripts/run_orbslam3.sh          run one sequence, save trajectory + times + machine info
scripts/run_all.sh               run + evaluate both sequences, build summary.md
eval/evaluate.py                 TUM conversion, evo_ape / evo_rpe, drift, timing, figure
eval/make_summary.py             results/summary.md table
eval/plot_struggle.py            where tracking struggles: error / state / brightness / motion vs time
configs/EuRoC_noLC.yaml          default EuRoC.yaml + `loopClosing: 0` (only change)
docs/jetson_latency_sources.md   published VIO latency on Jetson (sources for the 38 ms target)
docs/ros2_interfaces.md          ROS 2 nodes/topics D435i -> VIO -> PX4 (for the system diagram)
results/extra/                   Round 2 follow-up: MH_04_difficult, no-loop-closure runs
gt/V1_01_easy_openvins_corrected.tum   corrected ground truth for V1_01 (see below)
results/                         deliverables (committed)
runs/                            raw run outputs (logs, trajectories, times)
```

## Results (run1, 4 Nov 2026)

| Sequence | ATE RMSE (m) | RPE 1 m (m) | Length (m) | Drift (%) | Mean / p95 per frame (ms) |
|---|---|---|---|---|---|
| MH_01_easy | 0.039 | 0.020 | 80.5 | 0.06 | 37.8 / 48.7 |
| V1_01_easy | 0.022 | 0.014 | 58.3 | 0.04 | 37.1 / 47.7 |

Machine: Intel Xeon Platinum 8480+, 16 cores allocated (Slurm), no GPU, RHEL 8.7.
No tracking loss (1 map). run2 gives similar numbers; see `results/summary.md`.
For reference, the ORB-SLAM3 paper reports 0.036 m (MH_01) and 0.035 m (V1_01) for stereo-inertial.

## 1. Install (once)

### Option A: no root (HPC / lab server). This is what produced the results above

Works on any x86-64 Linux, with no sudo and no container. About 15 minutes.
On a cluster, run setup and the data download **on the login node**. Compute nodes
usually have no internet access (on NCHC they don't). Only the SLAM runs go to compute nodes.

```bash
git clone https://github.com/wandering-pegasus/sar-drone.git && cd sar-drone/localization
bash scripts/setup_orbslam3_conda.sh ~/slam   # micromamba env + Pangolin v0.8 + ORB-SLAM3 @ 4452a3c
source ~/slam/activate.sh                      # every new shell / job; sets ORB_SLAM3_DIR
```

Tested versions: conda-forge GCC 11.4, OpenCV 4.x, Eigen 3.4, CMake 4, Python 3.11, evo 1.31.1.
Two pitfalls the script handles: unpinned conda-forge gives OpenCV 5 / GCC 15
(ORB-SLAM3 does not build with them), and CMake 4 needs `CMAKE_POLICY_VERSION_MINIMUM=3.5`.

### Option B: Ubuntu 22.04 with sudo

About 8 GB free RAM for the build.

```bash
git clone https://github.com/wandering-pegasus/sar-drone.git && cd sar-drone/localization
pip install -r requirements.txt          # evo, numpy, matplotlib
bash scripts/setup_orbslam3.sh ~/slam    # Pangolin v0.8 + ORB-SLAM3 @ 4452a3c
export ORB_SLAM3_DIR=~/slam/ORB_SLAM3
```

What the setup script changes in ORB-SLAM3 (nothing algorithmic):
- `-std=c++11` → `-std=c++14` (needed to compile on Ubuntu 22.04).
- `stereo_inertial_euroc.cc` additionally writes `times_<run>.txt`: the time of
  each `TrackStereo()` call, which ORB-SLAM3 already measures but never saves. It also writes
  `states_<run>.txt` (tracking state per frame) and `online_<run>.txt` (the pose `TrackStereo()`
  returned at that frame, i.e. what would go to PX4).
- `src/LocalMapping.cc`, `src/LoopClosing.cc`: the existing "end VIBA 1/2", "*Loop detected" and
  "*Merge detected" prints get the keyframe timestamp appended (`patch_orbslam3_eventlog.py`).
  Text of the prints only.

If the build is killed (out of memory), rerun with fewer jobs: `JOBS=2 bash scripts/setup_orbslam3.sh ~/slam`.

## 2. Download data (~2.7 GB zips, 7 GB unpacked)

```bash
bash scripts/download_euroc.sh ~/datasets/euroc
export EUROC_DIR=~/datasets/euroc
```

The old ETH server (`robotics.ethz.ch`) has been offline since the dataset moved to the
[ETH Research Collection](https://doi.org/10.3929/ethz-b-000690084), which rate-limits
scripted downloads. The script therefore falls back to the Hugging Face mirror
`GlowBond/EuRoC_MAV_Dataset`. It fetches only the original per-sequence ASL zip from
inside the big archive (HTTP range requests, `scripts/remotezip_get.py`), checks its
CRC-32, then checks the frame count (MH_01: 3682, V1_01: 2912). The V1_01 zip was also
cross-checked against a second mirror (`pepijn223/euroc-mirror`): identical CRC
`0x1abe6a0d` and size. If you download the zips by hand, put `<seq>.zip` in the data
folder and the script only unzips them.

## 3. Run and evaluate

```bash
bash scripts/run_all.sh run1     # main result  -> results/
bash scripts/run_all.sh run2     # repeatability -> results/<seq>/reruns/run2/
```

Each sequence plays at real-time speed (~3 min). On a Slurm cluster, run it on a
compute node so the timing is not disturbed by other users on the login node:

```bash
srun -p development -A <account> -c 16 -t 40 bash scripts/slurm_run_all.sh run1
# or: sbatch -A <account> scripts/slurm_run_all.sh run1
```

Or step by step:

```bash
bash scripts/run_orbslam3.sh MH_01_easy run1
python3 eval/evaluate.py --seq MH_01_easy --run runs/MH_01_easy/run1
python3 eval/make_summary.py
```

## Round 2 follow-up (8 Nov): hard sequence and no loop closure

```bash
bash scripts/download_euroc.sh ~/datasets/euroc MH_04_difficult   # third sequence, same checks
bash scripts/run_orbslam3.sh MH_04_difficult run1                  # default config
for s in MH_01_easy V1_01_easy MH_04_difficult; do                 # loop closure off
  ORB_CFG=$PWD/configs/EuRoC_noLC.yaml bash scripts/run_orbslam3.sh $s noLC
done
# evaluate into results/extra/ (keeps the Round 2 deliverables untouched)
python3 eval/evaluate.py --seq MH_04_difficult --run runs/MH_04_difficult/run1 --outdir results/extra/MH_04_difficult
python3 eval/evaluate.py --seq MH_01_easy --run runs/MH_01_easy/noLC --tag noLC --outdir results/extra/noLC/MH_01_easy
python3 eval/plot_struggle.py --seq MH_04_difficult --run runs/MH_04_difficult/diag --outdir results/extra/MH_04_difficult
# online pose (needs the diag runs: same commands with tags diag / noLC_diag)
python3 eval/evaluate_online.py --seq MH_04_difficult --run runs/MH_04_difficult/noLC_diag \
    --outdir results/extra/online/MH_04_difficult_noLC --label "loop closure off"
python3 eval/make_extra_summary.py          # -> results/extra/summary.md
```

`evaluate.py` also reports:
- **start-aligned drift**: the SE(3) alignment uses only the first 5 m of path, then the final error is taken. This is
  closer to a real flight, where the start pose is known (AprilTag) and nothing corrects the end.
- **coverage**: the share of the sequence covered by the saved trajectory. ORB-SLAM3 saves only its largest map, so
  tracking loss shows up as coverage < 100 %.

## Output (per sequence)

| File | Content |
|---|---|
| `est.tum` | estimated trajectory, TUM format, seconds |
| `gt.tum` | ground truth actually used (regenerated by `evaluate.py`, not committed) |
| `ate.zip`, `ate.txt` | `evo_ape tum gt.tum est.tum -a` |
| `rpe.txt` | `evo_rpe tum gt.tum est.tum -a --delta 1 --delta_unit m` (translation) |
| `traj.png` | estimate (aligned) over ground truth, top view, metres |
| `metrics.json` | all numbers, source files, machine info |

Plus `results/summary.md` (table) and `results/writeup.md` (paragraph for the plan).

## Metric definitions

- **ATE**: RMSE of translation error after SE(3) Umeyama alignment of the whole
  trajectory (rotation + translation, **no scale**: stereo + IMU has metric scale).
- **RPE 1 m**: RMSE of translation error over consecutive 1 m segments.
- **Drift %** = ‖final position error after alignment‖ / ground-truth path length × 100.
  Path length is computed on the time-matched ground-truth poses.
- **Time/frame**: wall-clock time of `TrackStereo()` per stereo pair on the
  tracking thread. Local mapping and loop closing run in parallel threads and are
  not included. This is *processing time*, not the end-to-end capture→PX4
  latency of the final target (that is measured on the Jetson in Phase 1).

## Ground truth notes

- `MH_01_easy`: `mav0/state_groundtruth_estimate0/data.csv`, converted to TUM
  (EuRoC stores `qw qx qy qz`; TUM needs `qx qy qz qw`, the script reorders).
- `V1_01_easy`: the OpenVINS docs warn that the original ground truth on this
  sequence has an inaccurate orientation estimate. We use their recomputed
  trajectory (vicon2gt), copied from
  `rpng/open_vins/ov_data/euroc_mav/V1_01_easy.txt` (commit `69488123`).
  To compare with the original: `--gt $EUROC_DIR/V1_01_easy/mav0/state_groundtruth_estimate0/data.csv`.
  Measured on our run1 trajectory: against the original ground truth, ATE is 0.038 m and the
  rotation error is 5.5° RMSE. Against the corrected one, ATE is 0.022 m and the rotation
  error is 0.43°. The 5.5° is the known ground-truth orientation problem, not a VIO error.
- ORB-SLAM3's stereo-inertial output is the IMU body pose, the same frame as the
  EuRoC ground truth, so no extra extrinsic transform is applied.

## Rules followed

- Default `Examples/Stereo-Inertial/EuRoC.yaml`, no per-sequence tuning.
- Algorithm commit and machine specs are saved in `runs/<seq>/<tag>/machine.txt`
  and copied into `metrics.json` / `summary.md`.

## Sanity checks (printed by `evaluate.py`)

- ATE > 0.5 m → setup error (timestamp units, frames, missing `-a`).
- Estimated vs ground-truth length differ > 10 % → scale problem.
- More than 1 map in the ORB-SLAM3 atlas → tracking was lost at least once.
- Also check by eye: `traj.png` curves overlap; `run2` numbers close to `run1`.

## Troubleshooting

| Symptom | Fix |
|---|---|
| `Pangolin` not found at cmake | `sudo ldconfig`, check `/usr/local/lib/cmake/Pangolin` |
| build killed / `c++: fatal error: Killed` | `JOBS=1` and add swap |
| `Failed to load image` | `EUROC_DIR` must contain `<seq>/mav0/cam0/data/...` |
| `only N matched poses` | timestamps in ns vs s; trajectory file not from this sequence |
| black Pangolin window over SSH | run locally, or `export DISPLAY` with X forwarding |
