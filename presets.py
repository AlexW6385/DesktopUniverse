"""
Presets: the built-in ones, plus whatever you save from the panel
(one JSON file each in presets_user/, created automatically).

"Classic" are 1:1 transcriptions of the original scripts; their numbers are
hand-tuned, keep them as they are (only the sand is drawn 1x1 now):

    big_bang          <- legacy/DesktopUniverse.py
    less_than_nothing <- legacy/less_than_nothing.py
    waves             <- legacy/waves.py
    raindrops         <- legacy/raindrops.py
    yuanqi_xingkong   <- legacy/OOPUniverse.py, MODE = "缘起性空"
    suibo_zhuliu      <- legacy/OOPUniverse.py, MODE = "随波逐流"
    shennv_sanhua     <- legacy/OOPUniverse.py, MODE = "神女散花"

"New" show off levels and the newer forces; they are starting points.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

from config import ABOVE, CENTER, MOUSE, Field, Flow, Layer, Palette, Preset, Pull, from_dict, to_dict

USER_DIR = Path(__file__).with_name("presets_user")
AUTOSAVE = "_autosave"
AUTOSAVE_PREFIX = "上次的实验 · "


def classic_palette(color_var_max, offset):
    # the old scripts turned a channel down above 255-cvm-1 and up below cvm+1
    return Palette(50, 200, 1, color_var_max, color_var_max + 1, 255 - color_var_max - 1, offset)


def oop_palette(color_var):
    return Palette(150, 200, color_var, color_var, 50, 200, 0, random_start_dir=True)


def star(name, count, pulls, dot=10, color=None, **kw):
    """A layer of round sprites. No colour + dot 10 = the original star."""
    return Layer(name, count, pulls, look="dot", dot=dot, color=color, color_mode="fixed", **kw)


# ================================================================== classic

def big_bang():
    f = Field("classic", 40, min_dist=1)
    return Preset(
        "Big Bang",
        layers=[
            star("star", 3, [Pull(ABOVE, f)], velocity="drift"),
            Layer("sand", 5000, [Pull(MOUSE, f), Pull(ABOVE, f)], spawn="center"),
        ],
        friction=0.0001, dark="cycle", dark_scales_friction=True, trail=1.0,
        palette=classic_palette(1, 0),
    )


def less_than_nothing():
    f = Field("classic", 1000, min_dist=30, inner_radius=500, inner_gain=-2, outer_gain=2)
    return Preset(
        "Less Than Nothing",
        layers=[
            star("star", 0, [], motion="random_walk", velocity="drift"),
            Layer("sand", 10000, [Pull(MOUSE, f), Pull(ABOVE, f)]),
        ],
        friction=0.0001, dark=0.5, dark_scales_friction=True,
        palette=classic_palette(3, 50),
    )


def waves():
    f = Field("classic", 100, min_dist=30, inner_radius=200, inner_gain=-1, outer_gain=0)
    return Preset(
        "Waves",
        layers=[
            star("star", 0, [], motion="random_walk", velocity="drift"),
            Layer("sand", 15000, [Pull(MOUSE, f), Pull(ABOVE, f)]),
        ],
        friction=0.0051, dark=0.6, dark_scales_friction=True,
        palette=classic_palette(3, 30),
    )


def raindrops():
    f = Field("classic", 100, min_dist=3, inner_radius=50, inner_gain=-1, outer_gain=0)
    return Preset(
        "Raindrops",
        layers=[
            Layer("drop", 1, [], motion="teleport", teleport_every=1,  # old renew_speed = 0
                  velocity="zero", look="none"),
            Layer("sand", 30000, [Pull(ABOVE, f)]),
        ],
        friction=0.0111, dark=0.4, dark_scales_friction=True,
        palette=classic_palette(3, 50),
    )


def yuanqi_xingkong():
    mouse = Field("oop", 40, min_dist=10, max_dist=9999)
    stars = Field("oop", 50, min_dist=2, max_dist=9999)
    return Preset(
        "缘起性空",
        layers=[
            star("star", 3, [Pull(ABOVE, mouse)], velocity="zero"),
            Layer("sand", 5000, [Pull(ABOVE, stars), Pull(MOUSE, mouse)], velocity="jitter"),
        ],
        friction=0.0001, dark="cycle", dark_scales_friction=False, trail=1.0,
        palette=oop_palette(3),
    )


def _suibo(trail, title):
    mouse = Field("oop", -100, min_dist=30, max_dist=200)
    return Preset(
        title,
        layers=[Layer("sand", 15000, [Pull(MOUSE, mouse)], velocity="jitter")],
        friction=0.003, dark="cycle", dark_scales_friction=False, trail=trail,
        palette=oop_palette(3),
    )


# ================================================================== new

def solar_system():
    """mouse -> star -> planet -> sand: every level only pulls the next one."""
    return Preset(
        "Solar System",
        layers=[
            star("star", 2, [Pull(ABOVE, Field("classic", 40, min_dist=20))],
                 velocity="drift", friction=0.0001),
            star("planet", 7, [Pull(ABOVE, Field("classic", 15, min_dist=8)),
                               Pull(ABOVE, Field("vortex", 3, min_dist=8, max_dist=400))],
                 dot=6, color=[150, 200, 255], velocity="drift", friction=0.0002),
            Layer("sand", 25000, [Pull(ABOVE, Field("classic", 12, min_dist=3, max_dist=150))]),
        ],
        friction=0.0015, friction_shape="round", dark=0.8, dark_scales_friction=False,
        palette=classic_palette(2, 40), click_invert=True,
    )


def chain():
    """Four levels: each one chases the one above, the dust trails the last."""
    return Preset(
        "Chain",
        layers=[
            star("star1", 1, [Pull(ABOVE, Field("classic", 30, min_dist=15))], velocity="drift",
                 friction=0.0002, color=[255, 220, 150]),
            star("star2", 3, [Pull(ABOVE, Field("classic", 20, min_dist=10)),
                              Pull(ABOVE, Field("vortex", 4, min_dist=10))],
                 dot=8, velocity="drift", friction=0.0002, color=[255, 170, 120]),
            star("star3", 9, [Pull(ABOVE, Field("classic", 12, min_dist=6)),
                              Pull(ABOVE, Field("vortex", 3, min_dist=6))],
                 dot=5, velocity="drift", friction=0.0002, color=[160, 200, 255]),
            Layer("sand", 25000, [Pull(ABOVE, Field("classic", 10, min_dist=3, max_dist=250))],
                  jitter=0.02, color_mode="speed", color=[90, 110, 170], color2=[255, 230, 190],
                  speed_ref=5),
        ],
        friction=0.0015, friction_shape="round", dark=0.85, dark_scales_friction=False,
        trail=0.6, palette=classic_palette(2, 50), click_invert=True,
    )


def galaxy():
    """The cursor pulls and spins at once; speed shows as colour."""
    return Preset(
        "Galaxy",
        layers=[Layer("sand", 40000, [
            Pull(ABOVE, Field("classic", 30, min_dist=8)),
            Pull(ABOVE, Field("vortex", 12, min_dist=8)),
        ], jitter=0.05, color_mode="speed", color=[70, 90, 200], color2=[255, 210, 150],
            speed_ref=5)],
        friction=0.0004, friction_shape="round", dark=0.8, dark_scales_friction=False,
        trail=0.5, click_invert=True,
    )


def saturn():
    """A spring toward a circle around the cursor, plus spin: rings."""
    return Preset(
        "Saturn",
        layers=[Layer("sand", 25000, [
            Pull(ABOVE, Field("ring", 1.0, radius=160)),
            Pull(ABOVE, Field("vortex", 6, min_dist=20)),
        ], jitter=0.08)],
        friction=0.003, friction_shape="round", dark=0.8, dark_scales_friction=False,
        palette=classic_palette(2, 70), click_invert=True,
    )


def smoke():
    """Waves' push, drifting on a slow swirling wind."""
    f = Field("classic", 100, min_dist=30, inner_radius=200, inner_gain=-1, outer_gain=0)
    return Preset(
        "Smoke",
        layers=[Layer("sand", 30000, [Pull(MOUSE, f)])],
        friction=0.0051, dark=0.8, dark_scales_friction=True,
        palette=classic_palette(3, 50),
        flow=Flow(enabled=True, strength=0.06, scale=320, speed=0.25),
        click_invert=True,
    )


def snow_globe():
    """Gravity points down and the walls are solid; a slow swirl keeps lifting
    the snow, and the cursor stirs it."""
    push = Field("classic", 200, min_dist=5, inner_radius=160, inner_gain=-1, outer_gain=0)
    return Preset(
        "Snow Globe",
        layers=[Layer("snow", 20000, [Pull(MOUSE, push)], jitter=0.03, velocity="zero",
                      color_mode="speed", color=[150, 170, 210], color2=[255, 255, 255],
                      speed_ref=4)],
        friction=0.002, friction_shape="round", dark=1.0, dark_scales_friction=False,
        wind=[0.0, 0.02], flow=Flow(enabled=True, strength=0.09, scale=420, speed=0.15),
        edge="bounce", bounce=0.5, click_invert=True,
    )


def fountain():
    """Sand is born at the cursor, falls, and is reborn when it leaves."""
    return Preset(
        "Fountain",
        layers=[Layer("sand", 20000, [], spawn="mouse", velocity="big_bang",
                      big_bang_speed_range=8, color_mode="speed",
                      color=[90, 140, 255], color2=[220, 250, 255], speed_ref=8)],
        friction=0.0002, friction_shape="round", dark=1.0, dark_scales_friction=False,
        wind=[0.0, 0.06], edge="respawn", trail=0.7,
    )


def whirlpool():
    """Anchored at the screen's centre, so it keeps turning when the mouse is
    away (good as a wallpaper); the cursor pushes a hole through it."""
    return Preset(
        "Whirlpool",
        layers=[Layer("sand", 35000, [
            Pull(CENTER, Field("classic", 25, min_dist=10)),
            Pull(CENTER, Field("vortex", 14, min_dist=10)),
            Pull(MOUSE, Field("classic", 120, min_dist=10, inner_radius=140,
                              inner_gain=-1, outer_gain=0)),
        ], jitter=0.06, color_mode="speed", color=[60, 40, 140], color2=[120, 230, 255],
            speed_ref=6)],
        friction=0.0005, friction_shape="round", dark=0.9, dark_scales_friction=False,
        trail=0.5, click_invert=True,
    )


# ================================================================== catalogue

GROUPS = {
    "经典": {
        "big_bang": big_bang,
        "less_than_nothing": less_than_nothing,
        "waves": waves,
        "raindrops": raindrops,
        "yuanqi_xingkong": yuanqi_xingkong,
        "suibo_zhuliu": lambda: _suibo(0.0, "随波逐流"),
        "shennv_sanhua": lambda: _suibo(1.0, "神女散花"),
    },
    "新玩法": {
        "solar_system": solar_system,
        "chain": chain,
        "galaxy": galaxy,
        "saturn": saturn,
        "smoke": smoke,
        "snow_globe": snow_globe,
        "fountain": fountain,
        "whirlpool": whirlpool,
    },
}
BUILTIN = {k: make for group in GROUPS.values() for k, make in group.items()}
DEFAULT = "suibo_zhuliu"   # OOPUniverse.py's default MODE


class Library:
    """Built-ins plus presets_user/*.json. A saved file may shadow a built-in;
    deleting it brings the built-in back."""

    def __init__(self):
        self.reload()

    def reload(self):
        self.items: dict[str, Preset] = {}
        self.group: dict[str, str] = {}
        for g, members in GROUPS.items():
            for k, make in members.items():
                self.items[k], self.group[k] = make(), g
        if USER_DIR.is_dir():
            for path in sorted(USER_DIR.glob("*.json")):
                try:
                    p = from_dict(json.loads(path.read_text(encoding="utf-8")))
                except Exception as e:      # a broken file must not stop the show
                    print(f"skipping {path.name}: {e}")
                    continue
                self.items[path.stem] = p
                self.group[path.stem] = "自动保存" if path.stem == AUTOSAVE else "我的"

    def __contains__(self, key):
        return key in self.items

    def __iter__(self):
        return iter(self.items)

    def get(self, key) -> Preset:
        return copy.deepcopy(self.items[key])

    def keys(self):
        order = ["经典", "新玩法", "我的", "自动保存"]
        return sorted(self.items, key=lambda k: order.index(self.group[k]))

    def listing(self):
        return [[k, self.items[k].title, self.group[k], self.is_user(k)] for k in self.keys()]

    def is_user(self, key):
        return (USER_DIR / f"{key}.json").exists()

    def save(self, key, preset: Preset):
        USER_DIR.mkdir(exist_ok=True)
        path = USER_DIR / f"{key}.json"
        path.write_text(json.dumps(to_dict(preset), ensure_ascii=False, indent=2), encoding="utf-8")
        return path

    def delete(self, key):
        path = USER_DIR / f"{key}.json"
        if path.exists():
            path.unlink()
            return True
        return False

    def autosave(self, preset: Preset):
        p = copy.deepcopy(preset)
        if not p.title.startswith(AUTOSAVE_PREFIX):
            p.title = AUTOSAVE_PREFIX + p.title
        self.save(AUTOSAVE, p)


def get(key: str) -> Preset:
    """A fresh copy of a preset (built-in or saved)."""
    return Library().get(key)
