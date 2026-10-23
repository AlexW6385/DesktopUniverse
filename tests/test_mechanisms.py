"""
The newer mechanisms: text, crystals, slime, 3D flows, pendulums, paths, links, colours, trails.

    python -m pytest tests
"""
import math
import os
import sys
from datetime import datetime

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import numpy as np
import pygame

import engine
from config import ABOVE, CENTER, MOUSE, Field, Flow3D, Layer, Preset, Pull

pygame.init()


class Cursor:
    """A scriptable mouse: set .x .y .down between steps."""

    def __init__(self, x=0.0, y=0.0):
        self.x, self.y, self.down = x, y, False

    def __call__(self):
        return self.x, self.y, self.down


def world(layers, size=(400, 300), cursor=None, seed=0, **preset):
    cursor = cursor or Cursor(size[0] / 2, size[1] / 2)
    p = Preset("t", layers=layers, **preset)
    return engine.Universe(p, pygame.Surface(size), engine.Mouse(cursor), seed=seed), cursor


def run(u, frames, draw=False):
    for _ in range(frames):
        u.step()
        if draw:
            u.draw()


# ------------------------------------------------------------------ forces

def test_startle_ignores_a_still_cursor_and_flees_a_fast_one():
    f = Field("startle", 1.0, max_dist=200)
    pos, vel = np.array([[50.0, 0.0]]), np.zeros((1, 2))
    still = engine.pull(pos, vel, np.zeros(2), np.zeros(2), f, 1.0)
    fast = engine.pull(pos, vel, np.zeros(2), np.array([0.0, 10.0]), f, 1.0)
    slow = engine.pull(pos, vel, np.zeros(2), np.array([0.0, 2.0]), f, 1.0)
    assert np.allclose(still, 0)
    assert fast[0, 0] > 0 and abs(fast[0, 1]) < 1e-12               # straight away from the cursor
    assert math.isclose(fast[0, 0] / slow[0, 0], 5.0)               # in proportion to its speed


def test_absorb_swallows_and_rebirths():
    layer = Layer("dust", 200, [Pull(CENTER, Field("classic", 0.0, absorb=40))], spawn="edges",
                  velocity="zero")
    u, _ = world([layer])
    s = u.swarms[0]
    s.pos[:50] = u.center[0] + np.random.default_rng(0).normal(0, 5, (50, 2))   # inside the mouth
    u.step()
    d = np.hypot(*(s.pos - u.center[0]).T)
    assert (d > 40).all()                                            # all reborn on the edges


def test_damping_one_means_no_momentum():
    layer = Layer("probe", 50, [Pull(CENTER, Field("classic", 5.0, min_dist=1))], damping=1.0,
                  min_speed=2.0, max_speed=2.0, velocity="random", start_speed=5)
    u, _ = world([layer], friction=0.0)
    u.step()
    s = u.swarms[0]
    to_center = u.center[0] - s.pos
    cos = np.einsum("ij,ij->i", s.vel, to_center) / (np.hypot(*s.vel.T) * np.hypot(*to_center.T))
    assert np.allclose(np.hypot(*s.vel.T), 2.0) and (cos > 0.999).all()   # straight down the field


def test_tilt_points_gravity_at_the_cursor():
    layer = Layer("sand", 10, [], velocity="zero")
    u, cur = world([layer], wind=[0.0, 0.2], wind_mode="tilt")
    cur.x, cur.y = 390, 150                                          # far right of the centre
    u.mouse.update()
    w = u._wind()
    assert w[0] > 0.15 and abs(w[1]) < 1e-9
    cur.x, cur.y = 200, 150                                          # centred: a level tray
    u.mouse.update()
    assert np.allclose(u._wind(), 0)


# ------------------------------------------------------------------ text

def test_expand_text_cycles_and_fills_the_clock():
    now = datetime(2026, 10, 23, 9, 5, 7)                           # a Friday
    assert engine.expand_text("{time}", 0, 8, now) == "09:05"
    assert engine.expand_text("{seconds}", 0, 8, now) == "09:05:07"
    assert engine.expand_text("{date} {weekday}", 0, 8, now) == "10月23日 星期五"
    assert [engine.expand_text("a|b|c", t, 5) for t in (0, 5, 10, 15)] == ["a", "b", "c", "a"]


def test_text_bodies_settle_on_the_glyphs():
    layer = Layer("txt", 1500, [], spawn="text", text="88", text_size=0.5, home=0.03, damping=0.15,
                  velocity="zero")
    u, _ = world([layer], size=(500, 300), friction=0.0)
    run(u, 200)
    s = u.swarms[0]
    assert s.text_key == "88"
    assert np.median(np.hypot(*(s.pos - s.home).T)) < 1.0           # arrived
    assert (s.home[:, 0] > 0).all() and (s.home[:, 0] < 500).all()


def test_new_text_retargets_without_reshuffling_everyone():
    layer = Layer("txt", 800, [], spawn="text", text="1|7", text_period=1.0, home=0.03, damping=0.2,
                  velocity="zero")
    u, _ = world([layer], size=(400, 300))
    run(u, 30)
    first = u.swarms[0].home.copy()
    run(u, 40)                                                       # past one second: the next line
    assert u.swarms[0].text_key == "7" and not np.allclose(first, u.swarms[0].home)


# ------------------------------------------------------------------ crystals

def test_crystal_grows_connected_and_in_its_wedge():
    layer = Layer("ice", 600, [], motion="grow", grow_fold=6, grow_walkers=150, grow_speed=10)
    u, _ = world([layer], size=(400, 400))
    run(u, 250)
    s = u.swarms[0]
    c = s.crystal
    stuck = s.pos[c["stuck"]]
    assert c["stuck"].sum() > 50
    d = stuck - u.center[0]
    ang = np.arctan2(d[:, 1], d[:, 0])
    assert (ang >= -1e-6).all() and (ang <= math.pi / 6 + 0.05).all()   # one wedge of the flake
    # every stuck body sits next to another one (or the seed): it is one connected crystal
    seed = u.center[0]
    pts = np.vstack([stuck, seed])
    dist = np.hypot(*(pts[:, None, :] - pts[None, :, :]).transpose(2, 0, 1))
    np.fill_diagonal(dist, np.inf)
    assert (dist.min(axis=1)[:-1] <= 3 * c["g"] * math.sqrt(2)).all()


def test_noise_reduction_slows_growth():
    def grown(noise):
        layer = Layer("ice", 600, [], motion="grow", grow_fold=6, grow_walkers=150, grow_speed=10,
                      grow_noise=noise)
        u, _ = world([layer], size=(400, 400))
        run(u, 150)
        return u.swarms[0].crystal["stuck"].sum()
    assert grown(4) < grown(1)


def test_crystal_regrows_after_its_hold():
    layer = Layer("ice", 80, [], motion="grow", grow_walkers=80, grow_speed=20, grow_hold=0.2)
    u, _ = world([layer], size=(200, 200))
    run(u, 400)
    c = u.swarms[0].crystal
    assert c["done_at"] is None or u.t - c["done_at"] <= 0.2 + 1e-9


# ------------------------------------------------------------------ slime

def test_slime_crawls_at_its_speed_and_lays_scent():
    layer = Layer("mould", 3000, [], motion="slime", slime_speed=1.5, slime_cell=2, velocity="random")
    u, _ = world([layer], size=(300, 200))
    run(u, 20)
    s = u.swarms[0]
    assert np.allclose(np.hypot(*s.vel.T), 1.5)
    assert s.scent.shape == (100, 150) and s.scent.min() >= 0 and s.scent.sum() > 0
    assert ((s.pos >= 0) & (s.pos < [300, 200])).all()


def test_slime_finds_food_at_the_cursor():
    def near_cursor(food):
        layer = Layer("mould", 4000, [], motion="slime", slime_speed=2, slime_dist=12, slime_cell=2,
                      slime_mouse=food, slime_mouse_radius=20, velocity="random")
        u, _ = world([layer], size=(300, 200), cursor=Cursor(150, 100))
        run(u, 150)
        return (np.hypot(*(u.swarms[0].pos - [150, 100]).T) < 40).mean()
    assert near_cursor(60.0) > 2 * near_cursor(0.0)


# ------------------------------------------------------------------ 3D flows

def test_every_3d_flow_stays_finite_and_on_screen():
    for kind in engine.FLOWS_3D:
        layer = Layer("air", 1500, [], motion="flow3d")
        u, cur = world([layer], size=(400, 300), flow3d=Flow3D(kind))
        for i in range(60):
            cur.x = 400 * i / 60                                    # turn it around
            u.step()
        s = u.swarms[0]
        assert np.isfinite(s.p3).all(), kind
        assert ((s.pos > -50) & (s.pos < [450, 350])).mean() > 0.98, kind
        assert np.ptp(s.pos[:, 0]) > 100, kind                       # spread over the attractor


def test_blob_tears_apart():
    layer = Layer("air", 2000, [], motion="flow3d")
    u, _ = world([layer], flow3d=Flow3D("lorenz", start="blob", blob=0.001, mouse_turn=0))
    u.step()
    early = np.ptp(u.swarms[0].p3, axis=0).max()
    run(u, 900)
    assert np.ptp(u.swarms[0].p3, axis=0).max() > 100 * early         # the butterfly effect


# ------------------------------------------------------------------ pendulums

def energy(s, m2=1.0, l2=1.0, g=9.8):
    th1, w1, th2, w2 = s.T
    kinetic = 0.5 * (1 + m2) * w1 ** 2 + 0.5 * m2 * (l2 * w2) ** 2 + m2 * l2 * w1 * w2 * np.cos(th1 - th2)
    potential = -(1 + m2) * g * np.cos(th1) - m2 * g * l2 * np.cos(th2)
    return kinetic + potential


def test_pendulums_conserve_energy_and_reach():
    layer = Layer("bob", 300, [], motion="pendulum", pend_angle=120, pend_spread=1.0)
    u, _ = world([layer], size=(400, 400))
    u.step()
    e0 = energy(u.swarms[0].pend)
    run(u, 300)
    s = u.swarms[0]
    assert np.allclose(energy(s.pend), e0, rtol=0.0, atol=0.05 * np.abs(e0).max())
    piv = np.array([0.5 * 400, 0.42 * 400])
    assert (np.hypot(*(s.pos - piv).T) <= 0.42 * 400 + 1e-6).all()


def test_tiny_spread_stays_together_then_parts():
    layer = Layer("bob", 200, [], motion="pendulum", pend_angle=125, pend_spread=1e-4)
    u, _ = world([layer], size=(400, 400))
    run(u, 60)
    assert np.ptp(u.swarms[0].pos, axis=0).max() < 2                # still one pendulum
    run(u, 1500)
    assert np.ptp(u.swarms[0].pos, axis=0).max() > 50               # chaos has parted them


def test_click_lets_go_from_the_cursor():
    layer = Layer("bob", 50, [], motion="pendulum", pend_click=True)
    u, cur = world([layer], size=(400, 400))
    run(u, 30)
    cur.x, cur.y, cur.down = 380, 168, True                          # straight to the right of the pivot
    u.step()
    s = u.swarms[0]
    assert np.allclose(s.pend[:, 0], math.pi / 2, atol=0.05)


# ------------------------------------------------------------------ paths

def test_new_path_shapes_stay_inside_their_radius():
    for shape, extra in (("rose", {"path_k": 0.4, "path_loops": 5}),
                         ("spiro", {"path_k": 3 / 8, "path_d": 0.8, "path_loops": 3}),
                         ("sunflower", {"path_speed": 0.05})):
        layer = Layer("p", 2000, [], motion="path", path_shape=shape, path_size=[0.8, 0.8], **extra)
        u, _ = world([layer], size=(400, 300))
        run(u, 30)
        r = np.hypot(*(u.swarms[0].pos - u.center[0]).T)
        assert r.max() <= 0.8 * 150 + 1e-6, shape
        assert r.max() > 0.6 * 0.8 * 150, shape


def test_sunflower_uses_the_golden_angle():
    layer = Layer("seed", 1000, [], motion="path", path_shape="sunflower", path_speed=0.0)
    u, _ = world([layer])
    d = u.swarms[0].pos - u.center[0]
    a = np.degrees(np.arctan2(d[:, 1], d[:, 0]))
    step = np.mod(np.diff(a[:10]), 360)
    assert np.allclose(step, 137.508, atol=1e-6)


def test_elastic_path_can_be_pushed_and_springs_back():
    hand = Pull(MOUSE, Field("classic", 400, min_dist=1, inner_radius=60, inner_gain=-1, outer_gain=0))
    layer = Layer("curve", 1500, [hand], motion="path", path_shape="spiro", path_loops=3, home=0.08,
                  damping=0.2, path_speed=0.0)
    u, cur = world([layer], size=(400, 300), cursor=Cursor(-500, -500))
    run(u, 60)
    rest = np.hypot(*(u.swarms[0].pos - u.swarms[0].home).T).max()
    target = u.swarms[0].home[0]
    cur.x, cur.y = target
    run(u, 30)
    pushed = np.hypot(*(u.swarms[0].pos - u.swarms[0].home).T).max()
    cur.x, cur.y = -500, -500
    run(u, 120)
    back = np.hypot(*(u.swarms[0].pos - u.swarms[0].home).T).max()
    assert rest < 1 and pushed > 20 and back < 2


# ------------------------------------------------------------------ births and colours

def test_click_burst_rebirths_at_the_cursor_in_one_colour():
    layer = Layer("paint", 1000, [], click_burst=200, velocity="sphere", start_speed=5, color_mode="birth")
    u, cur = world([layer], cursor=Cursor(120, 80))
    u.step()
    cur.down = True
    u.step()
    s = u.swarms[0]
    fresh = np.hypot(*(s.pos - s.vel - [120, 80]).T) < 1e-6        # started this frame at the cursor
    assert fresh.sum() == 200
    assert np.ptp(s.birth_hue[fresh]) < 60
    speed = np.hypot(*s.vel[fresh].T)
    assert speed.max() <= 5 + 1e-9 and np.median(speed) > 3.5     # a shell: most near full speed


def test_index_colours_run_across_the_layer():
    layer = Layer("p", 100, [], color_mode="index")
    u, _ = world([layer])
    u.p.palette.spread, u.p.palette.saturation = 300, 1.0
    c = u.swarms[0].colors()
    assert c.shape == (100, 3) and not np.allclose(c[0], c[-1])


def test_links_respect_reveal_and_max_degree():
    layer = Layer("star", 300, [], links=80, link_max=2, link_reveal=100, velocity="zero")
    u, cur = world([layer], size=(400, 300), cursor=Cursor(200, 150))
    u.draw()                                                         # must not fail
    s = u.swarms[0]
    near = np.hypot(*(s.pos - [200, 150]).T) < 180
    assert near.sum() > 10


# ------------------------------------------------------------------ trails

def test_long_trails_really_fade_to_the_background():
    for bg in ([0, 0, 0], [10, 12, 30], [236, 230, 218]):
        layer = Layer("x", 1, [], velocity="zero", look="none")
        u, _ = world([layer], size=(60, 40), trail=0.995, background=bg)
        u.screen.fill((128, 200, 90) if sum(bg) < 384 else (40, 90, 160))
        for _ in range(3000):
            u.frame += 1
            u.fade()
        assert np.abs(pygame.surfarray.array3d(u.screen).astype(int) - bg).max() <= 1, bg
