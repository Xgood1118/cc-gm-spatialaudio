# -*- coding: utf-8 -*-
import argparse
import json
import spatialaudio as m


def main():
    ap = argparse.ArgumentParser(description="spatialaudio")
    ap.add_argument("path")
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    d = json.load(open(a.path, encoding="utf-8"))
    l = m.Listener(d["listener"]["pos"], d["listener"]["forward"])
    ss = [m.Source(s["pos"], s["vel"], s["gain"], s["occluded"]) for s in d["sources"]]
    left, right = m.render_frame(l, ss, 0.1, 48000)
    print(json.dumps({"n": len(left)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
