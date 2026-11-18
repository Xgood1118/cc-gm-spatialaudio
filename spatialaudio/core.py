# -*- coding: utf-8 -*-
"""spatialaudio"""

from __future__ import annotations

__all__ = ["Listener", "Source", "mix", "render_frame"]


class Listener:
    """Listener"""

    def __init__(self, pos, forward):
        """听者"""
        raise NotImplementedError("Listener.__init__ 尚未实现")

class Source:
    """Source"""

    def __init__(self, pos, vel, gain, occluded):
        """声源"""
        raise NotImplementedError("Source.__init__ 尚未实现")


def render_frame(listener, sources, duration, rate):
    """渲染一帧，返回 (左, 右)"""
    raise NotImplementedError("render_frame 尚未实现")


def mix(channels):
    """混音并防削波"""
    raise NotImplementedError("mix 尚未实现")
