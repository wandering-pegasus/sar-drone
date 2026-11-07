# sar-drone

Open-source drone for search and rescue where GPS does not work (inside buildings, under collapsed structures, in tunnels).
The drone finds its own position with a camera and motion sensor (visual-inertial SLAM) and detects and tracks victims lying on the ground, running on a Jetson Orin Nano.

Team **Wandering Pegasus**, National Yang Ming Chiao Tung University (NYCU), 11th TSMC Youth Dream Program.

## Folders

| Folder | What goes in it | Owner |
|---|---|---|
| `localization/` | VI-SLAM tests (EuRoC), trajectory error and drift results | Kevin |
| `results_perception/` | Victim detection tests: detection rate, latency, VRAM, example frames | Jay |
| `hardware/` | Parts list, block diagram, weight and flight-time estimates | Capybara (水豚) |
| `evaluation/` | Evaluation framework and metrics | Judy |
| `docs/` | Plan, figures and shared documents | Thu Hang |

Each folder has its own README saying how to rerun its results.
Do not commit videos or large files; share them by link.
