#!/usr/bin/env python3
"""Build results/extra/summary.md: MH_04_difficult runs and loop-closure on/off comparison.

Reads metrics.json written by eval/evaluate.py:
  with loop closure    results/<seq>/metrics.json (Round 2) and results/extra/MH_04_difficult/metrics.json
  without              results/extra/noLC/<seq>/metrics.json
Usage: python3 eval/make_extra_summary.py
"""
import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
RES = REPO / "results"
EXTRA = RES / "extra"
SEQS = ["MH_01_easy", "V1_01_easy", "MH_04_difficult"]


def load(p: Path):
    return json.loads(p.read_text()) if p.exists() else None


def lc_metrics(seq):
    return load(EXTRA / seq / "metrics.json") or load(RES / seq / "metrics.json")


def f(x, nd=3):
    return "–" if x is None else f"{x:.{nd}f}"


def row(seq, label, r):
    if r is None:
        return f"| {seq} | {label} | (not run) | | | | | | |"
    t = r.get("timing") or {}
    return (f"| {seq} | {label} | {f(r['ate_rmse_m'])} | {f(r['rpe_1m_rmse_m'])} | "
            f"{f(r['drift_pct'], 2)} | {f(r.get('drift_start_aligned_pct'), 2)} | "
            f"{f(r.get('max_error_start_aligned_m'))} | {f(100 * r['coverage'], 0) if 'coverage' in r else '–'} | "
            f"{f(t.get('mean_ms'), 1)} / {f(t.get('p95_ms'), 1)} |")


def main():
    lines = [
        "# Round 2 follow-up: hard sequence and loop closure off",
        "",
        "Same pipeline as Round 2: ORB-SLAM3 stereo-inertial, default `EuRoC.yaml`; same machine (Intel Xeon",
        "Platinum 8480+, 16 cores, no GPU). The *no loop closure* runs use `configs/EuRoC_noLC.yaml`, which",
        "is the default config plus `loopClosing: 0` (switches off place recognition, loop correction and map merging).",
        "",
        "- **Drift (global)**: final error after SE(3) alignment of the whole trajectory (Round 2 definition).",
        "- **Drift (start-aligned)**: SE(3) alignment on the first 5 m only, then the final error divided by the",
        "  path length. Closer to a flight that starts at a known pose and is never corrected afterwards.",
        "- **Max err (start-aligned)**: the largest position error anywhere along the path under that alignment.",
        "- **Coverage**: share of the sequence covered by the saved trajectory. ORB-SLAM3 saves only its largest",
        "  map, so frames lost before or after it do not count.",
        "",
        "**Loop closure never fired in any run** (no `*Loop detected` / `*Merge detected` in any log, including",
        "the Round 2 runs). Switching it off therefore changes nothing; differences between on/off rows are",
        "run-to-run variation. The low Round 2 drift comes from ORB-SLAM3 re-using its map in these small rooms",
        "and from scoring the end-of-run, refined trajectory, not from loop closure.",
        "",
        "| Sequence | Loop closure | ATE RMSE (m) | RPE 1 m (m) | Drift global (%) | Drift start-aligned (%) | Max err start-aligned (m) | Coverage (%) | ms/frame mean / p95 |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for seq in SEQS:
        lines.append(row(seq, "on (default)", lc_metrics(seq)))
        lines.append(row(seq, "**off**", load(EXTRA / "noLC" / seq / "metrics.json")))
    rr = load(EXTRA / "MH_04_difficult" / "reruns" / "run2" / "metrics.json")
    if rr:
        lines += ["", ("MH_04_difficult run2 (loop closure on, repeatability): ATE {:.3f} m, drift {:.2f} %, "
                       "coverage {:.0f} %, {:.1f} / {:.1f} ms.").format(
            rr["ate_rmse_m"], rr["drift_pct"], 100 * rr["coverage"],
            rr["timing"]["mean_ms"], rr["timing"]["p95_ms"])]
    on_rows = []
    for seq in SEQS:
        for tag, label in (("LC", "on (default)"), ("noLC", "**off**")):
            r = load(EXTRA / "online" / f"{seq}_{tag}" / "metrics_online.json")
            if r is None:
                on_rows.append(f"| {seq} | {label} | (not run) | | | | | | |")
                continue
            s10, s30 = r["segment_drift"].get("10m"), r["segment_drift"].get("30m")
            on_rows.append(
                f"| {seq} | {label} | {r['eval_start_s']:.0f}–{r['eval_end_s']:.0f} s, {r['evaluated_length_m']:.0f} m | "
                f"{f(r['ate_rmse_m'])} | {f(r['start_aligned_drift_pct'], 2)} | {f(r['start_aligned_max_error_m'], 2)} | "
                f"{f(s10['mean_pct'], 2) + ' / ' + f(s10['max_pct'], 2) if s10 else '–'} | "
                f"{f(s30['mean_pct'], 2) + ' / ' + f(s30['max_pct'], 2) if s30 else '–'} | "
                f"{len(r['loop_closures_s'])} / {len(r['map_merges_s'])} |")
    if any("(not run)" not in x for x in on_rows):
        lines += [
            "", "## Online pose (what the drone would send to PX4)", "",
            "The tables above use ORB-SLAM3's saved trajectory, which is refined after the fact. Here the pose",
            "returned by `TrackStereo()` at each frame is scored instead (`eval/evaluate_online.py`), starting 1 s",
            "after IMU initialisation finished (last `end VIBA 2`). **Segment drift** = relative translation",
            "error over every 10 m / 30 m sub-path ÷ its length (30 m = our target loop). No alignment needed.",
            "",
            "| Sequence | Loop closure | Evaluated | ATE RMSE (m) | Drift start-aligned (%) | Max err start-aligned (m) | 10 m drift mean / max (%) | 30 m drift mean / max (%) | Loops / merges |",
            "|---|---|---|---|---|---|---|---|---|",
            *on_rows,
        ]
    s = load(EXTRA / "MH_04_difficult" / "struggle.json")
    if s:
        lines += ["", "## MH_04_difficult: where tracking struggles", "",
                  f"Per-frame tracking state (diagnostic run): {s['frames_per_state']}.",
                  f"Not-OK intervals (s from sequence start): {s['not_ok_intervals_s']}.",
                  f"Saved trajectory covers {s['saved_trajectory_span_s'][0]}–{s['saved_trajectory_span_s'][1]} s "
                  f"of {s['sequence_span_s']} s.",
                  "Figure: `results/extra/MH_04_difficult/struggle.png`."]
    (EXTRA / "summary.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
