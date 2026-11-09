#!/usr/bin/env python3
"""Build results/summary.md from results/<seq>/metrics.json (+ reruns).

Usage: python3 eval/make_summary.py
"""
import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
RES = REPO / "results"
SEQS = ["MH_01_easy", "V1_01_easy"]


def fmt(x, nd=3):
    return "–" if x is None else f"{x:.{nd}f}"


def machine_str(m: dict) -> str:
    cpu = m.get("cpu", "?")
    cores = m.get("cores", "")
    ram = m.get("ram", "")
    gpu = m.get("gpu", "")
    s = f"{cpu}"
    if cores:
        s += f", {cores} cores"
    if ram:
        s += f", {ram} RAM"
    if gpu and not gpu.startswith("none"):
        s += f", {gpu}"
    return s


def main() -> None:
    rows, reruns, notes = [], [], []
    for seq in SEQS:
        f = RES / seq / "metrics.json"
        if not f.exists():
            rows.append(f"| {seq} | (not run yet) | | | | | | | |")
            continue
        r = json.loads(f.read_text())
        t = r.get("timing") or {}
        rows.append(
            f"| {seq} | {r['algorithm']} | {fmt(r['ate_rmse_m'])} | {fmt(r['rpe_1m_rmse_m'])} | "
            f"{fmt(r['gt_length_m'], 1)} | {fmt(r['drift_pct'], 2)} | "
            f"{fmt(t.get('mean_ms'), 1)} | {fmt(t.get('p95_ms'), 1)} | {machine_str(r.get('machine', {}))} |"
        )
        if r.get("maps_in_atlas") not in (None, 1):
            notes.append(f"- {seq}: {r['maps_in_atlas']} maps in atlas (tracking lost at least once).")
        if "V1_01" in seq:
            notes.append(f"- {seq}: ground truth = OpenVINS-corrected trajectory "
                         "(original EuRoC V1_01 ground truth has inaccurate orientation).")
        for rf in sorted((RES / seq / "reruns").glob("*/metrics.json")):
            rr = json.loads(rf.read_text())
            reruns.append(
                f"| {seq} | {r['tag']} vs {rr['tag']} | {fmt(r['ate_rmse_m'])} / {fmt(rr['ate_rmse_m'])} | "
                f"{fmt(r['drift_pct'], 2)} / {fmt(rr['drift_pct'], 2)} | "
                f"{fmt(r['gt_length_m'], 1)} / {fmt(rr['gt_length_m'], 1)} | "
                f"{fmt((r.get('timing') or {}).get('mean_ms'), 1)} / {fmt((rr.get('timing') or {}).get('mean_ms'), 1)} | "
                f"{fmt((r.get('timing') or {}).get('p95_ms'), 1)} / {fmt((rr.get('timing') or {}).get('p95_ms'), 1)} |"
            )
        commit = r.get("commit")

    lines = [
        "# Round 2 results: VI-SLAM on EuRoC",
        "",
        "ATE: RMSE of absolute translation error after SE(3) alignment (evo `-a`, no scale).  ",
        "RPE: RMSE of translation error over 1 m segments.  ",
        "Drift: final position error after alignment / ground-truth path length × 100.  ",
        "Time/frame: wall time of `TrackStereo()` per stereo frame (tracking thread; "
        "local mapping and loop closing run in parallel threads).",
        "",
        "| Sequence | Algorithm | ATE RMSE (m) | RPE 1 m (m) | Trajectory length (m) | Drift (%) | Mean time/frame (ms) | p95 (ms) | Machine |",
        "|---|---|---|---|---|---|---|---|---|",
        *rows,
        "",
        "Configuration: default `Examples/Stereo-Inertial/EuRoC.yaml`, no per-sequence tuning.",
    ]
    try:
        lines.append(f"ORB-SLAM3 commit: `{commit}`")
    except NameError:
        pass
    if notes:
        lines += ["", "Notes:", *notes]
    if reruns:
        lines += ["", "## Repeatability", "",
                  "| Sequence | Runs | ATE (m) | Drift (%) | Length (m) | Mean (ms) | p95 (ms) |",
                  "|---|---|---|---|---|---|---|", *reruns, "",
                  "Length is measured over the poses matched to ground truth, so it changes slightly "
                  "with how quickly ORB-SLAM3 initialises in each run. Timing varies between runs "
                  "because ORB-SLAM3's mapping threads and the OS scheduler are not deterministic."]
    (RES / "summary.md").write_text("\n".join(lines) + "\n")
    print((RES / "summary.md").read_text())


if __name__ == "__main__":
    main()
