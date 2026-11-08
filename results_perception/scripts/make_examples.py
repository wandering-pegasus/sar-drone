"""Annotated example frames (boxes + keypoints) with FACES BLURRED -> results_perception/examples/.
Heads are pixelated from the pose keypoints (nose/eyes/ears) BEFORE drawing; on frames where no model finds a
person, the hand-labelled ground-truth box (sofa video) is pixelated instead. Run: python make_examples.py"""
import csv
from pathlib import Path
import cv2, numpy as np
from ultralytics import YOLO

ROOT = Path(__file__).resolve().parents[2]; OUT = ROOT / "results_perception/examples"; OUT.mkdir(exist_ok=True)
FPS = 30000 / 1001
MODELS = {k: YOLO(f"yolo11{k}-pose.pt") for k in "nsm"}

def frame(video, t):
    cap = cv2.VideoCapture(str(next((ROOT / "videos").glob(video + ".*")))); cap.set(cv2.CAP_PROP_POS_FRAMES, int(round(t * FPS)))
    ok, f = cap.read(); assert ok; return f, int(round(t * FPS))

def pred(img, k, imgsz=640): return MODELS[k].predict(img, imgsz=imgsz, conf=0.25, device="mps", verbose=False)[0]

def pixelate(img, cx, cy, r, circle=True):
    h, w = img.shape[:2]; x1, y1, x2, y2 = int(max(0, cx - r)), int(max(0, cy - r)), int(min(w, cx + r)), int(min(h, cy + r))
    if x2 <= x1 or y2 <= y1: return
    roi = img[y1:y2, x1:x2]; small = cv2.resize(roi, (max(1, (x2-x1)//14), max(1, (y2-y1)//14)), interpolation=cv2.INTER_LINEAR)
    pix = cv2.resize(small, (x2-x1, y2-y1), interpolation=cv2.INTER_NEAREST)
    if circle:
        mask = np.zeros(roi.shape[:2], np.uint8); cv2.circle(mask, ((x2-x1)//2, (y2-y1)//2), min(x2-x1, y2-y1)//2, 255, -1)
        roi[mask > 0] = pix[mask > 0]
    else: roi[:] = pix

def blur_heads(img, results):
    for r in results:
        if r.keypoints is None: continue
        for kp, box in zip(r.keypoints.data.cpu().numpy(), r.boxes.xyxy.cpu().numpy()):
            head = kp[:5][kp[:5, 2] > 0.3]; bh = box[3] - box[1]; bw = box[2] - box[0]
            if len(head):
                c = head[:, :2].mean(0); ext = max(np.ptp(head[:, 0]) if len(head) > 1 else 0, np.ptp(head[:, 1]) if len(head) > 1 else 0)
                rad = max(0.10 * max(bh, bw), 1.4 * ext, 24)
            else:   # no head keypoints: pixelate the whole box top part
                c = np.array([(box[0] + box[2]) / 2, box[1] + 0.12 * bh]); rad = max(0.18 * bh, 0.3 * bw, 30)
            pixelate(img, c[0], c[1], rad * 1.2)

def draw(raw, res, title, blurred, x0=20):
    img = res.plot(img=blurred.copy(), labels=False, line_width=3)
    cv2.rectangle(img, (0, 0), (img.shape[1], 70), (0, 0, 0), -1); cv2.putText(img, title, (x0, 48), cv2.FONT_HERSHEY_SIMPLEX, 1.4, (255, 255, 255), 3)
    return img

def blurred_frame(raw, imgsz=640):
    b = raw.copy()
    for k in "msn": blur_heads(b, [pred(raw, k, imgsz)])       # union of all three models' head locations
    return b

def save(name, img, scale=1.0):
    if scale != 1: img = cv2.resize(img, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
    cv2.imwrite(str(OUT / name), img, [cv2.IMWRITE_JPEG_QUALITY, 88])

# ex1: success, person fully visible
raw, f = frame("hide_and_return", 20.5); b = blurred_frame(raw)
save("ex1_success_standing_yolo11m.jpg", draw(raw, pred(raw, "m"), "yolo11m-pose | hide_and_return t=20.5s | OK", b), 0.6)

# ex2: person stepping out from behind the wall (partly hidden), all three models
raw, f = frame("hide_and_return", 37.9); b = blurred_frame(raw)
panels = []
for k in "nsm":
    res = pred(raw, k)
    panels.append(draw(raw, res, f"yolo11{k}-pose: " + ("found" if len(res.boxes) else "MISSED") + " (partly behind wall)", b, x0=170)[:, 150:1250])
save("ex2_partly_behind_wall_n_s_m.jpg", np.hstack([cv2.resize(p, None, fx=0.45, fy=0.45) for p in panels]))

# ex3: sofa, success (m, default 640)
raw, f = frame("lying_sofa", 10.68); b = blurred_frame(raw)
img = draw(raw, pred(raw, "m"), "yolo11m-pose | lying_sofa t=10.7s | person A found (B missed)", b)
save("ex3_sofa_yolo11m_finds_one_of_two.jpg", img, 0.6)

# ex4: sofa, failure for all three at 640 px; GT boxes shown (pixelated inside)
gt = {r["person"]: [float(r[k]) for k in ("x1", "y1", "x2", "y2")] for r in csv.DictReader(open(ROOT / "results_perception/ground_truth_sofa_boxes.csv")) if int(r["frame"]) == int(round(14.55 * FPS))}
raw, f = frame("lying_sofa", 14.55); b = raw.copy()
for p, g in gt.items(): b[int(g[1]):int(g[3]), int(g[0]):int(g[2])] = cv2.resize(cv2.resize(b[int(g[1]):int(g[3]), int(g[0]):int(g[2])], (6, 4), interpolation=cv2.INTER_AREA), (int(g[2])-int(g[0]), int(g[3])-int(g[1])), interpolation=cv2.INTER_NEAREST)
panels = []
for k in "nsm":
    res = pred(raw, k); img = draw(raw, res, f"yolo11{k}-pose: {'false box only' if len(res.boxes) else 'nothing found'}", b)
    for p, g in gt.items():
        cv2.rectangle(img, tuple(int(v) for v in g[:2]), tuple(int(v) for v in g[2:]), (0, 255, 255), 3)
        cv2.putText(img, "person (ground truth)", (int(g[0]) - 40, int(g[1]) - 12), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 255, 255), 2)
    panels.append(img)
save("ex4_failure_sofa_small_people_n_s_m.jpg", np.vstack([cv2.resize(np.vstack([p[:70], p[200:800]]), None, fx=0.6, fy=0.6) for p in panels]))
print(sorted(p.name for p in OUT.iterdir()))
