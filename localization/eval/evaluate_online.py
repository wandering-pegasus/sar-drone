#!/usr/bin/env python3
"""Drift of the ONLINE ORB-SLAM3 trajectory: the pose the drone would have sent to PX4.

The usual f_*.txt is written at the end of the run, after later bundle adjustments
have refined every pose, so it is smoother than anything available in flight. This
script evaluates online_*.txt instead (written by the patched example, see
scripts/patch_orbslam3_timing.py): one pose per frame, exactly as TrackStereo()
returned it at that moment.

Steps
  1. keep frames with tracking state OK;
  2. drop the IMU-initialisation phase: ORB-SLAM3 re-aligns its world frame (gravity,
     biases) until "end VIBA 2", nominally 15 s of map time after start, later if the
     initialisation restarts (e.g. while the drone stands still). The evaluation starts
     --settle-s (default 1 s) after the LAST "end VIBA 2 t=..." in log.txt, which needs
     scripts/patch_orbslam3_eventlog.py (adds timestamps to these prints);
  3. camera pose -> body (IMU) pose with T_b_c1 from the ORB-SLAM3 settings file,
     the same frame as the EuRoC ground truth;
  4. metrics:
       start-aligned drift  SE(3) alignment on the first --start-align-m metres only,
                            then final error / path length, and the max error on the way;
       segment drift        for every sub-path of 10 m and 30 m (sliding, evo RPE all pairs):
                            relative translation error / segment length x 100 %.
                            30 m = the closed-loop length in our 4.5 % target.
Writes metrics_online.json and online_error.png into --outdir.

Usage:
  python3 eval/evaluate_online.py --seq MH_04_difficult --run runs/MH_04_difficult/noLC_diag \
      --outdir results/extra/online/MH_04_difficult_noLC --label "loop closure off"
"""
from __future__ import annotations

import argparse
import copy
import glob
import json
import os
import re
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "eval"))
from evaluate import DEFAULT_GT, prepare_gt  # noqa: E402

SERIES = ["#2a78d6", "#eb6834"]  # categorical slots 1, 2
INK2, GRID, SURFACE = "#52514e", "#e6e5e0", "#fcfcfb"


def read_T_b_c1(yaml_path: Path) -> np.ndarray:
    txt = yaml_path.read_text()
    m = re.search(r"IMU\.T_b_c1:.*?data:\s*\[([^\]]*)\]", txt, re.S)
    if not m:
        raise SystemExit(f"IMU.T_b_c1 not found in {yaml_path}")
    return np.array([float(x) for x in m.group(1).replace("\n", " ").split(",")]).reshape(4, 4)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seq", required=True)
    ap.add_argument("--run", required=True, type=Path)
    ap.add_argument("--outdir", required=True, type=Path)
    ap.add_argument("--label", default="")
    ap.add_argument("--gt", type=Path)
    ap.add_argument("--settle-s", type=float, default=1.0,
                    help="seconds after the last 'end VIBA 2' before evaluation starts")
    ap.add_argument("--start-align-m", type=float, default=5.0)
    ap.add_argument("--segments", type=float, nargs="+", default=[10.0, 30.0])
    args = ap.parse_args()

    from scipy.spatial.transform import Rotation as R
    from evo.core import metrics, sync
    from evo.core.trajectory import PoseTrajectory3D
    from evo.tools import file_interface

    run = args.run.resolve()
    out = args.outdir if args.outdir.is_absolute() else REPO / args.outdir
    out.mkdir(parents=True, exist_ok=True)

    # ---- settings file actually used (machine.txt records it)
    cfg = None
    for line in (run / "machine.txt").read_text().splitlines():
        if line.startswith("config:"):
            cfg = Path(line.split(":", 1)[1].strip())
    T_b_c = read_T_b_c1(cfg)
    T_c_b = np.linalg.inv(T_b_c)

    # ---- online poses
    of = sorted(glob.glob(str(run / "online_*.txt")))
    if not of:
        raise SystemExit(f"no online_*.txt in {run}: rebuild with scripts/patch_orbslam3_timing.py")
    a = np.loadtxt(of[0])
    t = a[:, 0] * 1e-9
    state = a[:, 1].astype(int)
    ok = (state == 2) | (state == 5)

    # events with timestamps from the (patched) ORB-SLAM3 log
    log = (run / "log.txt").read_text(errors="ignore")
    viba2 = [float(x) for x in re.findall(r"end VIBA 2 t=([0-9.]+)", log)]
    loops = [float(x) for x in re.findall(r"\*Loop detected t=([0-9.]+)", log)]
    merges = [float(x) for x in re.findall(r"\*Merge detected t=([0-9.]+)", log)]
    if not viba2:
        raise SystemExit("no 'end VIBA 2 t=' in log.txt: IMU init never finished, or the event-log "
                         "patch (scripts/patch_orbslam3_eventlog.py) is missing")
    resets = [float(t[i]) for i in range(1, len(state)) if state[i] <= 1 < state[i - 1]]
    t_viba2 = viba2[-1]
    t_start = t_viba2 + args.settle_s
    sel = ok & (t >= t_start)
    rel = lambda xs: [round(float(x - t[0]), 2) for x in xs]  # noqa: E731
    late_changes = rel([x for x in loops + merges if x >= t_start])

    # camera -> body
    P, Q = a[sel, 3:6], a[sel, 6:10]  # Twc
    Rwc = R.from_quat(Q).as_matrix()
    Twc = np.tile(np.eye(4), (len(P), 1, 1))
    Twc[:, :3, :3], Twc[:, :3, 3] = Rwc, P
    Twb = Twc @ T_c_b
    q_wb = R.from_matrix(Twb[:, :3, :3]).as_quat()  # x y z w
    est_tum = out / "online_body.tum"
    np.savetxt(est_tum, np.column_stack([t[sel], Twb[:, :3, 3], q_wb]), fmt="%.9f",
               header="timestamp tx ty tz qx qy qz qw  (online, body frame)")

    # ---- ground truth
    gt_src = args.gt or DEFAULT_GT.get(args.seq) or (
        Path(os.environ.get("EUROC_DIR", Path.home() / "datasets" / "euroc"))
        / args.seq / "mav0" / "state_groundtruth_estimate0" / "data.csv")
    prepare_gt(Path(gt_src), out / "gt.tum")
    ref = file_interface.read_tum_trajectory_file(str(out / "gt.tum"))
    est = file_interface.read_tum_trajectory_file(str(est_tum))
    ref, est = sync.associate_trajectories(ref, est, max_diff=0.01)

    seg = np.linalg.norm(np.diff(ref.positions_xyz, axis=0), axis=1)
    cum = np.concatenate([[0.0], np.cumsum(seg)])
    length = float(cum[-1])

    # start-aligned
    n0 = int(np.searchsorted(cum, args.start_align_m)) + 1
    est_s = copy.deepcopy(est)
    est_s.align(ref, correct_scale=False, n=n0)
    err_s = np.linalg.norm(est_s.positions_xyz - ref.positions_xyz, axis=1)
    # whole-trajectory aligned (ATE, for reference)
    est_a = copy.deepcopy(est)
    est_a.align(ref, correct_scale=False)
    err_a = np.linalg.norm(est_a.positions_xyz - ref.positions_xyz, axis=1)

    seg_res = {}
    for d in args.segments:
        if length < d * 1.05:
            seg_res[f"{d:g}m"] = None
            continue
        rpe = metrics.RPE(metrics.PoseRelation.translation_part, delta=d,
                          delta_unit=metrics.Unit.meters, all_pairs=True)
        rpe.process_data((ref, est))  # relative errors are alignment-free
        e = np.asarray(rpe.error)
        seg_res[f"{d:g}m"] = {
            "segments": int(e.size),
            "mean_pct": float(100 * e.mean() / d),
            "p95_pct": float(100 * np.percentile(e, 95) / d),
            "max_pct": float(100 * e.max() / d),
        }

    res = {
        "sequence": args.seq,
        "label": args.label,
        "run": str(args.run),
        "config": str(cfg),
        "gt_source": str(gt_src),
        "frames": int(len(t)),
        "frames_ok": int(ok.sum()),
        "map_resets_s": rel(resets),
        "end_viba2_s": rel(viba2),
        "loop_closures_s": rel(loops),
        "map_merges_s": rel(merges),
        "eval_start_s": round(float(t_start - t[0]), 2),
        "eval_end_s": round(float(t[sel][-1] - t[0]), 2),
        "evaluated_poses": int(est.num_poses),
        "evaluated_length_m": length,
        "ate_rmse_m": float(np.sqrt(np.mean(err_a ** 2))),
        "start_aligned_final_error_m": float(err_s[-1]),
        "start_aligned_drift_pct": float(100 * err_s[-1] / length),
        "start_aligned_max_error_m": float(err_s.max()),
        "segment_drift": seg_res,
    }
    (out / "metrics_online.json").write_text(json.dumps(res, indent=2))

    # ---- figure: error along the path (start-aligned), one series, events marked
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(7.2, 2.8), dpi=150)
    fig.patch.set_facecolor(SURFACE)
    ax.set_facecolor(SURFACE)
    ax.plot(cum, err_s, color=SERIES[0], lw=1.5)
    for x in late_changes:
        xm = np.interp(x + t[0], est.timestamps, cum)
        ax.axvline(xm, color=INK2, lw=0.8, ls="--")
    ax.set_xlabel("distance travelled since evaluation start (m)")
    ax.set_ylabel("position error (m)")
    ax.set_title(f"{args.seq}, online pose{', ' + args.label if args.label else ''}: "
                 f"error after aligning only the first {args.start_align_m:g} m", loc="left", fontsize=9)
    ax.grid(axis="y", color=GRID, lw=0.6)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    if late_changes:
        ax.text(0.99, 0.95, "dashed: big map correction (loop closure / merge)", transform=ax.transAxes,
                ha="right", va="top", fontsize=7.5, color=INK2)
    fig.tight_layout()
    fig.savefig(out / "online_error.png", facecolor=SURFACE)

    print(json.dumps(res, indent=2))


if __name__ == "__main__":
    main()
