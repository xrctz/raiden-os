"""Trigger something in the VM and grab a burst of screenshots right after it
(to see animations), over one QMP connection.

    qmpburst.py SOCK OUT_PREFIX COUNT INTERVAL [click X Y | key COMBO | drag X1 Y1 X2 Y2] [--screen WxH]
writes OUT_PREFIX-00.ppm, -01.ppm, ...
"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import qmp  # noqa: E402

args = sys.argv[1:]
sock_path, prefix, count, interval = args[0], args[1], int(args[2]), float(args[3])
rest = args[4:]
q = qmp.QMP(sock_path)
size = qmp.screen_size(sock_path, rest)
if rest[:1] == ["click"]:
    x, y = float(rest[1]), float(rest[2])
    q.cmd("input-send-event", events=qmp.abs_event(x, y, size))
    time.sleep(0.08)
    q.cmd("input-send-event", events=[qmp.btn("left", True)])
    time.sleep(0.06)
    q.cmd("input-send-event", events=[qmp.btn("left", False)])
elif rest[:1] == ["drag"]:
    # press, then move in steps while capturing, release at the end
    x1, y1, x2, y2 = (float(v) for v in rest[1:5])
    q.cmd("input-send-event", events=qmp.abs_event(x1, y1, size))
    time.sleep(0.1)
    q.cmd("input-send-event", events=[qmp.btn("left", True)])
    time.sleep(0.15)
    start = time.time()
    for i in range(count):
        f = min(1.0, (i + 1) / (count * 0.6))
        q.cmd("input-send-event", events=qmp.abs_event(x1 + (x2 - x1) * f, y1 + (y2 - y1) * f, size))
        time.sleep(interval)
        q.cmd("screendump", filename=f"{prefix}-{i:02d}.ppm")
    q.cmd("input-send-event", events=[qmp.btn("left", False)])
    print(f"{count} frames in {time.time() - start:.2f} s (drag)")
    sys.exit(0)
elif rest[:1] == ["key"]:
    q.cmd("send-key", keys=[{"type": "qcode", "data": k} for k in rest[1].split("-")],
          **{"hold-time": 80})
start = time.time()
for i in range(count):
    q.cmd("screendump", filename=f"{prefix}-{i:02d}.ppm")
    time.sleep(interval)
print(f"{count} frames in {time.time() - start:.2f} s")
