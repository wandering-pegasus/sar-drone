"""Latency of yolo11n/s/m-pose on the Mac (default settings: conf 0.25, imgsz 640).

Per frame Ultralytics reports r.speed = {preprocess, inference, postprocess} in ms.
On MPS (Apple GPU) work is queued asynchronously and Ultralytics does NOT synchronise for MPS,
so part of the GPU time shows up in "postprocess". We therefore time with torch.mps.synchronize()
(mode "synced", the headline numbers) and also record "raw" (r.speed exactly as the task-sheet
script would give it). The first 10 frames are warm-up and are skipped.

Writes: results_perception/latency.csv              synced, device=mps, headline video (lying_sofa)
        results_perception/latency_extra.csv        all videos x {mps synced, mps raw, cpu (first 150 frames)}
"""
import csv, platform, subprocess, sys
from pathlib import Path
import numpy as np, torch, ultralytics
import ultralytics.utils.ops as ops
from ultralytics import YOLO

ROOT = Path(__file__).resolve().parents[2]
MODELS = ["yolo11n-pose", "yolo11s-pose", "yolo11m-pose"]
VIDEOS = ["lying_sofa", "hide_and_return", "standing_clothes"]
HEADLINE = "lying_sofa"
WARMUP = 10

_orig_time = ops.Profile.time
def _synced_time(self):
    torch.mps.synchronize()
    import time; return time.perf_counter()

hw = subprocess.run(["system_profiler", "SPHardwareDataType"], capture_output=True, text=True).stdout
get = lambda k: next(l.split(":", 1)[1].strip() for l in hw.splitlines() if l.strip().startswith(k))
MACHINE = f"{get('Model Name')} ({get('Model Identifier')}), {get('Chip')}, {get('Memory')}"
OS = f"macOS {platform.mac_ver()[0]}"
VERS = f"ultralytics {ultralytics.__version__}; torch {torch.__version__}"

def run(model, src, device, synced, max_frames=None):
    ops.Profile.time = _synced_time if synced else _orig_time
    pre, inf, post = [], [], []
    for i, r in enumerate(model.predict(str(src), stream=True, imgsz=640, conf=0.25, device=device, verbose=False)):
        if i >= WARMUP:
            pre.append(r.speed["preprocess"]); inf.append(r.speed["inference"]); post.append(r.speed["postprocess"])
        if max_frames and i + 1 >= max_frames: break
    pre, inf, post = map(np.array, (pre, inf, post))
    return dict(frames=len(inf), pre=pre.mean(), inf_mean=inf.mean(), inf_p95=np.percentile(inf, 95),
                post=post.mean(), total=(pre + inf + post).mean(), total_p95=np.percentile(pre + inf + post, 95))

fields = ["model", "machine", "device", "imgsz", "preprocess_ms", "inference_mean_ms", "inference_p95_ms",
          "postprocess_ms", "total_mean_ms", "total_p95_ms", "frames_measured", "video", "timing", "os", "software"]
def row(m, v, dev, timing, d):
    return [m, MACHINE, dev, 640, f"{d['pre']:.1f}", f"{d['inf_mean']:.1f}", f"{d['inf_p95']:.1f}", f"{d['post']:.1f}",
            f"{d['total']:.1f}", f"{d['total_p95']:.1f}", d["frames"], v, timing, OS, VERS]

head, extra = [], []
for v in VIDEOS:
    src = next((ROOT / "videos").glob(v + ".*"))
    for m in MODELS:
        model = YOLO(m + ".pt")
        run(model, src, "mps", True, 30)                                  # extra warm-up of the model itself
        d = run(model, src, "mps", True);  extra.append(row(m, v, "mps", "synced", d))
        if v == HEADLINE: head.append(row(m, v, "mps", "synced", d))
        d = run(model, src, "mps", False); extra.append(row(m, v, "mps", "raw r.speed", d))
        print(v, m, "done", flush=True)
src = next((ROOT / "videos").glob(HEADLINE + ".*"))
for m in MODELS:                                                          # CPU sanity check
    model = YOLO(m + ".pt")
    d = run(model, src, "cpu", False, 160); extra.append(row(m, HEADLINE, "cpu", "r.speed (first 160 frames)", d))
    print("cpu", m, flush=True)
ops.Profile.time = _orig_time

for name, rows in (("latency.csv", head), ("latency_extra.csv", extra)):
    with open(ROOT / "results_perception" / name, "w", newline="") as f:
        w = csv.writer(f); w.writerow(fields); w.writerows(rows)
