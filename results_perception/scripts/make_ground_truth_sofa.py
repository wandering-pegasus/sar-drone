"""Ground truth for lying_sofa: two people lying on sofas, hand-labelled ONCE at t=12.0 s
(frame 360) and propagated to every frame by chaining ORB+RANSAC homographies between
consecutive frames (the sofas sit against a wall, the camera pans). The result is checked by eye
(see check sheets in the notes) and written to results_perception/ground_truth_sofa_boxes.csv
(frame, person, x1,y1,x2,y2 in 1920x1080 pixels, inside = fraction of the box inside the image).
"""
import csv
from pathlib import Path
import cv2, numpy as np

ROOT = Path(__file__).resolve().parents[2]
REF_FRAME = 360
REF_BOXES = {"A_black_pants_left_sofa": (690, 420, 870, 555),
             "B_white_top_right_sofa": (1360, 440, 1530, 515)}
SC = 0.5   # work at half resolution

cap = cv2.VideoCapture(str(ROOT / "videos/lying_sofa.MOV"))
grays = []
while True:
    ok, f = cap.read()
    if not ok: break
    grays.append(cv2.cvtColor(cv2.resize(f, None, fx=SC, fy=SC), cv2.COLOR_BGR2GRAY))
n = len(grays)
orb = cv2.ORB_create(3000)
bf = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True)
kp = [orb.detectAndCompute(g, None) for g in grays]

def H_between(i, j):          # maps points in frame i -> frame j
    (ki, di), (kj, dj) = kp[i], kp[j]
    if di is None or dj is None: return None
    m = bf.match(di, dj)
    if len(m) < 20: return None
    p = np.float32([ki[x.queryIdx].pt for x in m]); q = np.float32([kj[x.trainIdx].pt for x in m])
    H, inl = cv2.findHomography(p, q, cv2.RANSAC, 3.0)
    return H if H is not None and inl.sum() >= 15 else None

# H_to_ref[i]: frame i -> reference frame
H_to_ref = [None] * n
H_to_ref[REF_FRAME] = np.eye(3)
for i in range(REF_FRAME - 1, -1, -1):      # backwards: i -> i+1 -> ref
    H = H_between(i, i + 1)
    H_to_ref[i] = H_to_ref[i + 1] @ H if (H is not None and H_to_ref[i + 1] is not None) else None
for i in range(REF_FRAME + 1, n):           # forwards: i -> i-1 -> ref
    H = H_between(i, i - 1)
    H_to_ref[i] = H_to_ref[i - 1] @ H if (H is not None and H_to_ref[i - 1] is not None) else None

W, Hh = 1920, 1080
out = []
for i in range(n):
    if H_to_ref[i] is None: continue
    Hi = np.linalg.inv(H_to_ref[i])           # ref -> frame i (half-res coordinates)
    for name, (x1, y1, x2, y2) in REF_BOXES.items():
        pts = np.float32([[x1, y1], [x2, y1], [x2, y2], [x1, y2]]) * SC
        q = cv2.perspectiveTransform(pts[None], Hi)[0] / SC
        bx1, by1, bx2, by2 = q[:, 0].min(), q[:, 1].min(), q[:, 0].max(), q[:, 1].max()
        ix = max(0, min(bx2, W) - max(bx1, 0)); iy = max(0, min(by2, Hh) - max(by1, 0))
        inside = ix * iy / max(1e-6, (bx2 - bx1) * (by2 - by1))
        out.append([i, name, round(bx1, 1), round(by1, 1), round(bx2, 1), round(by2, 1), round(inside, 3)])
with open(ROOT / "results_perception/ground_truth_sofa_boxes.csv", "w", newline="") as fh:
    w = csv.writer(fh); w.writerow(["frame", "person", "x1", "y1", "x2", "y2", "inside_frac"]); w.writerows(out)
print("frames", n, "with GT", len(out) // 2)
