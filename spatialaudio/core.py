# -*- coding: utf-8 -*-
"""spatialaudio 核心：距离衰减、多普勒、双耳声像、遮挡与平滑恢复。

仅使用 Python 标准库。坐标约定：听者 forward 为朝向，+z 为上，
左方向 = up × forward。声源信号为基频 440 Hz 加三次谐波的合成音，
便于测试频移与低通效果。
"""

from __future__ import annotations

import itertools
import math

__all__ = ["Listener", "Source", "mix", "render_frame"]

SPEED_OF_SOUND = 343.0      # 声速 (m/s)
REF_DISTANCE = 1.0          # 参考距离 (m)：此处增益为 1
MAX_DISTANCE = 200.0        # 远场截断阈值 (m)：之外增益为 0
BASE_FREQ = 440.0           # 声源基频 (Hz)
MAX_ITD = 0.0006            # 最大耳间时间差 (s)
OCCLUSION_GAIN = 0.4        # 完全遮挡时的增益系数
OCCLUSION_CUTOFF = 700.0    # 完全遮挡时的低通截止频率 (Hz)
OPEN_CUTOFF = 18000.0       # 无遮挡时的低通截止频率 (Hz)
OCC_RATE = 2.0              # 遮挡因子每秒最大变化量（恢复坡度上界）

_FUND = 1.1                 # 基波幅度
_HARM = 0.2                 # 三次谐波幅度（远小于基波，不改变过零结构）
_TWO_PI = 2.0 * math.pi
_LOG_OPEN = math.log(OPEN_CUTOFF)
_LOG_OCC = math.log(OCCLUSION_CUTOFF)


def _unit(v):
    n = math.sqrt(v[0] * v[0] + v[1] * v[1] + v[2] * v[2])
    if n == 0.0:
        return (0.0, 0.0, 0.0)
    return (v[0] / n, v[1] / n, v[2] / n)


class Listener:
    """Listener"""

    def __init__(self, pos, forward):
        """听者"""
        self.pos = tuple(float(x) for x in pos)
        self.forward = _unit(tuple(float(x) for x in forward))
        f = self.forward
        left = (-f[1], f[0], 0.0)  # up(+z) × forward
        if left == (0.0, 0.0, 0.0):
            left = (0.0, 1.0, 0.0)
        self.left = _unit(left)


class Source:
    """Source"""

    def __init__(self, pos, vel, gain, occluded):
        """声源"""
        self.pos = tuple(float(x) for x in pos)
        self.vel = tuple(float(x) for x in vel)
        self.gain = float(gain)
        self.occluded = bool(occluded)
        self.freq = BASE_FREQ
        self._phase = 0.0
        self._occ = 1.0 if self.occluded else 0.0
        self._lp = 0.0


def _signal(src, ux, uy, uz, n, rate):
    """生成单源单声道信号，含多普勒频移（相位跨帧连续）。"""
    vr = src.vel[0] * ux + src.vel[1] * uy + src.vel[2] * uz  # 正对方向为远离
    lim = 0.9 * SPEED_OF_SOUND
    if vr > lim:
        vr = lim
    elif vr < -lim:
        vr = -lim
    f = src.freq * SPEED_OF_SOUND / (SPEED_OF_SOUND + vr)
    step = _TWO_PI * f / rate
    ph = src._phase
    src._phase = (ph + n * step) % _TWO_PI
    sin = math.sin
    phases = itertools.islice(
        itertools.accumulate(itertools.repeat(step, n), initial=ph), n)
    return [_FUND * sin(a) + _HARM * sin(3.0 * a) for a in phases]


def _cutoff(occ):
    return math.exp(_LOG_OPEN + (_LOG_OCC - _LOG_OPEN) * occ)


def _apply_occlusion(src, sig, occ0, occ1, n, rate):
    """遮挡处理：低通 + 增益包络。返回 (信号, 标量增益)。"""
    if occ0 <= 1e-4 and occ1 <= 1e-4:
        src._lp = 0.0
        return sig, 1.0
    y = src._lp
    out = []
    ap = out.append
    if occ0 == occ1:
        # 稳态：恒定截止的一阶低通，增益用标量
        alpha = 1.0 - math.exp(-_TWO_PI * _cutoff(occ0) / rate)
        for x in sig:
            y += alpha * (x - y)
            ap(y)
        src._lp = y
        return out, 1.0 - (1.0 - OCCLUSION_GAIN) * occ0
    # 过渡帧：遮挡因子逐样本插值，增益与低通同步渐变，避免突变
    inv_n = 1.0 / n
    k = 1.0 - OCCLUSION_GAIN
    for i, x in enumerate(sig):
        occ = occ0 + (occ1 - occ0) * (i * inv_n)
        alpha = 1.0 - math.exp(-_TWO_PI * _cutoff(occ) / rate)
        y += alpha * (x - y)
        ap(y * (1.0 - k * occ))
    src._lp = y
    return out, 1.0


def _accum(out, sig, g, delay, n):
    """把 sig 按增益 g 与小数样本延迟 delay 累加进 out（可为 None）。"""
    if g == 0.0:
        return out
    k = int(delay)
    frac = delay - k
    if k == 0 and frac == 0.0:
        if out is None:
            return [g * x for x in sig]
        return [a + g * x for a, x in zip(out, sig)]
    if out is None:
        out = [0.0] * n
    m = n - k - 1
    if m <= 0:
        return out
    g1 = g * (1.0 - frac)
    g2 = g * frac
    # out[i] += g1*sig[i-k] + g2*sig[i-k-1]（线性插值小数延迟）
    seg = [g1 * a + g2 * b for a, b in
           zip(itertools.islice(sig, 1, m + 1), itertools.islice(sig, 0, m))]
    out[k] += g1 * sig[0]
    tail = [a + b for a, b in zip(itertools.islice(out, k + 1, None), seg)]
    return out[:k + 1] + tail


def render_frame(listener, sources, duration, rate):
    """渲染一帧，返回 (左, 右)"""
    n = int(round(duration * rate))
    if n <= 0:
        return [], []
    left = None
    right = None
    for src in sources:
        dx = src.pos[0] - listener.pos[0]
        dy = src.pos[1] - listener.pos[1]
        dz = src.pos[2] - listener.pos[2]
        dist = math.sqrt(dx * dx + dy * dy + dz * dz)
        if dist > MAX_DISTANCE or src.gain == 0.0:
            continue
        if dist > 0.0:
            ux, uy, uz = dx / dist, dy / dist, dz / dist
        else:
            ux, uy, uz = 0.0, 0.0, 0.0

        # 遮挡因子：逐帧逼近目标，变化率有上界（恢复不突变）
        target = 1.0 if src.occluded else 0.0
        step = OCC_RATE * duration
        occ0 = src._occ
        if target > occ0:
            occ1 = min(target, occ0 + step)
        else:
            occ1 = max(target, occ0 - step)
        src._occ = occ1

        sig = _signal(src, ux, uy, uz, n, rate)
        sig, occ_gain = _apply_occlusion(src, sig, occ0, occ1, n, rate)

        # 距离衰减：参考距离处为 1，之后随距离单调递减
        att = REF_DISTANCE / dist if dist > REF_DISTANCE else 1.0
        g = src.gain * att * occ_gain
        if g == 0.0:
            continue

        # 双耳声像：方位角 -> 等功率声像 + 耳间时间差
        fwd = ux * listener.forward[0] + uy * listener.forward[1] + uz * listener.forward[2]
        lft = ux * listener.left[0] + uy * listener.left[1] + uz * listener.left[2]
        pan = math.sin(math.atan2(lft, fwd))  # >0 偏左；背面不反相
        phi = (1.0 - pan) * (math.pi / 4.0)
        gl = g * math.cos(phi)
        gr = g * math.sin(phi)
        itd = pan * MAX_ITD * rate  # 样本数；>0 时右耳延迟
        if itd >= 0.0:
            dl, dr = 0.0, itd
        else:
            dl, dr = -itd, 0.0
        left = _accum(left, sig, gl, dl, n)
        right = _accum(right, sig, gr, dr, n)

    if left is None:
        left = [0.0] * n
    if right is None:
        right = [0.0] * n
    # 多源叠加防削波：超限时整体按比例压低，保持声道间平衡
    peak = max(max(map(abs, left)), max(map(abs, right)))
    if peak > 1.0:
        s = 1.0 / peak
        left = [v * s for v in left]
        right = [v * s for v in right]
    return left, right


def mix(channels):
    """混音并防削波：各通道相加，峰值超 1 时等比例压低所有样本。"""
    out = []
    for c in channels:
        out = [a + b for a, b in itertools.zip_longest(out, c, fillvalue=0.0)]
    if not out:
        return []
    peak = max(map(abs, out))
    if peak > 1.0:
        s = 1.0 / peak
        out = [x * s for x in out]
    return out
