#!/usr/bin/env python3
"""Evaluate one VIO run on one EuRoC sequence.

Produces, in results/<seq>/ (or results/<seq>/reruns/<tag>/ for extra runs):
  est.tum       estimated trajectory, TUM format (timestamp in seconds)
  gt.tum        ground truth used, TUM format
  ate.zip       evo_ape output   (SE(3) alignment, -a, no scale)
  rpe.txt       evo_rpe output   (translation, delta = 1 m)
  traj.png      estimate (aligned) over ground truth, metres
  metrics.json  every number for summary.md

Usage:
  python3 eval/evaluate.py --seq MH_01_easy --run runs/MH_01_easy/run1
  python3 eval/evaluate.py --seq V1_01_easy --run runs/V1_01_easy/run1
  python3 eval/evaluate.py --seq MH_01_easy --run runs/MH_01_easy/run2 --tag run2

Ground truth default:
  MH_01_easy -> $EUROC_DIR/MH_01_easy/mav0/state_groundtruth_estimate0/data.csv
  V1_01_easy -> gt/V1_01_easy_openvins_corrected.tum  (see README: the original
                V1_01 ground truth has inaccurate orientation; OpenVINS recomputed it)
Override with --gt <file.csv|file.tum>.
"""
from __future__ import annotations

import argparse
import copy
import glob
import json
import os
import re
import subprocess
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
DEFAULT_GT = {
    "V1_01_easy": REPO / "gt" / "V1_01_easy_openvins_corrected.tum",
}


# ---------------------------------------------------------------- conversion
def euroc_csv_to_tum(csv_path: Path, out: Path) -> None:
    """EuRoC state_groundtruth_estimate0/data.csv -> TUM.
    columns: t[ns], px, py, pz, qw, qx, qy, qz, ..."""
    a = np.loadtxt(csv_path, delimiter=",", comments="#", usecols=range(8))
    t = a[:, 0] * 1e-9
    p = a[:, 1:4]
    q_wxyz = a[:, 4:8]
    tum = np.column_stack([t, p, q_wxyz[:, 1:4], q_wxyz[:, 0]])  # -> qx qy qz qw
    np.savetxt(out, tum, fmt="%.9f", header="timestamp tx ty tz qx qy qz qw")


def orbslam_euroc_to_tum(traj_path: Path, out: Path) -> None:
    """ORB-SLAM3 SaveTrajectoryEuRoC: 't[ns] tx ty tz qx qy qz qw' (space separated)."""
    a = np.loadtxt(traj_path)
    if a.ndim != 2 or a.shape[1] != 8:
        sys.exit(f"unexpected trajectory format in {traj_path}: shape {a.shape}")
    t = a[:, 0]
    if t[0] > 1e14:          # nanoseconds -> seconds
        t = t * 1e-9
    a[:, 0] = t
    np.savetxt(out, a, fmt="%.9f", header="timestamp tx ty tz qx qy qz qw")


def prepare_gt(gt_path: Path, out: Path) -> None:
    if gt_path.suffix == ".csv":
        euroc_csv_to_tum(gt_path, out)
    else:
        a = np.loadtxt(gt_path)
        np.savetxt(out, a, fmt="%.9f", header="timestamp tx ty tz qx qy qz qw")


# ---------------------------------------------------------------- helpers
def path_length(xyz: np.ndarray) -> float:
    return float(np.sum(np.linalg.norm(np.diff(xyz, axis=0), axis=1)))


def run(cmd: list[str], cwd: Path) -> str:
    print("$", " ".join(cmd))
    r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    if r.returncode != 0:
        print(r.stdout, r.stderr, sep="\n", file=sys.stderr)
        sys.exit(f"command failed: {' '.join(cmd)}")
    return r.stdout


def read_machine(run_dir: Path) -> dict:
    info = {}
    f = run_dir / "machine.txt"
    if f.exists():
        for line in f.read_text().splitlines():
            if ":" in line:
                k, v = line.split(":", 1)
                info[k.strip()] = v.strip()
    return info


def read_maps(run_dir: Path):
    f = run_dir / "log.txt"
    if not f.exists():
        return None
    m = re.findall(r"There are (\d+) maps", f.read_text(errors="ignore"))
    return int(m[-1]) if m else None


# ---------------------------------------------------------------- main
def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seq", required=True)
    ap.add_argument("--run", required=True, type=Path, help="run folder from run_orbslam3.sh")
    ap.add_argument("--gt", type=Path, help="ground truth .csv (EuRoC) or .tum")
    ap.add_argument("--est", type=Path, help="trajectory file (default: f_*.txt in --run)")
    ap.add_argument("--est-format", choices=["orbslam", "tum"], default="orbslam")
    ap.add_argument("--algorithm", default="ORB-SLAM3 (stereo-inertial)")
    ap.add_argument("--tag", default="run1", help="run1 = main result; others go to reruns/")
    ap.add_argument("--outdir", type=Path, help="write here instead of results/<seq>[/reruns/<tag>]")
    ap.add_argument("--start-align-m", type=float, default=5.0,
                    help="path length (m) used for the start-aligned drift (default 5)")
    args = ap.parse_args()

    from evo.core import metrics, sync
    from evo.tools import file_interface

    run_dir = args.run.resolve()
    out = REPO / "results" / args.seq
    if args.tag != "run1":
        out = out / "reruns" / args.tag
    if args.outdir:
        out = args.outdir if args.outdir.is_absolute() else REPO / args.outdir
    out.mkdir(parents=True, exist_ok=True)

    # --- trajectory files
    est_src = args.est
    if est_src is None:
        cands = sorted(glob.glob(str(run_dir / "f_*.txt")))
        if not cands:
            sys.exit(f"no f_*.txt in {run_dir}")
        est_src = Path(cands[0])
    if args.est_format == "orbslam":
        orbslam_euroc_to_tum(est_src, out / "est.tum")
    else:
        prepare_gt(est_src, out / "est.tum")  # plain copy/normalise

    gt_src = args.gt or DEFAULT_GT.get(args.seq)
    if gt_src is None:
        euroc = Path(os.environ.get("EUROC_DIR", Path.home() / "datasets" / "euroc"))
        gt_src = euroc / args.seq / "mav0" / "state_groundtruth_estimate0" / "data.csv"
    if not Path(gt_src).exists():
        sys.exit(f"ground truth not found: {gt_src}  (use --gt or set EUROC_DIR)")
    prepare_gt(Path(gt_src), out / "gt.tum")

    # --- evo CLI outputs (the files the task asks for)
    for f in ("ate.zip",):
        (out / f).unlink(missing_ok=True)
    ape_txt = run(["evo_ape", "tum", "gt.tum", "est.tum", "-a",
                   "--save_results", "ate.zip", "--no_warnings"], out)
    (out / "ate.txt").write_text(ape_txt)
    rpe_txt = run(["evo_rpe", "tum", "gt.tum", "est.tum", "-a",
                   "--pose_relation", "trans_part",
                   "--delta", "1", "--delta_unit", "m", "--no_warnings"], out)
    (out / "rpe.txt").write_text(rpe_txt)

    # --- same numbers through the API + drift and length
    ref = file_interface.read_tum_trajectory_file(str(out / "gt.tum"))
    est = file_interface.read_tum_trajectory_file(str(out / "est.tum"))
    est_span = (est.timestamps[0], est.timestamps[-1])
    ref, est = sync.associate_trajectories(ref, est, max_diff=0.01)
    n_matched = est.num_poses
    if n_matched < 100:
        sys.exit(f"only {n_matched} matched poses: check timestamp units (s vs ns)")
    est_aligned = copy.deepcopy(est)
    est_aligned.align(ref, correct_scale=False)  # SE(3) Umeyama, same as evo -a

    ape = metrics.APE(metrics.PoseRelation.translation_part)
    ape.process_data((ref, est_aligned))
    ate_rmse = ape.get_statistic(metrics.StatisticsType.rmse)

    rpe = metrics.RPE(metrics.PoseRelation.translation_part, delta=1.0,
                      delta_unit=metrics.Unit.meters, all_pairs=False)
    rpe.process_data((ref, est_aligned))
    rpe_rmse = rpe.get_statistic(metrics.StatisticsType.rmse)
    rpe_mean = rpe.get_statistic(metrics.StatisticsType.mean)

    # start-aligned drift: SE(3)-align on the first N m of path only, then take the final error.
    # Closer to a real flight, where the start pose is known (AprilTag) and nothing corrects the end.
    cum = np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.diff(ref.positions_xyz, axis=0), axis=1))])
    n_start = int(np.searchsorted(cum, args.start_align_m)) + 1
    est_start = copy.deepcopy(est)
    est_start.align(ref, correct_scale=False, n=n_start)
    final_err_start = float(np.linalg.norm(est_start.positions_xyz[-1] - ref.positions_xyz[-1]))
    err_start = np.linalg.norm(est_start.positions_xyz - ref.positions_xyz, axis=1)

    # coverage: how much of the ground-truth time span the saved trajectory covers.
    # ORB-SLAM3 saves only its largest map, so tracking loss shows up as low coverage.
    gt_all = file_interface.read_tum_trajectory_file(str(out / "gt.tum"))
    gt_span = float(gt_all.timestamps[-1] - gt_all.timestamps[0])
    coverage = float(est.timestamps[-1] - est.timestamps[0]) / gt_span

    gt_len = path_length(ref.positions_xyz)
    est_len = path_length(est.positions_xyz)
    final_err = float(np.linalg.norm(est_aligned.positions_xyz[-1] - ref.positions_xyz[-1]))
    drift_pct = 100.0 * final_err / gt_len

    # --- timing
    timing = {}
    tfiles = sorted(glob.glob(str(run_dir / "times_*.txt")))
    if tfiles:
        t = np.loadtxt(tfiles[0])
        t = t[t > 0]
        timing = {
            "frames": int(t.size),
            "mean_ms": float(np.mean(t)),
            "median_ms": float(np.median(t)),
            "p95_ms": float(np.percentile(t, 95)),
            "max_ms": float(np.max(t)),
        }

    machine = read_machine(run_dir)
    maps = read_maps(run_dir)

    # --- figure
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(6.4, 5.6), dpi=150)
    g, e = ref.positions_xyz, est_aligned.positions_xyz
    ax.plot(g[:, 0], g[:, 1], color="#444444", lw=2.2, label="Ground truth")
    ax.plot(e[:, 0], e[:, 1], color="#d1495b", lw=1.2, label=f"{args.algorithm} (SE(3)-aligned)")
    ax.plot(g[0, 0], g[0, 1], "o", color="#444444", ms=5)
    ax.set_xlabel("x [m]")
    ax.set_ylabel("y [m]")
    ax.set_aspect("equal", adjustable="datalim")
    ax.grid(alpha=0.3)
    ax.set_title(f"{args.seq}: ATE RMSE {ate_rmse:.3f} m, drift {drift_pct:.2f}%")
    ax.legend(loc="best", fontsize=8)
    fig.tight_layout()
    fig.savefig(out / "traj.png")
    plt.close(fig)

    result = {
        "sequence": args.seq,
        "tag": args.tag,
        "algorithm": args.algorithm,
        "commit": machine.get("orbslam3_commit", ""),
        "gt_source": str(gt_src),
        "est_source": str(est_src),
        "matched_poses": int(n_matched),
        "est_time_span_s": float(est_span[1] - est_span[0]),
        "ate_rmse_m": float(ate_rmse),
        "rpe_1m_rmse_m": float(rpe_rmse),
        "rpe_1m_mean_m": float(rpe_mean),
        "gt_length_m": gt_len,
        "est_length_m": est_len,
        "final_error_m": final_err,
        "drift_pct": drift_pct,
        "start_align_m": args.start_align_m,
        "final_error_start_aligned_m": final_err_start,
        "drift_start_aligned_pct": 100.0 * final_err_start / gt_len,
        "max_error_start_aligned_m": float(err_start.max()),
        "coverage": coverage,
        "config": machine.get("config", ""),
        "timing": timing,
        "maps_in_atlas": maps,
        "machine": machine,
    }
    (out / "metrics.json").write_text(json.dumps(result, indent=2))

    # --- sanity checks from the task sheet
    print(f"\n== {args.seq} [{args.tag}] ==")
    print(f"ATE RMSE      {ate_rmse:.4f} m")
    print(f"RPE 1 m RMSE  {rpe_rmse:.4f} m")
    print(f"length        gt {gt_len:.2f} m / est {est_len:.2f} m")
    print(f"drift         {drift_pct:.2f} %  (final error {final_err:.3f} m)")
    print(f"drift (start-aligned on first {args.start_align_m:g} m) {100*final_err_start/gt_len:.2f} %  "
          f"(final error {final_err_start:.3f} m, max {err_start.max():.3f} m)")
    print(f"coverage      {100*coverage:.1f} % of the ground-truth time span")
    if timing:
        print(f"time/frame    mean {timing['mean_ms']:.1f} ms, p95 {timing['p95_ms']:.1f} ms")
    warn = []
    if ate_rmse > 0.5:
        warn.append("ATE > 0.5 m: check timestamp units, frames, and that -a was used")
    # scale check on ~1 Hz decimated poses so per-frame jitter doesn't inflate length
    step = max(1, int(round(n_matched / max(1.0, est_span[1] - est_span[0]))))
    ratio = path_length(est.positions_xyz[::step]) / path_length(ref.positions_xyz[::step])
    result["length_ratio_1hz"] = ratio
    (out / "metrics.json").write_text(json.dumps(result, indent=2))
    if abs(ratio - 1) > 0.10:
        warn.append(f"est/gt length ratio {ratio:.2f}: possible scale error")
    if coverage < 0.9:
        warn.append(f"trajectory covers only {100*coverage:.0f}% of the sequence (tracking lost / map discarded)")
    if maps is not None and maps > 1:
        warn.append(f"{maps} maps in atlas: tracking was lost at least once")
    if not timing:
        warn.append("no times_*.txt: timing patch not applied?")
    if not machine:
        warn.append("no machine.txt: record CPU/GPU next to the timing numbers")
    for w in warn:
        print("WARNING:", w)
    if not warn:
        print("sanity checks passed")
    print(f"-> {out}")


if __name__ == "__main__":
    main()
