#!/usr/bin/env python3
"""Where does tracking struggle? Per-frame diagnostics for one ORB-SLAM3 run.

Lines up, on one time axis:
  1. position error of the saved trajectory (SE(3)-aligned, same as ATE)
  2. ORB-SLAM3 tracking state per frame (needs states_*.txt from the patched example)
  3. image brightness (mean grey level of cam0)
  4. speed (ground truth) and 5. rotation rate (IMU gyro)
  6. tracking time per frame
Frames where tracking is not OK are shaded in every panel.

Usage:
  python3 eval/plot_struggle.py --seq MH_04_difficult --run runs/MH_04_difficult/diag \
      --outdir results/extra/MH_04_difficult
Writes struggle.png and struggle.json (intervals + per-state statistics).
"""
from __future__ import annotations

import argparse
import glob
import json
import os
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
STATE_NAME = {-1: "not ready", 0: "no images", 1: "initialising", 2: "OK",
              3: "recently lost", 4: "lost", 5: "OK (KLT)"}
# reference status palette (fixed, never reused for series): good / warning / critical
STATE_COLOR = {2: "#0ca30c", 5: "#0ca30c", 1: "#fab219", 3: "#ec835a", 4: "#d03b3b",
               0: "#b4b2a9", -1: "#b4b2a9"}
SERIES = "#2a78d6"          # categorical slot 1
INK, INK2, GRID, SURFACE = "#0b0b0b", "#52514e", "#e6e5e0", "#fcfcfb"


def intervals(mask: np.ndarray, t: np.ndarray):
    """[(t_start, t_end)] for runs of True in mask."""
    out, start = [], None
    for i, m in enumerate(mask):
        if m and start is None:
            start = i
        if (not m or i == len(mask) - 1) and start is not None:
            end = i if m else i - 1
            out.append((float(t[start]), float(t[end])))
            start = None
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seq", required=True)
    ap.add_argument("--run", required=True, type=Path)
    ap.add_argument("--outdir", required=True, type=Path)
    args = ap.parse_args()

    from evo.core import sync
    from evo.tools import file_interface
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.image import imread

    euroc = Path(os.environ.get("EUROC_DIR", Path.home() / "datasets" / "euroc")) / args.seq / "mav0"
    run = args.run.resolve()
    out = args.outdir if args.outdir.is_absolute() else REPO / args.outdir
    out.mkdir(parents=True, exist_ok=True)

    # ---- frames
    cam = np.genfromtxt(euroc / "cam0" / "data.csv", delimiter=",", comments="#", dtype=None, encoding=None)
    t_ns = np.array([int(r[0]) for r in cam])
    files = [str(r[1]).strip() for r in cam]
    t0 = t_ns[0] * 1e-9
    tf = t_ns * 1e-9 - t0
    vals = []
    for f in files:
        im = imread(euroc / "cam0" / "data" / f)
        vals.append(im.mean() * (255.0 if im.dtype != np.uint8 else 1.0))
    bright = np.array(vals)

    # ---- tracking state + time per frame
    sf = sorted(glob.glob(str(run / "states_*.txt")))
    if not sf:
        raise SystemExit(f"no states_*.txt in {run}: rebuild with scripts/patch_orbslam3_timing.py")
    st = np.loadtxt(sf[0])
    st_t = st[:, 0] * 1e-9 - t0
    state = st[:, 1].astype(int)
    tt = np.loadtxt(sorted(glob.glob(str(run / "times_*.txt")))[0])[: len(state)]

    # ---- motion: GT speed, IMU gyro rate
    gt = np.loadtxt(euroc / "state_groundtruth_estimate0" / "data.csv", delimiter=",", comments="#")
    gt_t = gt[:, 0] * 1e-9 - t0
    speed = np.linalg.norm(gt[:, 8:11], axis=1)
    imu = np.loadtxt(euroc / "imu0" / "data.csv", delimiter=",", comments="#")
    imu_t = imu[:, 0] * 1e-9 - t0
    gyro = np.degrees(np.linalg.norm(imu[:, 1:4], axis=1))
    k = 20  # 0.1 s moving average at 200 Hz
    gyro_s = np.convolve(gyro, np.ones(k) / k, mode="same")

    # ---- position error of the saved trajectory
    gt_tum = out / "gt.tum"
    np.savetxt(gt_tum, np.column_stack([gt[:, 0] * 1e-9, gt[:, 1:4], gt[:, 5:8], gt[:, 4]]), fmt="%.9f")
    est_f = sorted(glob.glob(str(run / "f_*.txt")))[0]
    e = np.loadtxt(est_f)
    e[:, 0] *= 1e-9
    est_tum = out / "est.tum"
    np.savetxt(est_tum, e, fmt="%.9f")
    ref = file_interface.read_tum_trajectory_file(str(gt_tum))
    est = file_interface.read_tum_trajectory_file(str(est_tum))
    ref, est = sync.associate_trajectories(ref, est, max_diff=0.01)
    est.align(ref, correct_scale=False)
    err = np.linalg.norm(est.positions_xyz - ref.positions_xyz, axis=1)
    err_t = est.timestamps - t0

    # ---- intervals and statistics
    bad = (state != 2) & (state != 5)
    bad_iv = intervals(bad, st_t)
    lost_iv = intervals(state >= 3, st_t)
    # per-frame features at state timestamps
    b_at = np.interp(st_t, tf, bright)
    v_at = np.interp(st_t, gt_t, speed, left=np.nan, right=np.nan)
    w_at = np.interp(st_t, imu_t, gyro_s)
    ok = ~bad
    stats = {
        "sequence": args.seq,
        "run": str(args.run),
        "frames": int(len(state)),
        "frames_per_state": {STATE_NAME[s]: int((state == s).sum()) for s in np.unique(state)},
        "not_ok_intervals_s": [[round(x, 2), round(y, 2)] for x, y in bad_iv],
        "lost_intervals_s": [[round(x, 2), round(y, 2)] for x, y in lost_iv],
        "saved_trajectory_span_s": [round(float(err_t[0]), 2), round(float(err_t[-1]), 2)],
        "sequence_span_s": round(float(tf[-1]), 2),
        "error_max_m": float(err.max()),
        "error_max_at_s": round(float(err_t[np.argmax(err)]), 2),
        "brightness_ok_mean": float(np.nanmean(b_at[ok])),
        "brightness_not_ok_mean": float(np.nanmean(b_at[bad])) if bad.any() else None,
        "speed_ok_mean_mps": float(np.nanmean(v_at[ok])),
        "speed_not_ok_mean_mps": float(np.nanmean(v_at[bad])) if bad.any() else None,
        "gyro_ok_mean_dps": float(np.nanmean(w_at[ok])),
        "gyro_not_ok_mean_dps": float(np.nanmean(w_at[bad])) if bad.any() else None,
        "brightness_overall_p10_p50_p90": [float(x) for x in np.percentile(bright, [10, 50, 90])],
        "track_ms_mean": float(tt[tt > 0].mean()),
        "track_ms_p95": float(np.percentile(tt[tt > 0], 95)),
    }
    # ---- figure: small multiples, one measure per panel, shared time axis
    plt.rcParams.update({"font.size": 8.5, "axes.edgecolor": INK2, "axes.labelcolor": INK,
                         "xtick.color": INK2, "ytick.color": INK2, "axes.titlecolor": INK})
    fig, ax = plt.subplots(6, 1, figsize=(8.0, 9.2), dpi=150, sharex=True,
                           gridspec_kw={"height_ratios": [1.3, 0.45, 1, 1, 1, 1]})
    fig.patch.set_facecolor(SURFACE)
    for a_ in ax:
        a_.set_facecolor(SURFACE)
        a_.grid(axis="y", color=GRID, lw=0.6)
        for s in ("top", "right"):
            a_.spines[s].set_visible(False)
        for x0, x1 in bad_iv:
            a_.axvspan(x0, x1 + 0.05, color="#d03b3b", alpha=0.10, lw=0)

    ax[0].plot(err_t, err, color=SERIES, lw=1.5)
    ax[0].set_ylabel("position\nerror (m)")
    ax[0].set_title(f"{args.seq}: where ORB-SLAM3 tracking struggles "
                    f"(shaded = tracking not OK)", loc="left", fontsize=10)
    # map resets: a frame back in state "initialising" after tracking had started
    resets = [float(st_t[i]) for i in range(1, len(state)) if state[i] <= 1 < state[i - 1]]
    stats["map_resets_s"] = [round(x, 2) for x in resets]
    for x in resets:
        for a_ in ax:
            a_.axvline(x, color=INK2, lw=0.9, ls="--")
    if err_t[0] > tf[0] + 1:
        msg = "no pose saved before this"
        if resets:
            msg = f"map reset at {resets[-1]:.1f} s: earlier map discarded,\n" + msg
        ax[0].text(err_t[0] + 0.8, err.max() * 0.92, msg, fontsize=7.5, color=INK2, va="top")

    for s in np.unique(state):
        m = state == s
        ax[1].scatter(st_t[m], np.zeros(m.sum()), marker="|", s=120, lw=1.4,
                      color=STATE_COLOR.get(s, "#b4b2a9"), label=STATE_NAME.get(s, str(s)))
    ax[1].set_yticks([])
    ax[1].set_ylabel("state")
    ax[1].legend(loc="upper left", bbox_to_anchor=(1.0, 1.25), fontsize=7.5, frameon=False,
                 handletextpad=0.3)
    ax[1].grid(False)

    ax[2].plot(tf, bright, color=SERIES, lw=1.2)
    ax[2].set_ylabel("brightness\n(mean grey, 0–255)")
    ax[3].plot(gt_t, speed, color=SERIES, lw=1.2)
    ax[3].set_ylabel("speed\n(m/s)")
    ax[4].plot(imu_t, gyro_s, color=SERIES, lw=1.0)
    ax[4].set_ylabel("rotation rate\n(deg/s)")
    ax[5].plot(st_t, tt, color=SERIES, lw=0.8)
    ax[5].axhline(50, color=INK2, lw=0.8, ls="--")
    ax[5].text(tf[0] + 0.5, 51, "50 ms = frame period at 20 FPS", va="bottom", ha="left", fontsize=7.5,
               color=INK2, bbox=dict(facecolor=SURFACE, edgecolor="none", pad=0.5))
    ax[5].set_ylabel("tracking time\n(ms/frame)")
    ax[5].set_xlabel("time since start of sequence (s)")
    for a_ in ax:
        a_.set_xlim(tf[0], tf[-1])
    fig.align_ylabels(ax)
    fig.tight_layout()
    fig.savefig(out / "struggle.png", facecolor=SURFACE, bbox_inches="tight")
    over = tt > 50.0
    stats["frames_over_50ms"] = int(over.sum())
    stats["error_at_speed_over_2mps_mean_m"] = float(np.nanmean(err[np.interp(err_t, gt_t, speed) > 2.0]))
    stats["error_at_speed_under_2mps_mean_m"] = float(np.nanmean(err[np.interp(err_t, gt_t, speed) <= 2.0]))
    dark = np.interp(err_t, tf, bright) < 30
    stats["error_dark_mean_m"] = float(err[dark].mean()) if dark.any() else None
    stats["error_not_dark_mean_m"] = float(err[~dark].mean())
    stats["dark_threshold_grey"] = 30
    (out / "struggle.json").write_text(json.dumps(stats, indent=2))
    print(json.dumps(stats, indent=2))
    print(f"-> {out / 'struggle.png'}")


if __name__ == "__main__":
    main()
