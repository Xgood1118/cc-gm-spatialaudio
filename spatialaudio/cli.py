# -*- coding: utf-8 -*-
import argparse
import json

import spatialaudio as m
from spatialaudio.core import BASE_FREQ, SPEED_OF_SOUND


def _freq(samples, rate):
    """上穿零检测（线性插值）估计信号频率。"""
    crossings = []
    prev = samples[0]
    for i in range(1, len(samples)):
        cur = samples[i]
        if prev <= 0.0 < cur:
            crossings.append(i - cur / (cur - prev))
        prev = cur
    if len(crossings) < 2:
        return 0.0
    return (len(crossings) - 1) * rate / (crossings[-1] - crossings[0])


def main():
    ap = argparse.ArgumentParser(description="spatialaudio")
    ap.add_argument("path")
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    d = json.load(open(a.path, encoding="utf-8"))
    l = m.Listener(d["listener"]["pos"], d["listener"]["forward"])
    ss = [m.Source(s["pos"], s["vel"], s["gain"], s["occluded"]) for s in d["sources"]]

    rate = 48000
    frame = 0.1
    frames = 10
    left, right = [], []
    recovery = None
    released = False
    count = 0
    for _ in range(frames):
        lf, rf = m.render_frame(l, ss, frame, rate)
        left.extend(lf)
        right.extend(rf)
        if not released:
            # 第一帧后解除全部遮挡，观察恢复过程
            for s in ss:
                s.occluded = False
            released = True
        if recovery is None:
            count += 1
            if all(s._occ <= 0.01 for s in ss):
                recovery = count

    peak = max(max(map(abs, left)), max(map(abs, right)))
    max_diff = max(abs(x - y) for x, y in zip(left, right))

    # 多普勒偏差：对每个运动源单独渲染测频，与理论值比较
    dev = 0.0
    for s in ss:
        dx = s.pos[0] - l.pos[0]
        dy = s.pos[1] - l.pos[1]
        dz = s.pos[2] - l.pos[2]
        dist = (dx * dx + dy * dy + dz * dz) ** 0.5
        if dist == 0.0:
            continue
        vr = (s.vel[0] * dx + s.vel[1] * dy + s.vel[2] * dz) / dist
        if vr == 0.0:
            continue
        probe = m.Source(s.pos, s.vel, s.gain, False)
        pl, _ = m.render_frame(l, [probe], 0.5, rate)
        meas = _freq(pl, rate)
        theory = BASE_FREQ * SPEED_OF_SOUND / (SPEED_OF_SOUND + vr)
        if theory > 0.0:
            dev = max(dev, abs(meas - theory) / theory)

    result = {
        "sample_rate": rate,
        "frames": frames,
        "mix_peak": round(peak, 6),
        "doppler_deviation": round(dev, 6),
        "max_channel_diff": round(max_diff, 6),
        "occlusion_recovery_frames": recovery,
    }
    text = json.dumps(result, ensure_ascii=False, indent=2)
    if a.out:
        with open(a.out, "w", encoding="utf-8") as f:
            f.write(text + "\n")
    print(text)


if __name__ == "__main__":
    main()
