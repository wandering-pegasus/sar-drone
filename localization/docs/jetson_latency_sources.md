# Published VIO latency on NVIDIA Jetson: sources for the 38 ms target

Prepared 8 Nov 2026 for Thu Hang (judges' question on the latency target).
Every number below was read from the source itself. Page, table and figure references
are given so anyone can check them.

## Bottom line (for the plan)

1. **Stock ORB-SLAM3 on a Jetson is too slow for 38 ms.** Three independent sources measure
   60–85 ms *mean* per frame on Jetson CPUs, before camera, driver and PX4 transport are added.
   Our server-CPU number (37.8 ms mean, 48.7 ms p95) is not evidence either way: it is a different CPU.
2. **GPU-accelerated cuVSLAM (Isaac ROS) is roughly 10× faster on the same boards.**
   NVIDIA reports 3.8 ms mean for stereo-inertial tracking on Jetson AGX Orin. An independent
   industrial benchmark measures 9.4 ms mean (40 ms max) on Jetson Xavier.
3. **So the 38 ms p95 target is plausible with cuVSLAM, not with stock ORB-SLAM3.**
   No source reports p95 or end-to-end (capture → flight controller) latency on a Jetson, so
   **our own Phase-1 measurement on our Jetson is still required**. That is task #10 in the plan.

Suggested sentence for the plan:

> Published benchmarks show that CPU-only ORB-SLAM3 needs 60–85 ms per frame on Jetson boards
> (Khabiri et al., IROS 2025; Roy et al., 2026), while NVIDIA's GPU-accelerated cuVSLAM tracks a
> stereo-inertial frame in 3.8 ms on Jetson AGX Orin (Korovko et al., 2025) and about 9 ms on the
> older Jetson Xavier (Abi Hana et al., 2026). We therefore run cuVSLAM on the drone and keep
> ORB-SLAM3 as an offline accuracy baseline. This leaves most of the 38 ms budget for image
> capture, transport and the PX4 interface, which we will measure end-to-end on our Jetson in Phase 1.

## Numbers

| # | System | Board | Mode / data | Per-frame time | Statistic | Source |
|---|---|---|---|---|---|---|
| 1 | ORB-SLAM3 (stock, CPU) | Jetson Xavier NX (6-core Carmel @ 1.4 GHz, 15 W) | stereo-inertial, EuRoC MH01 | **84.6 ± 17.3 ms** | mean ± std, 5 runs | [B] Table III |
| 2 | ORB-SLAM3 + GPU tracking (FastTrack) | Jetson Xavier NX | stereo-inertial, EuRoC MH01 | 41.3 ± 9.0 ms | mean ± std | [B] Table III |
| 3 | ORB-SLAM3 (stock, CPU) | Jetson Xavier NX | stereo-inertial, 6 seqs EuRoC + TUM-VI | 77.5 ms | mean | [B] Table III |
| 4 | ORB-SLAM3 (stock, CPU) | Jetson Orin Nano (6-core A78AE, 8 GB) | stereo-inertial, all 11 EuRoC seqs | **62.1 ms** | mean | [C] Table 8 |
| 5 | ORB-SLAM3 + GPU ORB front end | Jetson Orin Nano | stereo-inertial, EuRoC | 69.7 ms (14.4 FPS); 28 FPS when extraction is pipelined (throughput, not latency) | mean | [C] Tables 7, 8 |
| 6 | ORB-SLAM3 (stereo, CPU) | Jetson Xavier* | stereo VO, 1280×720 @ 15 FPS, warehouse | 60.3 ms (max 71.6 ms) | mean / max | [D] Table 3 |
| 7 | cuVSLAM | Jetson Xavier* | same as #6 | **9.4 ms (max 40.3 ms)** | mean / max | [D] Table 3 |
| 8 | cuVSLAM | Jetson AGX Orin 64 GB, MAXN | stereo-inertial, 768×480 recorded | **3.8 ms** | mean "track call time" | [A] Table 1 |
| 9 | cuVSLAM | Jetson AGX Orin 64 GB, MAXN | stereo (no IMU) | 1.8 ms | mean | [A] Table 1 |
| 10 | cuVSLAM ("VSLAM") | Jetson AGX Xavier | KITTI odometry benchmark | 7 ms (0.007 s) | runtime column | [E] |
| — | *ours*: ORB-SLAM3 (stock, CPU) | Intel Xeon Platinum 8480+ (server, 16 cores) | stereo-inertial, EuRoC MH01 | 37.8 ms (p95 48.7 ms) | mean, p95 | our Round 2 run |
| — | ORB-SLAM3 (stock, CPU), for scale | Intel i7-12700K desktop @ 5 GHz | stereo-inertial, EuRoC MH01 | 15.5 ± 2.6 ms | mean ± std | [B] Table II |

\* [D] writes "NVIDIA Jetson Xavier or Xavier" and does not say which Xavier model.

### What each number measures (important when comparing with 38 ms)

- **[A], [B], [C]: one tracking call only.** Image loading and acquisition, ROS transport and the flight-controller link are
  *excluded*. Local mapping and loop closing run in other threads. This is the same quantity as our `TrackStereo()` time.
- **[A] is the cuVSLAM authors' own result, on recorded images.** Their live tests on the AGX Orin report CPU/GPU
  utilisation, not time. For UAVs they recommend 60 FPS cameras (App. A.2), which would halve the frame period to 16.7 ms.
- **[B] is the only peer-reviewed source here.** It measures stock ORB-SLAM3 on a Jetson in our exact
  configuration (stereo-inertial, EuRoC). Stock ORB-SLAM3 also *dropped frames* on the Jetson: 50.2 on MH01 and 69.4 on MH02,
  averaged over 5 runs (Table V).
- **[C] is a recent preprint (Aug 2026), not yet peer reviewed.** It is the only source on the Orin generation for ORB-SLAM3.
- **None of the sources gives p95 or end-to-end latency.** The closest is the max in [D].

## Sources

- **[A]** A. Korovko, D. Slepichev, A. Efitorov, A. Dzhumamuratova, V. Kuznetsov, J. Biswas, H. Rabeti, S. Pouya (NVIDIA),
  "cuVSLAM: CUDA accelerated visual odometry and mapping," arXiv:2506.04359v3, Jul 2025. Table 1 (p. 8); App. A.2 (pp. 19–21).
- **[B]** K. Khabiri, P. Hosseininejad, S. Gopinath, K. Dantu, S. Y. Ko, "FastTrack: GPU-Accelerated Tracking for Visual SLAM,"
  *IEEE/RSJ IROS 2025*, pp. 15165–15172, doi:10.1109/IROS60139.2025.11247316 (arXiv:2509.10757). Tables I–III, V.
- **[C]** R. Roy, A. A. K. Yadav, H. Jain (IIT Jodhpur), "Jetson-ORB-SLAM3: Accuracy-Preserving GPU Implementation for Edge
  Computing Devices," arXiv:2608.17874, Aug 2026 (preprint). Tables 6–8, §4.4.
- **[D]** C. Abi Hana et al. (Idealworks, NVIDIA), "Industrial cuVSLAM Benchmark & Integration," arXiv:2603.16240, Mar 2026
  (preprint). Tables 2–3.
- **[E]** NVIDIA Isaac ROS documentation, `isaac_ros_visual_slam` / `isaac_ros_cuvslam` package page, KITTI comparison table
  (cuVSLAM 0.007 s on Jetson AGX Xavier vs ORB-SLAM2 0.06 s on 2 x86 cores). Read 8 Nov 2026. NVIDIA's general Isaac ROS
  performance page (release 5.0) has no Visual SLAM entry.

### The paper Thu Hang suggested

J. Jeon, S. Jung, E. Lee, D. Choi, H. Myung, "Run Your Visual-Inertial Odometry on NVIDIA Jetson: Benchmark Tests on a Micro
Aerial Vehicle," *IEEE RA-L* 6(3):5332–5339, 2021, doi:10.1109/LRA.2021.3075141 (a correction was published, doi:10.1109/LRA.2021.3085435).

- It is a good source for **hardware choice and resource use**: TX2, Xavier NX and AGX Xavier; D435i at 640×480, 30 Hz; CPU and
  memory usage; ATE.
- It does **not** report per-frame time or latency. It also tests ORB-SLAM**2** stereo, not ORB-SLAM3, and boards older than Orin.
- Usable statement from it: CPU-only stereo methods (ORB-SLAM2, S-MSCKF, Kimera) lost accuracy on the weaker boards
  "owing to the limitation of per-frame processing time", while GPU-accelerated VINS-Fusion did not. Their conclusion: "In stereo
  VO/VIO, a GPU-accelerated algorithm would be appropriate for use in TX2."

### Do not cite

arXiv:2605.03678 ("Robust Visual SLAM for UAV Navigation in GPS-Denied and Degraded Environments", May 2026) has a Jetson latency
table (Table VIII: ORB-SLAM3 6.2 ms on AGX Orin, 18.2 ms on Nano). Its own limitations section, however, says "All experiments
are conducted on a fixed high-end server (NVIDIA RTX 3090)". It also lists a GPU latency for ORB-SLAM3, which runs on the CPU.
The table cannot be trusted. A judge who checks it would find the contradiction.
