"""
The built-in legacy presets must move particles exactly like the original
scripts. Each test runs a scalar port of the original per-particle code next
to the vectorised engine and compares positions frame by frame.

    python -m pytest tests        (or: python tests/test_legacy.py)
"""
import math
import os
import sys

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import numpy as np
import pygame

import engine
import presets

DARK = 0.7
FRAMES = 150
N = 300


# ---------------------------------------------------------- original formulas
def classic_speed_change(x, y, sx, sy, gx, gy, g, stop, inner_r=0, ig=1, og=1):
    dx, dy = gx - x, gy - y
    dist = (dx * dx + dy * dy) ** 0.5
    tmp = g * (ig if dist < inner_r else og)
    if dist < stop:
        return sx, sy
    return sx + tmp * dx / dist ** 2, sy + tmp * dy / dist ** 2


def oop_force(x, y, vx, vy, ax, ay, G, rng, dark):
    dx, dy = ax - x, ay - y
    dist = (dx ** 2 + dy ** 2) ** 0.5
    if round(dist) not in rng:
        return vx, vy
    force = dark * G / dist ** 2
    ang = math.atan2(dy, dx)
    return vx + force * math.cos(ang) * abs(dx), vy + force * math.sin(ang) * abs(dy)


def move(b, f):
    b[2] *= max(0, 1 - f * b[2] ** 2)
    b[3] *= max(0, 1 - f * b[3] ** 2)
    b[0] += b[2]
    b[1] += b[3]


# what each original script did with one star / sand body, given the cursor m
def ref_big_bang(stars, sand, m, drop):
    g, f = 40 * DARK, 0.0001 * DARK
    for s in stars:
        s[2], s[3] = classic_speed_change(*s, *m, g, 1)
        move(s, f)
    for b in sand:
        b[2], b[3] = classic_speed_change(*b, *m, g, 1)
        for s in stars:
            b[2], b[3] = classic_speed_change(*b, s[0], s[1], g, 1)
        move(b, f)


def ref_ring(gravity, stop, inner, ig, og, friction):
    def ref(stars, sand, m, drop):
        g, f = gravity * DARK, friction * DARK
        for b in sand:
            b[2], b[3] = classic_speed_change(*b, *m, g, stop, inner, ig, og)
            move(b, f)
    return ref


def ref_raindrops(stars, sand, m, drop):
    g, f = 100 * DARK, 0.0111 * DARK
    for b in sand:
        b[2], b[3] = classic_speed_change(*b, *drop, g, 3, 50, -1, 0)
        move(b, f)


def ref_yuanqi(stars, sand, m, drop):
    for s in stars:
        s[2], s[3] = oop_force(*s, *m, 40, range(10, 9999), DARK)
        move(s, 0.0001)
    for b in sand:
        for s in stars:
            b[2], b[3] = oop_force(*b, s[0], s[1], 50, range(2, 9999), DARK)
        b[2], b[3] = oop_force(*b, *m, 40, range(10, 9999), DARK)
        move(b, 0.0001)


def ref_suibo(stars, sand, m, drop):
    for b in sand:
        b[2], b[3] = oop_force(*b, *m, -100, range(30, 200), DARK)
        move(b, 0.003)


REFERENCE = {
    "big_bang": ref_big_bang,
    "less_than_nothing": ref_ring(1000, 30, 500, -2, 2, 0.0001),
    "waves": ref_ring(100, 30, 200, -1, 0, 0.0051),
    "raindrops": ref_raindrops,
    "yuanqi_xingkong": ref_yuanqi,
    "suibo_zhuliu": ref_suibo,
    "shennv_sanhua": ref_suibo,
}


# 缘起性空 is a chaotic three-body dance: floating-point noise (1e-16) doubles
# every few frames, so it is compared over a shorter run.
CHAOTIC = {"yuanqi_xingkong": 60}


def run(key):
    pygame.init()
    screen = pygame.Surface((8000, 8000))
    p = presets.get(key)
    p.dark = DARK
    p.layer("sand").count = N
    frame = [0]

    def cursor():
        f = frame[0]
        return 4000 + 300 * math.cos(f / 20), 4000 + 300 * math.sin(f / 25), False

    u = engine.Universe(p, screen, engine.Mouse(cursor), seed=1)
    for s in u.swarms:                   # keep everyone away from the edges
        s.pos = s.pos / 8000 * 1500 + 3250
    names = u.counts()
    sand_sw = u.swarm("sand")
    sand = [list(r) for r in np.hstack([sand_sw.pos, sand_sw.vel])]
    star_sw = u.swarm("star") if "star" in names else None
    stars = [list(r) for r in np.hstack([star_sw.pos, star_sw.vel])] if star_sw else []

    worst = 0.0
    for f in range(CHAOTIC.get(key, FRAMES)):
        frame[0] = f
        u.step()
        drop = tuple(u.swarm("drop").pos[0]) if "drop" in names else None
        m = cursor()[:2]
        REFERENCE[key](stars, sand, m, drop)
        worst = max(worst, np.abs(np.array(sand)[:, :2] - sand_sw.pos).max())
    return worst


def test_legacy_presets_match_original_physics():
    for key in REFERENCE:
        err = run(key)
        assert err < 1e-6, f"{key}: drifted {err} px from the original"


if __name__ == "__main__":
    for key in REFERENCE:
        print(f"{key:18s} max |dpos| over {CHAOTIC.get(key, FRAMES)} frames: {run(key):.1e}")
