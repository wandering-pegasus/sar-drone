"""SUPPLEMENT (not default settings): lying_sofa at larger input sizes, same ground truth/matching as
evaluate.py (frames 4.0-21.0 s, person counted if >=80 % of its GT box is inside the image, IoU >= 0.2).
Writes results_perception/supplement_sofa_imgsz.csv. Usage: python supplement_imgsz.py [1280 ...]"""
import csv, sys
from pathlib import Path
import numpy as np
from ultralytics import YOLO

ROOT = Path(__file__).resolve().parents[2]; R = ROOT / "results_perception"
SIZES = [int(a) for a in sys.argv[1:]] or [1280]
FPS = 30000 / 1001
MODELS = ["yolo11n-pose", "yolo11s-pose", "yolo11m-pose"]
persons = ["A_black_pants_left_sofa", "B_white_top_right_sofa"]
gt = {}
for r in csv.DictReader(open(R / "ground_truth_sofa_boxes.csv")):
    gt.setdefault(int(r["frame"]), {})[r["person"]] = (tuple(float(r[k]) for k in ("x1", "y1", "x2", "y2")), float(r["inside_frac"]))
def iou(a, b):
    ix = max(0, min(a[2], b[2]) - max(a[0], b[0])); iy = max(0, min(a[3], b[3]) - max(a[1], b[1])); i = ix * iy
    return i / ((a[2]-a[0])*(a[3]-a[1]) + (b[2]-b[0])*(b[3]-b[1]) - i + 1e-9)
lo, hi = int(4.0 * FPS), int(21.0 * FPS)
out = []
for sz in SIZES:
    for m in MODELS:
        model = YOLO(m + ".pt"); found = {p: 0 for p in persons}; tot = {p: 0 for p in persons}; fp = sc = 0; ms = []
        for f, r in enumerate(model.predict(str(ROOT / "videos/lying_sofa.MOV"), stream=True, imgsz=sz, conf=0.25, device="mps", verbose=False)):
            if f < lo or f > hi: continue
            bs = r.boxes.xyxy.cpu().tolist(); vis = [p for p in persons if gt[f][p][1] >= 0.8]
            if not vis: continue
            sc += 1; matched = set()
            for p in vis:
                tot[p] += 1; hit = [i for i, b in enumerate(bs) if iou(b, gt[f][p][0]) >= 0.2]
                if hit: found[p] += 1; matched.update(hit)
            fp += any(i not in matched for i in range(len(bs)))
        out.append([m, sz, f"{100*sum(found.values())/sum(tot.values()):.1f}", f"{100*found[persons[0]]/tot[persons[0]]:.1f}",
                    f"{100*found[persons[1]]/tot[persons[1]]:.1f}", f"{100*fp/sc:.1f}"])
        print(out[-1], flush=True)
with open(R / "supplement_sofa_imgsz.csv", "w", newline="") as fh:
    w = csv.writer(fh); w.writerow(["model", "imgsz", "instance_recall_pct", "person_A_pct", "person_B_pct", "frames_with_false_box_pct"]); w.writerows(out)
