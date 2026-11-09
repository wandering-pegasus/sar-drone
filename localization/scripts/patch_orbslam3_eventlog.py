#!/usr/bin/env python3
"""Add the keyframe timestamp to ORB-SLAM3's existing event prints (log-only change).

ORB-SLAM3 prints "end VIBA 1/2" (IMU initialisation steps that rotate/shift the world
frame) and "*Loop detected" / "*Merge detected" (map corrections), but without a time.
Knowing *when* they happened is needed to evaluate the online pose fairly: until
"end VIBA 2" the world frame is still being re-aligned, so the online pose jumps.

Changes (text of the prints only; no algorithm change):
  src/LocalMapping.cc  "end VIBA 1"      -> "end VIBA 1 t=<keyframe time, s>"
                       "end VIBA 2"      -> "end VIBA 2 t=<keyframe time, s>"
  src/LoopClosing.cc   "*Loop detected"  -> "*Loop detected t=<keyframe time, s>"
                       "*Merge detected" -> "*Merge detected t=<keyframe time, s>"

Usage: python3 patch_orbslam3_eventlog.py <ORB_SLAM3 dir>     (idempotent)
"""
import sys
from pathlib import Path

PATCHES = {
    "src/LocalMapping.cc": [
        ('cout << "end VIBA 1" << endl;',
         'cout << "end VIBA 1 t=" << std::to_string(mpCurrentKeyFrame->mTimeStamp) << endl;  // CS1 event log'),
        ('cout << "end VIBA 2" << endl;',
         'cout << "end VIBA 2 t=" << std::to_string(mpCurrentKeyFrame->mTimeStamp) << endl;  // CS1 event log'),
    ],
    "src/LoopClosing.cc": [
        ('Verbose::PrintMess("*Merge detected", Verbose::VERBOSITY_QUIET);',
         'Verbose::PrintMess("*Merge detected t=" + std::to_string(mpCurrentKF->mTimeStamp), '
         'Verbose::VERBOSITY_QUIET);  // CS1 event log'),
        ('Verbose::PrintMess("*Loop detected", Verbose::VERBOSITY_QUIET);',
         'Verbose::PrintMess("*Loop detected t=" + std::to_string(mpCurrentKF->mTimeStamp), '
         'Verbose::VERBOSITY_QUIET);  // CS1 event log'),
    ],
}


def main() -> int:
    root = Path(sys.argv[1])
    for rel, reps in PATCHES.items():
        p = root / rel
        src = p.read_text()
        for old, new in reps:
            if new in src:
                print(f"already applied in {rel}: {old[:40]}")
                continue
            if src.count(old) != 1:
                print(f"ERROR: '{old}' not found exactly once in {rel}", file=sys.stderr)
                return 1
            src = src.replace(old, new)
            print(f"applied in {rel}: {old[:40]}")
        p.write_text(src)
    return 0


if __name__ == "__main__":
    sys.exit(main())
