#!/usr/bin/env python3
"""Make ORB-SLAM3's stereo_inertial_euroc example write per-frame logs.

1. times_<run>.txt   TrackStereo() time per frame in ms. ORB-SLAM3 already measures it
                     (vTimesTrack) but never saves it.
2. states_<run>.txt  "t_ns state" per frame, from SLAM.GetTrackingState() right after
                     TrackStereo(): 1 = not initialised, 2 = OK, 3 = recently lost, 4 = lost
                     (enum eTrackingState in include/Tracking.h).
3. online_<run>.txt  "t_ns state map_changed tx ty tz qx qy qz qw": the ONLINE pose
                     returned by TrackStereo() for that frame (camera 0 in world, Twc), i.e.
                     what the drone would send to PX4 at that moment. The usual
                     f_<run>.txt is written at the end, after later bundle adjustments
                     have refined every pose, so it is smoother than anything available
                     in flight. map_changed = SLAM.MapChanged() (IMU init, loop closure,
                     merge: a big map correction happened since the previous frame).

All of this is read-only logging in the example program; the SLAM algorithm is unchanged.
The pose is copied out of the value TrackStereo() already returns; MapChanged() and
GetTrackingState() only read counters. Each patch is applied once, so rerunning is safe.

Usage: python3 patch_orbslam3_timing.py <path/to/stereo_inertial_euroc.cc>
"""
import sys
from pathlib import Path

# (marker, anchor, new text, mode) - mode "after": insert after anchor; "replace": replace anchor
PATCHES = [
    (
        "// CS1 timing patch",
        "SLAM.SaveKeyFrameTrajectoryEuRoC(kf_file);",
        """
        {   // CS1 timing patch: per-frame TrackStereo() time in ms
            const string t_file = "times_" + string(argv[argc-1]) + ".txt";
            ofstream ft(t_file.c_str());
            ft << fixed;
            for (int k = 0; k < nImages[0]; k++) ft << setprecision(3) << 1e3 * vTimesTrack[k] << endl;
            ft.close();
            cout << "Saved per-frame times to " << t_file << endl;
        }""",
        "after",
    ),
    (
        "// CS1 online patch (declare)",
        "vTimesTrack.resize(tot_images);",
        """
    struct CS1Rec { double t; int state; int changed; float p[3]; float q[4]; };  // CS1 online patch (declare)
    vector<CS1Rec> cs1_rec;
    cs1_rec.reserve(tot_images);""",
        "after",
    ),
    (
        "// CS1 online patch (keep pose)",
        "SLAM.TrackStereo(imLeft,imRight,tframe,vImuMeas);",
        "Sophus::SE3f cs1_Tcw = SLAM.TrackStereo(imLeft,imRight,tframe,vImuMeas);  // CS1 online patch (keep pose)",
        "replace",
    ),
    (
        "// CS1 online patch (record)",
        "vTimesTrack[ni]=ttrack;",
        """
            {   // CS1 online patch (record): outside the timed region
                CS1Rec r;
                r.t = tframe;
                r.state = SLAM.GetTrackingState();
                r.changed = SLAM.MapChanged() ? 1 : 0;
                const Sophus::SE3f Twc = cs1_Tcw.inverse();
                const Eigen::Vector3f p = Twc.translation();
                const Eigen::Quaternionf q = Twc.unit_quaternion();
                r.p[0] = p.x(); r.p[1] = p.y(); r.p[2] = p.z();
                r.q[0] = q.x(); r.q[1] = q.y(); r.q[2] = q.z(); r.q[3] = q.w();
                cs1_rec.push_back(r);
            }""",
        "after",
    ),
    (
        "// CS1 online patch (save)",
        "SLAM.SaveKeyFrameTrajectoryEuRoC(kf_file);",
        """
        {   // CS1 online patch (save): tracking state + online pose per frame
            const string s_file = "states_" + string(argv[argc-1]) + ".txt";
            const string o_file = "online_" + string(argv[argc-1]) + ".txt";
            ofstream fs(s_file.c_str()), fo(o_file.c_str());
            fs << fixed; fo << fixed;
            for (size_t k = 0; k < cs1_rec.size(); k++) {
                const CS1Rec& r = cs1_rec[k];
                fs << setprecision(0) << 1e9 * r.t << " " << r.state << endl;
                fo << setprecision(0) << 1e9 * r.t << " " << r.state << " " << r.changed << setprecision(7);
                for (int j = 0; j < 3; j++) fo << " " << r.p[j];
                for (int j = 0; j < 4; j++) fo << " " << r.q[j];
                fo << endl;
            }
            fs.close(); fo.close();
            cout << "Saved per-frame states / online poses to " << s_file << ", " << o_file << endl;
        }""",
        "after",
    ),
]


def main() -> int:
    path = Path(sys.argv[1])
    src = path.read_text()
    changed = False
    for marker, anchor, text, mode in PATCHES:
        if marker in src:
            print(f"already applied: {marker}")
            continue
        if src.count(anchor) != 1:
            print(f"ERROR: anchor '{anchor}' not found exactly once in {path}", file=sys.stderr)
            return 1
        src = src.replace(anchor, text if mode == "replace" else anchor + text)
        changed = True
        print(f"applied: {marker}")
    for hdr in ("fstream", "iomanip"):
        if f"<{hdr}>" not in src:
            src = f"#include <{hdr}>\n" + src
            changed = True
    if changed:
        path.write_text(src)
    print(f"patched: {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
