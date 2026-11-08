# Detection test: setup and failure notes

All latency numbers: **MacBook Pro (Mac16,1), Apple M4, 16 GB, macOS 27.2, Ultralytics 8.4.204, torch 2.15.0, Python 3.14.6**, device `mps` unless stated.
All VRAM numbers: **RTX 3050 6GB Laptop GPU** (Thu Hang's laptop, `vram.csv`, ultralytics 8.4.203, torch 2.15.0+cu132).
The two machines are different, so latency (Mac) and VRAM (RTX 3050 6GB Laptop GPU) must not be compared with each other.

## Setup
- Models: pretrained `yolo11n-pose`, `yolo11s-pose`, `yolo11m-pose` (downloaded automatically, no training).
- Settings: **defaults - conf 0.25, imgsz 640**. The only deviation is the clearly labelled supplement below (imgsz 1280).
- Videos (own phone recordings, 1920x1080, 29.97 fps, HEVC; kept out of git, share by link):

| id | file | length | content |
|---|---|---|---|
| `hide_and_return` | one person go out (hide behind the wall) and go in.MOV | 92.9 s / 2786 frames | one person walks behind a wall/door and back, 10 times; lit room |
| `standing_clothes` | one person stand and clothes on the table.MOV | 13.5 s / 406 frames | person standing, camera pans to a table with clothes/laptop and back; lit room |
| `lying_sofa` | two people lying on the sofa.MOV | 27.4 s / 822 frames | handheld walk-around; two people lying on two sofas along the far wall, partly behind chairs and tables |

**Deviation from the task sheet:** the sheet asks for `lying_room`, `lying_dark`, `lying_covered`. The recorded videos are different scenes: only `lying_sofa` contains lying people (and it is the "partly covered" case); **there is no dim/dark video and no lit-room video of a lying person**. Consequently the "dark corridor" part of the self-check could not be tested. Re-recording `lying_dark` is recommended.

## How the detection rate is defined
Rate = frames in which the model found the person / frames in which the person is in view (default threshold 0.25).
- **`hide_and_return`**: *hidden* = person fully behind the wall (runs of >= 15 frames where the smoothed any-model detection signal is < 25 %; checked by eye on dense frame strips at 0.25 s steps). *partial* = within 0.75 s of a hidden run (person half behind the wall). *clear* = everything else. Hidden frames are removed from the rate (task-sheet rule: "trim frames where nobody is in view"); they are used to count false alarms. Headline = *clear* frames.
- **`standing_clothes`**: hand-labelled segments (clear 0-3.4 s, partial 3.4-6.2 s, hidden 6.2-8.1 s, partial 8.1-8.75 s, clear 8.75 s-end) from dense frame strips.
- **`lying_sofa`**: two people. Their boxes were labelled once by hand (t = 12.0 s) and propagated to all frames by tracking camera motion (ORB + RANSAC homographies; `make_ground_truth_sofa.py`), then checked by eye every second. Scored window: 4.0-21.0 s, a person is counted only while >= 80 % of their box is inside the image (511 frames, 891 person-instances). A person is "found" if any detected box overlaps their box with IoU >= 0.2. The headline is found person-instances / person-instances. People that are partly behind chairs/tables are still counted (that is the point of the test).
- For the two single-person videos a detected box is assumed to be the person (spot-checked on annotated frames; frames with 2+ boxes: n/s/m 0/0/0 on clear frames of `hide_and_return`).

## Results (`detection.csv`, `detection_detail.csv`)
| Video | Frames scored | n (%) | s (%) | m (%) |
|---|---|---|---|---|
| hide_and_return, clear | 1648 | 100.0 | 100.0 | 100.0 |
| hide_and_return, partial (half behind wall) | 466 | 64.8 | 68.5 | 74.2 |
| hide_and_return, hidden (false alarms) | 672 | 0.0 | 0.6 | 1.5 |
| standing_clothes, clear | 245 | 100.0 | 100.0 | 100.0 |
| standing_clothes, partial (at image edge) | 104 | 70.2 | 76.0 | 77.9 |
| standing_clothes, hidden (false alarms) | 57 | 0.0 | 1.8 | 1.8 |
| lying_sofa, all person-instances | 891 | 1.8 | 3.7 | 11.3 |
| lying_sofa, left-sofa person (black trousers) | 511 | 2.9 | 6.5 | 19.8 |
| lying_sofa, right-sofa person (white top) | 380 | 0.3 | 0.0 | 0.0 |

## Failure notes
1. **Small, distant, partly covered lying people (`lying_sofa`) are the main failure.** At 640 px the people are only ~100-250 px wide in the 1920 px frame; the models find the left-sofa person in 3-20 % of frames and the right-sofa person (white clothing against a dark sofa, partly behind a table and chairs) almost never. yolo11m-pose finds lying people about 3x as often as yolo11s-pose (11.3 % vs 3.7 %), but both are far from usable; the 640 px resize is a large part of the problem (see supplement).
2. **False boxes** on furniture (chairs, tables, a ceiling light) appear in 2.5 / 2.9 / 3.7 % of scored `lying_sofa` frames (n/s/m) and in the close-up chair frames before the window (e.g. 1.6-3.4 s).
3. **Person half behind a wall or at the image edge**: detection falls to 65-78 %; larger models cope better (n < s < m in both videos). Thin slivers (a few pixels of arm/leg behind the door edge) are sometimes found by m but not by n/s.
4. **False alarms when nobody is in view** are rare: 0-1.8 % of hidden frames (a few isolated frames).
5. Motion blur and camera pans (frames 2-4 s of `lying_sofa`, close-up of a chair) give no usable detections; these frames are outside the scored window.

## Supplement (not default settings): larger input size on `lying_sofa`
Same ground truth and matching, `supplement_imgsz.py`, device mps, conf 0.25:

| model | imgsz | all instances (%) | left-sofa (%) | right-sofa (%) | frames with a false box (%) |
|---|---|---|---|---|---|
| yolo11n-pose | 1280 | 32.1 | 54.6 | 1.8 | 13.5 |
| yolo11s-pose | 1280 | 46.4 | 76.7 | 5.5 | 4.9 |
| yolo11m-pose | 1280 | 50.3 | 87.3 | 0.5 | 8.2 |

A larger input size helps a lot (m: 11 % -> 50 %), but latency also grows (not measured at 1280 here) and the right-sofa person is still essentially not found. This should be one of the first things tried in Phase 1 (higher resolution / tiling, then fine-tuning on lying people).

## Latency (`latency.csv`, `latency_extra.csv`)
- Per frame, 1080p input resized to 640, default settings, first 10 frames skipped, `lying_sofa` video (812 frames measured). Mean of preprocess / inference / postprocess and the p95 of inference.
- **Timing method:** on MPS, Ultralytics does not synchronise the GPU, so its `r.speed["inference"]` only measures queuing the work (3.5 / 3.6 / 4.4 ms mean) and the rest lands in "postprocess" (8.1 / 10.0 / 26.0 ms). The headline numbers use `torch.mps.synchronize()` around each stage; the sum pre+inf+post is the same either way (12.3 / 14.3 / 31.2 ms raw vs 13.1 / 15.1 / 31.9 ms synced). The raw numbers are kept in `latency_extra.csv` (`timing = raw r.speed`).
- Latency on the other two videos is within ~1 ms (see `latency_extra.csv`).
- CPU check (`device=cpu`, first 160 frames of `lying_sofa`): 20.3 / 38.0 / 74.6 ms total for n / s / m, i.e. 1.5x / 2.5x / 2.3x slower than MPS, so the Mac GPU is being used.

## Self-check (task sheet, page 6-7)
| Check | Result |
|---|---|
| `cpu` clearly slower than `mps` | **Yes** - n 20.3 vs 13.1 ms, s 38.0 vs 15.1 ms, m 74.6 vs 31.9 ms (total per frame) |
| Latency grows n -> s -> m | **Yes** - 13.1 -> 15.1 -> 31.9 ms (MPS, synced) |
| Detection lower in the dim corridor and when partly covered than in the lit room | **Partly / not testable**: no dark video exists. Partly covered (`lying_sofa`) is far lower than lit/uncovered (`hide_and_return`, `standing_clothes`): 1.8-11.3 % vs 100 %. But that video also differs in distance and posture, so the comparison is not a controlled test. |
| Frames without a person trimmed | **Yes** - hidden frames excluded from the rate and reported separately |
| Machine next to every latency number, GPU name next to every VRAM number | Yes (this file, `latency.csv`, `writeup.md`, `README.md`) |

## Notes
- Annotated videos (all 3 models x 3 videos) are in `annotated_videos/` locally (not in git); share them by link. They were rendered in the first run; per-frame CSVs were produced by an identical second run (same models, settings and device) to also store all boxes.
- Example frames in `examples/` have heads pixelated (from keypoints; ground-truth boxes pixelated in ex4).
