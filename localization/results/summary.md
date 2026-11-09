# Round 2 results: VI-SLAM on EuRoC

ATE: RMSE of absolute translation error after SE(3) alignment (evo `-a`, no scale).  
RPE: RMSE of translation error over 1 m segments.  
Drift: final position error after alignment / ground-truth path length × 100.  
Time/frame: wall time of `TrackStereo()` per stereo frame (tracking thread; local mapping and loop closing run in parallel threads).

| Sequence | Algorithm | ATE RMSE (m) | RPE 1 m (m) | Trajectory length (m) | Drift (%) | Mean time/frame (ms) | p95 (ms) | Machine |
|---|---|---|---|---|---|---|---|---|
| MH_01_easy | ORB-SLAM3 (stereo-inertial) | 0.039 | 0.020 | 80.5 | 0.06 | 37.8 | 48.7 | Intel(R) Xeon(R) Platinum 8480+, 16 cores, 503Gi RAM |
| V1_01_easy | ORB-SLAM3 (stereo-inertial) | 0.022 | 0.014 | 58.3 | 0.04 | 37.1 | 47.7 | Intel(R) Xeon(R) Platinum 8480+, 16 cores, 503Gi RAM |

Configuration: default `Examples/Stereo-Inertial/EuRoC.yaml`, no per-sequence tuning.
ORB-SLAM3 commit: `4452a3c4ab75b1cde34e5505a36ec3f9edcdc4c4`

Notes:
- V1_01_easy: ground truth = OpenVINS-corrected trajectory (original EuRoC V1_01 ground truth has inaccurate orientation).

## Repeatability

| Sequence | Runs | ATE (m) | Drift (%) | Length (m) | Mean (ms) | p95 (ms) |
|---|---|---|---|---|---|---|
| MH_01_easy | run1 vs run2 | 0.039 / 0.047 | 0.06 / 0.08 | 80.5 / 78.8 | 37.8 / 31.4 | 48.7 / 43.3 |
| V1_01_easy | run1 vs run2 | 0.022 / 0.022 | 0.04 / 0.03 | 58.3 / 58.3 | 37.1 / 29.9 | 47.7 / 40.5 |

Length is measured over the poses matched to ground truth, so it changes slightly with how quickly ORB-SLAM3 initialises in each run. Timing varies between runs because ORB-SLAM3's mapping threads and the OS scheduler are not deterministic.
