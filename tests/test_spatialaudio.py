# -*- coding: utf-8 -*-
import json
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import spatialaudio as mod  # noqa: E402

DATA = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")


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
