"""
Parameter templates for DesktopUniverse.

Every preset below is a 1:1 transcription of one of the original scripts.
The numbers are the hand-tuned values from those scripts; do not "clean them up".

    big_bang          <- DesktopUniverse.py
    less_than_nothing <- less than nothing.py
    waves             <- waves.py
    raindrops         <- raindrops.py
    yuanqi_xingkong   <- OOPUniverse.py, MODE = "缘起性空"
    suibo_zhuliu      <- OOPUniverse.py, MODE = "随波逐流"
    shennv_sanhua     <- OOPUniverse.py, MODE = "神女散花"

To make a new look: copy a preset, change numbers, give it a new key.
"""

from dataclasses import dataclass, field, replace
from math import inf


@dataclass(frozen=True)
class Field:
    """How one kind of attractor (the mouse, or each star) pulls on a body.

    law = "classic"  (the four standalone scripts)
        a = g * gain * d / r^2          -> magnitude g/r, pointing at the attractor
        skipped when r < min_dist       (old `stop_dist`)
        gain = inner_gain if r < inner_radius else outer_gain
        (old `gravity_dist`: e.g. waves.py repels inside 200px and ignores the rest)

    law = "oop"      (OOPUniverse.py)
        a_x = g / r^2 * (dx / r) * |dx|, same for y
        only active when min_dist <= round(r) < max_dist   (old GRAVITY_RANGE)

    In both laws g is multiplied by the current "dark" value every frame.
    """
    gravity: float
    law: str = "classic"
    min_dist: float = 0
    max_dist: float = inf
    inner_radius: float = 0
    inner_gain: float = 1.0
    outer_gain: float = 1.0


@dataclass(frozen=True)
class Palette:
    """Sand colour drift. Each frame one random RGB channel moves by a random
    step in [step_min, step_max]; its direction flips once it leaves (low, high).
    Drawn colour = offset + channel * dark."""
    init_min: int
    init_max: int
    step_min: int
    step_max: int
    low: int
    high: int
    offset: int = 0
    random_start_dir: bool = False   # OOP version starts each channel in a random direction


def classic_palette(color_var_max, offset):
    # bounds exactly as in the old scripts: > 255-cvm-1 turns down, < cvm+1 turns up
    return Palette(50, 200, 1, color_var_max, color_var_max + 1, 255 - color_var_max - 1, offset)


def oop_palette(color_var):
    return Palette(150, 200, color_var, color_var, 50, 200, 0, random_start_dir=True)


@dataclass(frozen=True)
class Preset:
    title: str
    sand_num: int
    star_num: int

    mouse: Field | None          # pull of the mouse on sand (and on stars if star_motion == "orbit")
    star: Field | None           # pull of every star on sand

    friction: float              # v *= 1 - friction * v^2, per axis
    dark: float | str            # a fixed number, or "cycle" (fades to black every 120 s)
    dark_scales_friction: bool   # classic scripts scaled friction by dark too; OOP did not

    trails: bool                 # True = never clear the screen (old KARMA_ON / commented-out fill)
    palette: Palette

    sand_spawn: str = "random"           # "center" | "random"
    sand_velocity: str = "big_bang"      # "big_bang" | "jitter" (randint(-2, 2))
    big_bang_speed_range: int = 10

    star_motion: str = "orbit"           # "orbit" (follows mouse) | "random_walk" | "teleport"
    star_velocity: str = "drift"         # "drift" (old +-0.5 start) | "zero"
    teleport_every: int = 1              # raindrops: old renew_speed + 1 frames
    draw_stars: bool = True

    edge: str = "wrap"                   # "wrap" (clean torus) | "legacy" (old abs(x - width) rule)


# ---------------------------------------------------------------- the presets

PRESETS: dict[str, Preset] = {

    "big_bang": Preset(
        title="Big Bang",
        sand_num=5000, star_num=3,
        mouse=Field(gravity=40, min_dist=1),
        star=Field(gravity=40, min_dist=1),
        friction=0.0001, dark="cycle", dark_scales_friction=True,
        trails=True,
        palette=classic_palette(color_var_max=1, offset=0),
        sand_spawn="center", sand_velocity="big_bang", big_bang_speed_range=10,
        star_motion="orbit", star_velocity="drift",
    ),

    "less_than_nothing": Preset(
        title="Less Than Nothing",
        sand_num=10000, star_num=0,
        mouse=Field(gravity=1000, min_dist=30, inner_radius=500, inner_gain=-2, outer_gain=2),
        star=Field(gravity=1000, min_dist=30, inner_radius=500, inner_gain=-2, outer_gain=2),
        friction=0.0001, dark=0.5, dark_scales_friction=True,
        trails=False,
        palette=classic_palette(color_var_max=3, offset=50),
        sand_spawn="random", sand_velocity="big_bang",
        star_motion="random_walk", star_velocity="drift",
    ),

    "waves": Preset(
        title="Waves",
        sand_num=15000, star_num=0,
        mouse=Field(gravity=100, min_dist=30, inner_radius=200, inner_gain=-1, outer_gain=0),
        star=Field(gravity=100, min_dist=30, inner_radius=200, inner_gain=-1, outer_gain=0),
        friction=0.0051, dark=0.6, dark_scales_friction=True,
        trails=False,
        palette=classic_palette(color_var_max=3, offset=30),
        sand_spawn="random", sand_velocity="big_bang",
        star_motion="random_walk", star_velocity="drift",
    ),

    "raindrops": Preset(
        title="Raindrops",
        sand_num=30000, star_num=1,
        mouse=None,
        star=Field(gravity=100, min_dist=3, inner_radius=50, inner_gain=-1, outer_gain=0),
        friction=0.0111, dark=0.4, dark_scales_friction=True,
        trails=False,
        palette=classic_palette(color_var_max=3, offset=50),
        sand_spawn="random", sand_velocity="big_bang",
        star_motion="teleport", star_velocity="zero", teleport_every=1,  # renew_speed = 0
        draw_stars=False,
    ),

    "yuanqi_xingkong": Preset(
        title="缘起性空",
        sand_num=5000, star_num=3,
        mouse=Field(gravity=40, law="oop", min_dist=10, max_dist=9999),
        star=Field(gravity=50, law="oop", min_dist=2, max_dist=9999),
        friction=0.0001, dark="cycle", dark_scales_friction=False,
        trails=True,
        palette=oop_palette(color_var=3),
        sand_spawn="random", sand_velocity="jitter",
        star_motion="orbit", star_velocity="zero",
    ),

    "suibo_zhuliu": Preset(
        title="随波逐流",
        sand_num=15000, star_num=0,
        mouse=Field(gravity=-100, law="oop", min_dist=30, max_dist=200),
        star=None,
        friction=0.003, dark="cycle", dark_scales_friction=False,
        trails=False,
        palette=oop_palette(color_var=3),
        sand_spawn="random", sand_velocity="jitter",
        star_motion="orbit", star_velocity="zero",
    ),

    "shennv_sanhua": Preset(
        title="神女散花",
        sand_num=15000, star_num=0,
        mouse=Field(gravity=-100, law="oop", min_dist=30, max_dist=200),
        star=None,
        friction=0.003, dark="cycle", dark_scales_friction=False,
        trails=True,
        palette=oop_palette(color_var=3),
        sand_spawn="random", sand_velocity="jitter",
        star_motion="orbit", star_velocity="zero",
    ),
}

DEFAULT = "suibo_zhuliu"   # OOPUniverse.py's default MODE


def variant(base: str, **changes) -> Preset:
    """Make a new preset from an existing one, e.g. variant("waves", sand_num=40000)."""
    return replace(PRESETS[base], **changes)
