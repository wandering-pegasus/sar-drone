"""Detection rate per model x video from results_perception/per_frame/*.csv.

Ground truth ("is a person in view?") per video:
  hide_and_return   Person walks behind a door/wall and back (10 times). HIDDEN = runs of >= 15 consecutive
                    frames where the smoothed (17-frame) any-model detection signal is < 25 % (checked by eye on
                    dense frame strips: person fully behind the wall; isolated detections inside a hidden run
                    count as false alarms). PARTIAL = within 0.75 s of a hidden run (person half behind
                    the wall). CLEAR = everything else.
  standing_clothes  Hand-labelled time segments (see SEGMENTS): person clear / leaving or entering at the image
                    edge (partial) / not in view (hidden).
  lying_sofa        Two people lying on sofas. Boxes labelled once and propagated (make_ground_truth_sofa.py).
                    Counted: frames 4.0-21.0 s, a person only if >= 80 % of its box is inside the image.
                    A person counts as found if any detected box has IoU >= 0.2 with its GT box.
Headline detection rate = found / person-frames over the CLEAR frames (single-person videos) or over all scored
person-instances (sofa; people are small and partly behind chairs/tables there).
Outputs: results_perception/detection_detail.csv  and  results_perception/detection.csv
"""
import csv
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
R = ROOT / "results_perception"
MODELS = ["yolo11n-pose", "yolo11s-pose", "yolo11m-pose"]
FPS = 30000 / 1001

# standing_clothes, seconds: (start, end, label)
SEGMENTS = {"standing_clothes": [(0.0, 3.4, "clear"), (3.4, 6.2, "partial"), (6.2, 8.1, "hidden"),
                                 (8.1, 8.75, "partial"), (8.75, 99, "clear")]}

def load(v, m):
    rows = list(csv.DictReader(open(R / f"per_frame/{v}__{m}.csv")))
    n = np.array([int(r["n_boxes"]) for r in rows])
    boxes = [[tuple(map(float, b.split(","))) for b in r["all_boxes_x1y1x2y2conf"].split(";") if b] for r in rows]
    return n, boxes

def iou(a, b):
    ix = max(0, min(a[2], b[2]) - max(a[0], b[0])); iy = max(0, min(a[3], b[3]) - max(a[1], b[1]))
    i = ix * iy
    return i / ((a[2]-a[0])*(a[3]-a[1]) + (b[2]-b[0])*(b[3]-b[1]) - i + 1e-9)

def labels_single(v, ns):
    N = len(ns[0]); lab = np.array(["clear"] * N, dtype=object)
    if v in SEGMENTS:
        for a, b, l in SEGMENTS[v]:
            lab[int(a * FPS):min(N, int(b * FPS) + 1)] = l
        return lab
    union = ((ns[0] > 0) | (ns[1] > 0) | (ns[2] > 0)).astype(float)          # hide_and_return
    smooth = np.convolve(union, np.ones(17) / 17, mode="same")                # robust to isolated sliver detections
    none = smooth < 0.25
    i = 0
    hidden = np.zeros(N, bool)
    while i < N:
        if none[i]:
            j = i
            while j < N and none[j]: j += 1
            if j - i >= 15: hidden[i:j] = True
            i = j
        else: i += 1
    lab[hidden] = "hidden"
    k = int(0.75 * FPS); idx = np.where(hidden)[0]
    near = np.zeros(N, bool)
    for t in idx: near[max(0, t - k):t + k + 1] = True
    lab[near & ~hidden] = "partial"
    return lab

detail, summary = [], {}
for v in ["hide_and_return", "standing_clothes"]:
    data = {m: load(v, m) for m in MODELS}
    lab = labels_single(v, [data[m][0] for m in MODELS])
    for m in MODELS:
        n = data[m][0]
        for l in ("clear", "partial", "hidden"):
            sel = lab == l
            detail.append([v, m, l, int(sel.sum()), f"{100*(n[sel]>0).mean():.1f}" if sel.any() else "",
                           int((n[sel] >= 2).sum())])
        summary[(v, m)] = (int((lab == "clear").sum()), 100 * (n[lab == "clear"] > 0).mean())
        summary[(v, m, "partial")] = 100 * (n[lab == "partial"] > 0).mean()
        summary[(v, m, "hidden")] = 100 * (n[lab == "hidden"] > 0).mean()

# ---- lying_sofa (instance level) ----
gt = {}
for r in csv.DictReader(open(R / "ground_truth_sofa_boxes.csv")):
    gt.setdefault(int(r["frame"]), {})[r["person"]] = (tuple(float(r[k]) for k in ("x1", "y1", "x2", "y2")), float(r["inside_frac"]))
lo, hi = int(4.0 * FPS), int(21.0 * FPS)
persons = ["A_black_pants_left_sofa", "B_white_top_right_sofa"]
for m in MODELS:
    n, boxes = load("lying_sofa", m)
    found = {p: 0 for p in persons}; tot = {p: 0 for p in persons}
    any_found = any_tot = fp_frames = scored_frames = 0
    for f in range(lo, hi + 1):
        vis = [p for p in persons if gt[f][p][1] >= 0.8]
        if not vis: continue
        scored_frames += 1
        hitp = 0; matched_boxes = set()
        for p in vis:
            tot[p] += 1
            hit = [bi for bi, b in enumerate(boxes[f]) if iou(b[:4], gt[f][p][0]) >= 0.2]
            if hit: found[p] += 1; hitp += 1; matched_boxes.update(hit)
        any_tot += 1; any_found += hitp > 0
        fp_frames += any(bi not in matched_boxes for bi in range(len(boxes[f])))
    inst = sum(found.values()) / sum(tot.values()) * 100
    summary[("lying_sofa", m)] = (sum(tot.values()), inst)
    detail.append(["lying_sofa", m, "instances_in_window", sum(tot.values()), f"{inst:.1f}", ""])
    for p in persons:
        detail.append(["lying_sofa", m, "person_" + p, tot[p], f"{100*found[p]/max(1,tot[p]):.1f}", ""])
    detail.append(["lying_sofa", m, "frames_with_>=1_person_found", any_tot, f"{100*any_found/any_tot:.1f}", ""])
    detail.append(["lying_sofa", m, "frames_with_unmatched_box(false_alarm)", scored_frames, f"{100*fp_frames/scored_frames:.1f}", ""])
    summary[("lying_sofa", m, "fp")] = 100 * fp_frames / scored_frames
    summary[("lying_sofa", m, "frames")] = scored_frames

with open(R / "detection_detail.csv", "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["video", "model", "frame_class", "frames", "pct_frames_with_detection_or_found", "frames_with_2plus_boxes"])
    w.writerows(detail)

import json
json.dump({"|".join(map(str, k)): v for k, v in summary.items()}, open("/tmp/_unused.json", "w")) if False else None
for r in detail: print(r)

# ---- detection.csv in the task-sheet layout ----
def S(v, m, k=None): return summary[(v, m) if k is None else (v, m, k)]
fmt = lambda x: f"{x:.1f}"
fails = {
 "hide_and_return": "Person half behind the wall: found in {pn}/{ps}/{pm}% of those frames (n/s/m); sliver detections inside fully-hidden frames (false alarms) {hn}/{hs}/{hm}%",
 "standing_clothes": "Person leaving/entering at the image edge: found in {pn}/{ps}/{pm}% of those frames (n/s/m); false alarms when nobody in view {hn}/{hs}/{hm}%",
 "lying_sofa": "Two small, distant people lying on sofas (roughly 100-250 px wide in a 1920 px frame), partly behind chairs/tables (640 px input): right-sofa person found in 0-0.3% of frames; left-sofa person found in {an}/{as_}/{am}% (n/s/m); false boxes on furniture in {fn}/{fs}/{fm}% of frames; with imgsz 1280 (supplement) instance rate rises to 32.1/46.4/50.3%",
}
rows = []
for v, label in [("hide_and_return", "hide_and_return"), ("standing_clothes", "standing_clothes"), ("lying_sofa", "lying_sofa")]:
    d = dict(zip("nsm", MODELS))
    if v == "lying_sofa":
        pa = {m: next(float(r[4]) for r in detail if r[0] == v and r[1] == m and r[2] == "person_A_black_pants_left_sofa") for m in MODELS}
        txt = fails[v].format(an=fmt(pa[MODELS[0]]), as_=fmt(pa[MODELS[1]]), am=fmt(pa[MODELS[2]]),
                              fn=fmt(S(v, MODELS[0], "fp")), fs=fmt(S(v, MODELS[1], "fp")), fm=fmt(S(v, MODELS[2], "fp")))
        frames = f"{S(v, MODELS[0])[0]} person-instances in {S(v, MODELS[0], 'frames')} frames"
    else:
        txt = fails[v].format(pn=fmt(S(v, MODELS[0], "partial")), ps=fmt(S(v, MODELS[1], "partial")), pm=fmt(S(v, MODELS[2], "partial")),
                              hn=fmt(S(v, MODELS[0], "hidden")), hs=fmt(S(v, MODELS[1], "hidden")), hm=fmt(S(v, MODELS[2], "hidden")))
        frames = S(v, MODELS[0])[0]
    rows.append([label, frames] + [fmt(S(v, m)[1]) for m in MODELS] + [txt])
with open(R / "detection.csv", "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["Video", "Frames (person clearly in view)", "yolo11n-pose (%)", "yolo11s-pose (%)", "yolo11m-pose (%)", "Where it fails"])
    w.writerows(rows)
