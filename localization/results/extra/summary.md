# Round 2 follow-up: hard sequence and loop closure off

Same pipeline as Round 2: ORB-SLAM3 stereo-inertial, default `EuRoC.yaml`; same machine (Intel Xeon
Platinum 8480+, 16 cores, no GPU). The *no loop closure* runs use `configs/EuRoC_noLC.yaml`, which
is the default config plus `loopClosing: 0` (switches off place recognition, loop correction and map merging).

- **Drift (global)**: final error after SE(3) alignment of the whole trajectory (Round 2 definition).
- **Drift (start-aligned)**: SE(3) alignment on the first 5 m only, then the final error divided by the
  path length. Closer to a flight that starts at a known pose and is never corrected afterwards.
- **Max err (start-aligned)**: the largest position error anywhere along the path under that alignment.
- **Coverage**: share of the sequence covered by the saved trajectory. ORB-SLAM3 saves only its largest
  map, so frames lost before or after it do not count.

**Loop closure never fired in any run** (no `*Loop detected` / `*Merge detected` in any log, including
the Round 2 runs). Switching it off therefore changes nothing; differences between on/off rows are
run-to-run variation. The low Round 2 drift comes from ORB-SLAM3 re-using its map in these small rooms
and from scoring the end-of-run, refined trajectory, not from loop closure.

| Sequence | Loop closure | ATE RMSE (m) | RPE 1 m (m) | Drift global (%) | Drift start-aligned (%) | Max err start-aligned (m) | Coverage (%) | ms/frame mean / p95 |
|---|---|---|---|---|---|---|---|---|
| MH_01_easy | on (default) | 0.039 | 0.020 | 0.06 | 0.01 | 0.202 | 100 | 37.8 / 48.7 |
| MH_01_easy | **off** | 0.045 | 0.021 | 0.07 | 0.01 | 0.226 | 100 | 38.7 / 50.4 |
| V1_01_easy | on (default) | 0.022 | 0.014 | 0.04 | 0.01 | 0.063 | 96 | 37.1 / 47.7 |
| V1_01_easy | **off** | 0.024 | 0.014 | 0.04 | 0.00 | 0.073 | 96 | 38.5 / 50.0 |
| MH_04_difficult | on (default) | 0.041 | 0.031 | 0.02 | 0.01 | 0.202 | 90 | 36.7 / 47.9 |
| MH_04_difficult | **off** | 0.041 | 0.030 | 0.02 | 0.01 | 0.179 | 90 | 36.9 / 48.3 |

MH_04_difficult run2 (loop closure on, repeatability): ATE 0.041 m, drift 0.07 %, coverage 90 %, 39.9 / 51.0 ms.

## Online pose (what the drone would send to PX4)

The tables above use ORB-SLAM3's saved trajectory, which is refined after the fact. Here the pose
returned by `TrackStereo()` at each frame is scored instead (`eval/evaluate_online.py`), starting 1 s
after IMU initialisation finished (last `end VIBA 2`). **Segment drift** = relative translation
error over every 10 m / 30 m sub-path ÷ its length (30 m = our target loop). No alignment needed.

| Sequence | Loop closure | Evaluated | ATE RMSE (m) | Drift start-aligned (%) | Max err start-aligned (m) | 10 m drift mean / max (%) | 30 m drift mean / max (%) | Loops / merges |
|---|---|---|---|---|---|---|---|---|
| MH_01_easy | on (default) | 47–184 s, 72 m | 0.041 | 0.03 | 0.17 | 0.96 / 3.16 | 0.51 / 1.36 | 0 / 0 |
| MH_01_easy | **off** | 47–184 s, 72 m | 0.036 | 0.03 | 0.15 | 0.89 / 3.05 | 0.47 / 1.28 | 0 / 0 |
| V1_01_easy | on (default) | 21–146 s, 53 m | 0.024 | 0.07 | 0.09 | 0.38 / 1.11 | 0.11 / 0.22 | 0 / 0 |
| V1_01_easy | **off** | 21–146 s, 53 m | 0.022 | 0.06 | 0.09 | 0.35 / 1.13 | 0.10 / 0.20 | 0 / 0 |
| MH_04_difficult | on (default) | 37–102 s, 74 m | 0.062 | 1.12 | 1.37 | 2.32 / 3.86 | 1.24 / 2.13 | 0 / 0 |
| MH_04_difficult | **off** | 37–102 s, 74 m | 0.053 | 0.60 | 0.81 | 2.23 / 3.80 | 1.19 / 2.06 | 0 / 0 |

## MH_04_difficult: where tracking struggles

Per-frame tracking state (diagnostic run): {'initialising': 33, 'OK': 1999}.
Not-OK intervals (s from sequence start): [[0.05, 1.6], [12.1, 12.1]].
Saved trajectory covers 12.15–100.45 s of 101.6 s.
Figure: `results/extra/MH_04_difficult/struggle.png`.
