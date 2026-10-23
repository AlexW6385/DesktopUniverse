"""
The data model of a universe. Everything here is plain data: it is edited
live from the panel, saved to JSON and loaded back.

A Preset is a stack of Layers, top to bottom. Every layer is a swarm of
identical bodies, and it can only be pulled by the layer directly above it:

    mouse            (the top: the "Absolute" of OOPUniverse.py)
      star1          pulled by the mouse
        star2        pulled by star1
          sand       pulled by star2

Each Pull names its source:
    "above"   every body of the layer above (the mouse, for the top layer)
    "mouse"   the cursor, which reaches every level (like the old Absolute,
              which pulled both stars and sand); switch it off per layer
    "center"  the middle of the screen, a fixed anchor
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass, field, fields

ABOVE = "above"
MOUSE = "mouse"
CENTER = "center"
SOURCES = (ABOVE, MOUSE, CENTER)
MAX_PAIRS = 600_000   # a pull costing more body pairs per frame than this is skipped (~25 ms)

LAWS = ("classic", "oop", "vortex", "ring")
MOTIONS = ("physics", "random_walk", "teleport", "fixed")
LOOKS = ("pixel", "dot", "none")
COLOR_MODES = ("palette", "fixed", "speed")
SPAWNS = ("random", "center", "mouse", "edges")
VELOCITIES = ("big_bang", "jitter", "drift", "zero")
EDGES = ("wrap", "bounce", "respawn", "legacy")
FRICTION_SHAPES = ("axis", "round")


@dataclass
class Field:
    """A force law. d = source - body, r = |d|, g = gravity * dark.

    classic  a = g * gain * d / r^(power+1)   strength g/r^power, toward the source
             (power 1 = the original scripts, 2 = Newton)
             gain = inner_gain inside inner_radius, outer_gain outside (negative = push)
    oop      a_x = g / r^2 * (dx/r) * |dx|    the OOPUniverse.py formula
    vortex   like classic but sideways: bodies swirl around the source
    ring     a = g/1000 * (r - radius) * d / r   a spring toward a circle

    Every law is only active while min_dist <= r < max_dist
    (oop compares round(r), exactly like the old GRAVITY_RANGE).
    """
    law: str = "classic"
    gravity: float = 40.0
    min_dist: float = 0.0
    max_dist: float = math.inf
    inner_radius: float = 0.0
    inner_gain: float = 1.0
    outer_gain: float = 1.0
    power: float = 1.0             # classic / vortex falloff
    radius: float = 150.0          # ring only


@dataclass
class Pull:
    source: str                    # "above" | "mouse" | "center"
    field: Field
    enabled: bool = True


@dataclass
class Layer:
    name: str
    count: int
    pulls: list[Pull] = field(default_factory=list)

    # motion
    motion: str = "physics"        # physics | random_walk | teleport | fixed
    friction: float | None = None  # None = the preset's friction
    jitter: float = 0.0            # random kick per frame (temperature)
    max_speed: float = 0.0         # 0 = no limit
    flow: float = 1.0              # how much the flow field moves this layer
    wind: float = 1.0              # how much the global wind / gravity moves it
    teleport_every: int = 1        # teleport: one body jumps every N frames

    # birth (on start, when the count grows, and on respawn)
    spawn: str = "random"          # random | center | mouse | edges
    velocity: str = "big_bang"     # big_bang | jitter (+-2) | drift (old star start) | zero
    big_bang_speed_range: int = 10

    # looks
    look: str = "pixel"            # pixel | dot | none
    size: list[int] = field(default_factory=lambda: [1, 1])   # pixel w, h
    dot: int = 10                  # dot diameter; 10 + no colour = the original star
    color_mode: str = "palette"    # palette (drifting) | fixed | speed (slow -> fast)
    color: list[int] | None = None # fixed colour, or the slow colour
    color2: list[int] = field(default_factory=lambda: [255, 120, 60])   # fast colour
    speed_ref: float = 6.0         # speed that gets the full fast colour


@dataclass
class Palette:
    """Colour drift. Each frame one random RGB channel moves by a random step
    in [step_min, step_max]; its direction flips once it leaves (low, high).
    Drawn colour = offset + channel * dark."""
    init_min: int = 50
    init_max: int = 200
    step_min: int = 1
    step_max: int = 3
    low: int = 4
    high: int = 251
    offset: int = 0
    random_start_dir: bool = False


@dataclass
class Flow:
    """A slowly changing swirling wind over the whole screen
    (divergence-free, so it stirs without piling bodies up)."""
    enabled: bool = False
    strength: float = 0.05
    scale: float = 300.0           # swirl size, px
    speed: float = 0.2             # how fast the pattern changes


@dataclass
class Preset:
    title: str
    layers: list[Layer]
    friction: float = 0.0001
    friction_shape: str = "axis"   # axis: x and y slow separately (the original rule;
                                   # orbits come out slightly square) | round: by total speed
    dark: float | str = "cycle"    # a number, or "cycle" (fade to black every 120 s)
    dark_scales_friction: bool = True
    trail: float = 0.0             # 0 = clear every frame, 1 = never clear, between = fade
    palette: Palette = field(default_factory=Palette)
    flow: Flow = field(default_factory=Flow)
    wind: list[float] = field(default_factory=lambda: [0.0, 0.0])   # constant pull, px/frame^2
    click_invert: bool = False     # hold the left button to flip the mouse's pull
    edge: str = "wrap"             # wrap | bounce | respawn | legacy (old abs rule)
    bounce: float = 0.8            # speed kept when bouncing off a wall

    def layer(self, name: str) -> Layer:
        return next(l for l in self.layers if l.name == name)


# ---------------------------------------------------------------- JSON round trip

def _clean(v):
    if isinstance(v, float) and math.isinf(v):
        return None
    if isinstance(v, dict):
        return {k: _clean(x) for k, x in v.items()}
    if isinstance(v, list):
        return [_clean(x) for x in v]
    return v


def to_dict(p: Preset) -> dict:
    return _clean(asdict(p))


def _build(cls, d: dict):
    names = {f.name for f in fields(cls)}
    return cls(**{k: v for k, v in d.items() if k in names})


def from_dict(d: dict) -> Preset:
    d = dict(d)
    if "trail" not in d and "trails" in d:          # files from the first rewrite
        d["trail"] = 1.0 if d["trails"] else 0.0
    layers = []
    for ld in d.get("layers", []):
        pulls = []
        for pd in ld.get("pulls", []):
            fd = dict(pd.get("field", {}))
            if fd.get("max_dist") is None:
                fd["max_dist"] = math.inf
            src = pd.get("source", ABOVE)
            if src not in SOURCES:          # older files named the layer: it is the one above
                src = ABOVE
            pulls.append(Pull(source=src, field=_build(Field, fd),
                              enabled=pd.get("enabled", True)))
        ld = dict(ld)
        if "color_mode" not in ld:
            ld["color_mode"] = "fixed" if ld.get("color") else "palette"
        layer = _build(Layer, {**ld, "pulls": pulls})
        layer.count = max(0, int(layer.count))
        layers.append(layer)
    p = _build(Preset, {**d, "layers": layers,
                        "palette": _build(Palette, d.get("palette", {})),
                        "flow": _build(Flow, d.get("flow", {}))})
    if isinstance(p.dark, str) and p.dark != "cycle":
        p.dark = float(p.dark)
    return p


def problems(p: Preset) -> list[str]:
    """Pulls the engine will skip because they would freeze the frame."""
    out = []
    for i, layer in enumerate(p.layers):
        if i == 0 or not any(pl.enabled and pl.source == ABOVE for pl in layer.pulls):
            continue
        above = p.layers[i - 1]
        if above.count * layer.count > MAX_PAIRS:
            out.append(f"{layer.name} <- {above.name}: {above.count} x {layer.count} pairs per "
                       f"frame is too many, that pull is skipped (keep upper layers small)")
    return out
