# -*- coding: utf-8 -*-
import json
import math
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import spatialaudio as mod  # noqa: E402
import spatialaudio.core as core  # noqa: E402

DATA = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")


def _rms(xs):
    return math.sqrt(sum(x * x for x in xs) / len(xs))


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


def _first_crossing(samples):
    """首个上穿零位置（线性插值，样本单位）。"""
    prev = samples[0]
    for i in range(1, len(samples)):
        cur = samples[i]
        if prev <= 0.0 < cur:
            return i - cur / (cur - prev)
        prev = cur
    return 0.0


def _goertzel(samples, freq, rate):
    """单频幅度（Goertzel），用于比较低通前后的谐波占比。"""
    w = 2.0 * math.pi * freq / rate
    c = 2.0 * math.cos(w)
    s1 = s2 = 0.0
    for x in samples:
        s0 = x + c * s1 - s2
        s2 = s1
        s1 = s0
    return 2.0 * math.sqrt(max(s1 * s1 + s2 * s2 - c * s1 * s2, 0.0)) / len(samples)


def _scene():
    d = json.load(open(os.path.join(DATA, "scene.json"), encoding="utf-8"))
    l = mod.Listener(d["listener"]["pos"], d["listener"]["forward"])
    ss = [mod.Source(s["pos"], s["vel"], s["gain"], s["occluded"]) for s in d["sources"]]
    return l, ss


def test_attenuation_monotone():
    l, _ = _scene()
    near = mod.render_frame(l, [mod.Source([1.0, 0, 0], [0, 0, 0], 1.0, False)], 0.05, 8000)
    far = mod.render_frame(l, [mod.Source([4.0, 0, 0], [0, 0, 0], 1.0, False)], 0.05, 8000)
    assert max(map(abs, near[0])) > max(map(abs, far[0]))


def test_reference_distance_unity():
    l, _ = _scene()
    out = mod.render_frame(l, [mod.Source([1.0, 0, 0], [0, 0, 0], 1.0, False)], 0.05, 8000)
    assert max(map(abs, out[0])) > 0.5


def test_occluded_attenuated():
    l, _ = _scene()
    open_ = mod.render_frame(l, [mod.Source([2.0, 0, 0], [0, 0, 0], 1.0, False)], 0.05, 8000)
    closed = mod.render_frame(l, [mod.Source([2.0, 0, 0], [0, 0, 0], 1.0, True)], 0.05, 8000)
    assert max(map(abs, closed[0])) < max(map(abs, open_[0]))


def test_mix_no_clipping():
    ch = [[1.5, -1.5, 0.2], [1.5, -1.5, 0.2]]
    out = mod.mix(ch)
    assert max(map(abs, out)) <= 1.0 + 1e-9


def test_side_discrimination():
    l, _ = _scene()
    left = mod.render_frame(l, [mod.Source([0.0, 2.0, 0], [0, 0, 0], 1.0, False)], 0.05, 8000)
    right = mod.render_frame(l, [mod.Source([0.0, -2.0, 0], [0, 0, 0], 1.0, False)], 0.05, 8000)
    assert max(map(abs, left[0])) > max(map(abs, left[1]))
    assert max(map(abs, right[1])) > max(map(abs, right[0]))
