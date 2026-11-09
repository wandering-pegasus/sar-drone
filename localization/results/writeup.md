# Round 2 write-up (for the plan)

Use the version that matches the plan's language. Figure: `results/MH_01_easy/traj.png`
(or V1_01_easy). Table: `results/summary.md`.

## English (~150 words)

To verify that the team can run VI-SLAM and compute the promised metrics, we
evaluated ORB-SLAM3 (stereo-inertial, default configuration, commit 4452a3c) on
two sequences of the public EuRoC MAV dataset (ETH Zürich): MH_01_easy (machine
hall, 80.5 m) and V1_01_easy (Vicon room, 58.3 m), using the provided
motion-capture ground truth. After SE(3) alignment, the absolute trajectory error
(ATE RMSE) was 0.039 m and 0.022 m, the relative pose error over 1 m segments
was 0.020 m and 0.014 m, and the final drift was 0.06 % and 0.04 % of distance
travelled (project target: ≤ 4.5 % on a 30 m loop). Both sequences ran to the end
without tracking loss, and a second run gave similar results. Tracking took
about 37 ms per frame on average (p95 about 48 ms) on one Intel Xeon Platinum 8480+
(16 cores, no GPU). These figures are our EuRoC baseline. Limitation: EuRoC is
a well-lit indoor scene with loop closures, and timing was measured on a server
CPU, not the Jetson; dark, dusty tunnels and end-to-end latency to PX4 remain to
be tested in Phases 1–3.

## 繁體中文（約 250 字）

為確認團隊能執行 VI-SLAM 並計算計畫中承諾的指標，我們以 ORB-SLAM3（雙目＋IMU、
預設參數、commit 4452a3c）在蘇黎世聯邦理工學院公開的 EuRoC MAV 資料集兩段序列上
進行測試：MH_01_easy（機械廠房，軌跡長 80.5 m）與 V1_01_easy（Vicon 室，58.3 m），
並以資料集提供的動作捕捉真值為參考。經 SE(3) 對齊後，絕對軌跡誤差（ATE RMSE）分別為
0.039 m 與 0.022 m，每 1 m 區段的相對位姿誤差為 0.020 m 與 0.014 m，終點漂移為行進
距離的 0.06 % 與 0.04 %（專案目標：30 m 閉環 ≤ 4.5 %）。兩段序列皆完整跑完、未失去追蹤，
重跑一次結果相近。在 Intel Xeon Platinum 8480+（16 核、無 GPU）上，每幀追蹤平均約
37 ms（p95 約 48 ms）。以上數據為本團隊的 EuRoC 基準。限制：EuRoC 為光線充足的室內
場景且含迴環，計時是在伺服器 CPU 而非 Jetson 上量測；昏暗、多塵的隧道環境及至 PX4 的
端到端延遲，將於第 1–3 階段測試。
