"""Figure for the plan: (a) latency per model on the Mac (MPS, synced) with CPU for comparison,
(b) detection rate per model and video. Reads latency.csv / latency_extra.csv / detection.csv."""
import csv
from pathlib import Path
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt, numpy as np
R = Path(__file__).resolve().parents[2] / "results_perception"
lat = list(csv.DictReader(open(R / "latency.csv"))); ext = list(csv.DictReader(open(R / "latency_extra.csv")))
cpu = {r["model"]: float(r["total_mean_ms"]) for r in ext if r["device"] == "cpu"}
det = list(csv.DictReader(open(R / "detection.csv")))
models = [r["model"] for r in lat]; short = [m.replace("yolo11", "").replace("-pose", "") for m in models]
fig, ax = plt.subplots(1, 2, figsize=(11, 4.2))
x = np.arange(3); w = 0.38
for i, (k, c) in enumerate([("preprocess_ms", "#9ecae1"), ("inference_mean_ms", "#3182bd"), ("postprocess_ms", "#08519c")]):
    bottom = np.array([sum(float(r[j]) for j in ["preprocess_ms", "inference_mean_ms", "postprocess_ms"][:i]) for r in lat])
    ax[0].bar(x - w/2, [float(r[k]) for r in lat], w, bottom=bottom, color=c, label=k.split("_")[0] + " (MPS)")
ax[0].bar(x + w/2, [cpu[m] for m in models], w, color="#bdbdbd", label="total (CPU)")
for i, r in enumerate(lat): ax[0].text(i - w/2, float(r["total_mean_ms"]) + 1, r["total_mean_ms"], ha="center", fontsize=9)
for i, m in enumerate(models): ax[0].text(i + w/2, cpu[m] + 1, f"{cpu[m]:.0f}", ha="center", fontsize=9)
ax[0].set_xticks(x, [f"yolo11{s}-pose" for s in short]); ax[0].set_ylabel("ms per 1080p frame (mean)")
ax[0].set_title("(a) Latency, MacBook Pro (Mac16,1), Apple M4\nlying_sofa video, imgsz 640", fontsize=10); ax[0].legend(fontsize=8)
names = ["hide_and_return\n(1 person, lit)", "standing_clothes\n(1 person, lit)", "lying_sofa\n(2 lying people,\nsmall/far)"]
cols = ["#9ecae1", "#3182bd", "#08519c"]
for i, c in enumerate(["yolo11n-pose (%)", "yolo11s-pose (%)", "yolo11m-pose (%)"]):
    v = [float(r[c]) for r in det]; b = ax[1].bar(np.arange(3) + (i - 1) * 0.26, v, 0.26, color=cols[i], label=c.replace(" (%)", ""))
    for xx, vv in zip(np.arange(3) + (i - 1) * 0.26, v): ax[1].text(xx, vv + 1.5, f"{vv:.0f}", ha="center", fontsize=8)
ax[1].set_xticks(np.arange(3), names, fontsize=8); ax[1].set_ylim(0, 125); ax[1].set_ylabel("detection rate (%)")
ax[1].set_title("(b) Detection rate (conf 0.25, imgsz 640)\nframes with the person clearly in view", fontsize=10); ax[1].legend(fontsize=8, loc="upper right", ncol=3)
plt.tight_layout(); plt.savefig(R / "figure_latency_detection.png", dpi=150)
