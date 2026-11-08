# results_perception - Victim detection, Round 2 (CS2, Jay)

Pretrained YOLO11-pose (n / s / m) on three own videos, run on a MacBook with Apple GPU (MPS). Results are in
[`results_perception/`](./); the ~150-word paragraph for the plan is
[`results_perception/writeup.md`](writeup.md).

**Machine for all latency numbers:** MacBook Pro (Mac16,1), Apple M4, 16 GB, macOS 27.2, Python 3.14.6, Ultralytics 8.4.204, torch 2.15.0.
**GPU for all VRAM numbers:** RTX 3050 6GB Laptop GPU (Thu Hang's laptop; `vram.csv` is copied unchanged).

## Headline numbers
| | yolo11n-pose | yolo11s-pose | yolo11m-pose |
|---|---|---|---|
| Latency per frame, MPS, total mean (ms) - MacBook Pro M4 | 13.1 | 15.1 | 31.9 |
| Same on CPU (ms) - MacBook Pro M4 | 20.3 | 38.0 | 74.6 |
| Detection: person standing, lit room (%) | 100 | 100 | 100 |
| Detection: two people lying on sofas, small/partly covered (%) | 1.8 | 3.7 | 11.3 |
| Same at imgsz 1280 (supplement) (%) | 32.1 | 46.4 | 50.3 |
| Training VRAM peak, tiger-pose 640 px - RTX 3050 6GB Laptop GPU (MiB) | 2,706 (batch 16) | 4,340 (batch 16) | 4,506 (batch 8; OOM at batch 16) |

## Files
```
README.md                      this file
requirements.txt               pip packages
scripts/
  run_models.py                  run n/s/m on all videos -> per-frame CSVs + annotated videos
  make_ground_truth_sofa.py      ground-truth boxes for lying_sofa (label once, propagate by camera tracking)
  evaluate.py                    detection rates -> detection.csv, detection_detail.csv
  measure_latency.py             latency -> latency.csv, latency_extra.csv
  supplement_imgsz.py            lying_sofa at imgsz 1280 (not default settings)
  make_examples.py               example frames with blurred faces
  make_figure.py                 figure for the writeup
results_perception/
  detection.csv                detection rate per model and video (task-sheet table)
  detection_detail.csv         partial / hidden / per-person breakdown
  latency.csv                  latency per model on the Mac (lying_sofa video, MPS)
  latency_extra.csv            all videos, raw r.speed vs synchronised, CPU check
  vram.csv                     from Thu Hang's NVIDIA laptop, UNCHANGED
  detection_test.md            test setup, definitions, failure notes, self-check
  examples/                    4 annotated frames, faces blurred (ex4 is a failure case)
  writeup.md                   ~150-word paragraph + figure + 2 tables
  figure_latency_detection.png
  mps_check.txt                output of the MPS check (task 1 evidence)
  ground_truth_sofa_boxes.csv  ground-truth boxes per frame (lying_sofa)
  supplement_sofa_imgsz.csv    supplement results
  per_frame/                   raw per-frame detections (all boxes) for every model x video
```
Videos and annotated videos are **not in git** (faces); share them by link (`videos/`, `annotated_videos/` in the repo root, git-ignored).

## Reproduce (macOS with Apple Silicon)
```bash
python3 -m venv yolo && source yolo/bin/activate
pip install -r results_perception/requirements.txt

# 1) the Mac GPU must be available (must print True)
python -c "import torch; print(torch.backends.mps.is_available())"

# 2) put the 3 videos (names below) in ./videos/
#    videos/hide_and_return.MOV   videos/standing_clothes.MOV   videos/lying_sofa.MOV

python results_perception/scripts/run_models.py              # models download automatically; ~10 min incl. annotated videos (add --no-video to skip them)
python results_perception/scripts/make_ground_truth_sofa.py  # ground truth for lying_sofa
python results_perception/scripts/evaluate.py                # -> detection.csv, detection_detail.csv
python results_perception/scripts/measure_latency.py         # -> latency.csv, latency_extra.csv (do not run other GPU jobs meanwhile)
python results_perception/scripts/supplement_imgsz.py 1280   # optional supplement
python results_perception/scripts/make_examples.py && python results_perception/scripts/make_figure.py
```
Default settings everywhere (conf 0.25, imgsz 640) except the supplement. The sofa ground truth is tied to the
video (reference frame 360 / t = 12.0 s), so other videos need their own labels.

## Task status (self-check table of the task sheet)
| # | Task | Status | Evidence |
|---|---|---|---|
| 1 | Set up the Mac | Done | `results_perception/mps_check.txt`, commands above |
| 2 | Record test videos | **Partly** - 3 videos exist but not the planned scenes (no dark/lit-room lying videos) | `results_perception/detection_test.md` |
| 3 | Run the models | Done (n, s, m on all 3 videos) | `annotated_videos/` (share link needed) |
| 4 | Detection rate | Done for the videos recorded | `detection.csv`, `detection_test.md` |
| 5 | Latency | Done | `latency.csv` |
| 6 | Example frames | Done (4 frames, 1 failure case, heads pixelated) | `examples/` |
| 7 | Merge VRAM results | Done (file copied byte-for-byte, GPU named) | `vram.csv` |
| 8 | Write for the plan | Drafted - **needs review by Thu Hang** | `writeup.md` |
| 9 | Push to the repo | Done - see the commit on `main` of `wandering-pegasus/sar-drone` | git log |
