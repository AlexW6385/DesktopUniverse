"""
    python -m pytest tests
"""
import math
import os
import sys

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import numpy as np
import pygame
import pytest

import engine
import presets
from config import Field, Flow, from_dict, problems, to_dict

pygame.init()


def one(pos, f, src=(0.0, 0.0), vel=None, src_vel=(0.0, 0.0), scale=1.0):
    pos = np.atleast_2d(np.asarray(pos, float))
    vel = np.zeros_like(pos) if vel is None else np.atleast_2d(np.asarray(vel, float))
    return engine.pull(pos, vel, np.asarray(src, float), np.asarray(src_vel, float), f, scale)


# ------------------------------------------------------------------ forces

def test_classic_power_law():
    for power in (1, 2, 0.5):
        f = Field("classic", 10, power=power)
        a = one([[100, 0]], f)[0]
        assert a[0] < 0 and abs(a[1]) < 1e-12                   # toward the source
        assert math.isclose(np.hypot(*a), 10 / 100 ** power, rel_tol=1e-9)


def test_inner_gain_turns_pull_into_push():
    f = Field("classic", 10, inner_radius=50, inner_gain=-1, outer_gain=1)
    assert one([[30, 0]], f)[0][0] > 0                         # pushed away inside
    assert one([[80, 0]], f)[0][0] < 0                         # pulled outside


def test_vortex_is_sideways():
    a = one([[100, 0]], Field("vortex", 10))[0]
    assert abs(a[0]) < 1e-12 and abs(a[1]) > 0


def test_ring_rests_on_its_radius():
    f = Field("ring", 1, radius=100)
    assert np.allclose(one([[100, 0]], f), 0)
    assert one([[150, 0]], f)[0][0] < 0 and one([[50, 0]], f)[0][0] > 0


def test_drag_matches_and_wake_pushes():
    drag = one([[10, 0]], Field("drag", 50), vel=[[0, 0]], src_vel=(4, 0))[0]
    assert math.isclose(drag[0], 2.0)
    wake_still = one([[10, 0]], Field("wake", 50), vel=[[3, 0]], src_vel=(0, 0))[0]
    assert np.allclose(wake_still, 0)                          # a still cursor does nothing


def test_distance_window():
    f = Field("classic", 10, min_dist=20, max_dist=60)
    assert np.allclose(one([[10, 0]], f), 0) and np.allclose(one([[80, 0]], f), 0)
    assert not np.allclose(one([[40, 0]], f), 0)


def test_pulse_swings_sign():
    f = Field("classic", 10, pulse=2, period=4)
    values = [engine.pulse_factor(f, t) for t in np.linspace(0, 4, 50)]
    assert min(values) < 0 < max(values)


def test_flow_is_divergence_free():
    cfg = Flow(True, 1.0, 300, 0.2)
    x, y, h = 437.0, 211.0, 0.5
    fx = lambda p: engine.flow(np.array([p]), cfg, 3.0)[0]
    div = ((fx((x + h, y))[0] - fx((x - h, y))[0]) + (fx((x, y + h))[1] - fx((x, y - h))[1])) / (2 * h)
    assert abs(div) < 2e-4          # float32 field, analytic divergence is exactly 0


def test_pressure_pushes_from_crowded_to_empty():
    rng = np.random.default_rng(0)
    pos = np.vstack([rng.normal([200, 200], 10, (2000, 2)), rng.random((200, 2)) * 800])
    acc = engine.neighbourhood(pos, np.zeros_like(pos), (800, 800), 16, 1.0, 0.0)
    edge = (np.hypot(*(pos - [200, 200]).T) > 15) & (np.hypot(*(pos - [200, 200]).T) < 40)
    outward = np.einsum("ij,ij->i", acc[edge], pos[edge] - [200, 200])
    assert (outward > 0).mean() > 0.8


def test_alignment_pulls_toward_the_local_mean():
    pos = np.tile([[50.0, 50.0]], (10, 1))
    vel = np.zeros((10, 2)); vel[0] = [10, 0]
    acc = engine.neighbourhood(pos, vel, (100, 100), 16, 0.0, 1.0)
    assert acc[0][0] < 0 and acc[1][0] > 0


# ------------------------------------------------------------------ presets

@pytest.mark.parametrize("key", presets.BUILTIN_KEYS)
def test_builtin_runs_and_round_trips(key):
    p = presets.get(key)
    assert from_dict(to_dict(p)) == p
    assert problems(p) == []
    for layer in p.layers:
        layer.count = min(layer.count, 2000)
    screen = pygame.Surface((800, 500))
    u = engine.Universe(p, screen, engine.Mouse(lambda: (400, 250, False)), seed=1)
    for _ in range(40):
        u.step()
        u.draw()
    for s in u.swarms:
        assert np.isfinite(s.pos).all() and np.isfinite(s.vel).all()


def test_slots_are_builtins():
    assert len(presets.SLOTS) == 9 and all(k in presets.BUILTIN_KEYS for k in presets.SLOTS)
    assert len(set(presets.BUILTIN_KEYS)) == len(presets.BUILTIN_KEYS)


def test_live_reconfigure_keeps_bodies():
    p = presets.get("galaxy")
    p.layers[1].count = 500
    u = engine.Universe(p, pygame.Surface((400, 300)), engine.Mouse(lambda: (0, 0, False)), seed=0)
    u.step()
    before = u.swarm("stars").pos.copy()
    p2 = from_dict(to_dict(p))
    p2.layers[1].count = 600
    u.reconfigure(p2)
    assert len(u.swarm("stars")) == 600 and np.allclose(u.swarm("stars").pos[:500], before)


# ------------------------------------------------------------------ library

def test_library_crud(tmp_path):
    lib = presets.Library(tmp_path)
    key = lib.save("My Galaxy", presets.get("galaxy"))
    assert key == "My_Galaxy" and key in lib.custom and lib.get(key).title == "My Galaxy"
    p = lib.get(key); p.friction = 0.01
    assert lib.save(key, p) == key and presets.Library(tmp_path).get(key).friction == 0.01   # update
    new = lib.rename(key, "Café Cosmos")                            # names need not be ASCII
    assert new == "Café_Cosmos" and key not in lib.custom and (tmp_path / "Café_Cosmos.json").exists()
    assert lib.delete(new) and not (tmp_path / "Café_Cosmos.json").exists()
    with pytest.raises(ValueError):
        lib.save("galaxy", presets.get("galaxy"))                 # built-in names are reserved
    lib.remember("saturn")
    assert presets.Library(tmp_path).last() == "saturn"
