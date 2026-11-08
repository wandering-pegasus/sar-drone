"""Run yolo11n/s/m-pose on every video in videos/ (device=mps, conf=0.25, imgsz=640).

Writes, for each model x video:
  results_perception/per_frame/<video>__<model>.csv   per-frame detections
  annotated_videos/<video>__<model>.mp4               boxes + keypoints drawn
Usage:  python run_models.py [--device mps] [--no-video]
"""
import argparse, csv, subprocess, sys, tempfile, os
from pathlib import Path
import cv2
from ultralytics import YOLO

ROOT = Path(__file__).resolve().parents[2]
VIDEOS = ["hide_and_return", "standing_clothes", "lying_sofa"]
MODELS = ["yolo11n-pose", "yolo11s-pose", "yolo11m-pose"]
CONF, IMGSZ = 0.25, 640

ap = argparse.ArgumentParser()
ap.add_argument("--device", default="mps")
ap.add_argument("--no-video", action="store_true")
args = ap.parse_args()

(ROOT / "results_perception/per_frame").mkdir(parents=True, exist_ok=True)
(ROOT / "annotated_videos").mkdir(exist_ok=True)

for vid in VIDEOS:
    src = next((ROOT / "videos").glob(vid + ".*"))
    fps = cv2.VideoCapture(str(src)).get(cv2.CAP_PROP_FPS)
    for mname in MODELS:
        model = YOLO(mname + ".pt")
        rows, writer, tmp = [], None, None
        for i, r in enumerate(model.predict(str(src), stream=True, imgsz=IMGSZ, conf=CONF,
                                            device=args.device, verbose=False)):
            n = len(r.boxes)
            confs = r.boxes.conf.cpu().tolist()
            best = r.boxes.xyxy[confs.index(max(confs))].cpu().tolist() if n else [""] * 4
            allb = ";".join(f"{x1:.0f},{y1:.0f},{x2:.0f},{y2:.0f},{c:.2f}"
                            for (x1, y1, x2, y2), c in zip(r.boxes.xyxy.cpu().tolist(), confs))
            rows.append([i, round(i / fps, 3), n, round(max(confs), 3) if n else 0,
                         *[round(v, 1) if v != "" else "" for v in best],
                         round(r.speed["preprocess"], 2), round(r.speed["inference"], 2),
                         round(r.speed["postprocess"], 2), allb])
            if not args.no_video:
                img = r.plot()
                if writer is None:
                    h, w = img.shape[:2]
                    tmp = tempfile.NamedTemporaryFile(suffix=".mp4", delete=False).name
                    writer = cv2.VideoWriter(tmp, cv2.VideoWriter_fourcc(*"mp4v"), fps, (w, h))
                writer.write(img)
        if writer:
            writer.release()
            out = ROOT / "annotated_videos" / f"{vid}__{mname}.mp4"
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", tmp, "-c:v", "libx264",
                            "-crf", "26", "-pix_fmt", "yuv420p", str(out)], check=True)
            os.unlink(tmp)
        with open(ROOT / f"results_perception/per_frame/{vid}__{mname}.csv", "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["frame", "t_s", "n_boxes", "max_conf", "x1", "y1", "x2", "y2",
                        "pre_ms", "inf_ms", "post_ms", "all_boxes_x1y1x2y2conf"])
            w.writerows(rows)
        print(vid, mname, len(rows), "frames", flush=True)
