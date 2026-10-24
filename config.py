"""
The data model. A universe is plain data, so it can be edited live from the
panel, saved as JSON and loaded back. SCHEMA at the bottom describes every
field (label, range, when it applies) and the panel builds itself from it.

A Preset is a stack of Layers, top to bottom. Each layer is a swarm of
identical bodies and can only be pulled by the layer directly above it:

    mouse            the very top
      sun            pulled by the mouse (or moving on its own path)
        planet       pulled by the sun
          dust       pulled by the planets

Pull sources: "above" (every body of the layer above; the mouse for the top
layer), plus two global ones that reach any level: "mouse" and "center".
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass, field, fields

ABOVE, MOUSE, CENTER = "above", "mouse", "center"
SOURCES = (ABOVE, MOUSE, CENTER)
MAX_PAIRS = 600_000     # a pull costing more body pairs per frame is skipped (~25 ms)


@dataclass
class Field:
    """One force. d = source - body, r = |d|.

    classic  strength / r^power toward the source (power 1: gentle and long
             range, 2: Newton, negative: a spring that grows with distance);
             inner_gain applies inside inner_radius (negative = push away)
    vortex   the same strength, but sideways: bodies swirl around the source
    ring     a spring toward a circle of `radius` around the source
             (for rings, pulse makes the radius breathe instead of the strength)
    drag     pulls the body's velocity toward the source's velocity
             (strength = % per frame): bodies get carried along with the source
    wake     pushes bodies the way the source is moving (strength = % of its
             velocity per frame); a still source does nothing, a moving cursor
             stirs everything it passes
    startle  pushes bodies away from the source, in proportion to how fast the
             source is moving: a still cursor is ignored, a sudden move scares
             everything off

    absorb > 0: bodies that come closer than this to the source are swallowed
    and reborn by their layer's birth rule.

    pulse > 0 makes the strength breathe: strength * (1 + pulse * sin(2 pi t / period + phase));
    with pulse > 1 it swings between pulling and pushing.
    """
    law: str = "classic"
    strength: float = 20.0
    power: float = 1.0
    min_dist: float = 0.0
    max_dist: float = math.inf
    inner_radius: float = 0.0
    inner_gain: float = 1.0
    outer_gain: float = 1.0
    radius: float = 150.0
    pulse: float = 0.0
    period: float = 8.0
    phase: float = 0.0
    absorb: float = 0.0


@dataclass
class Pull:
    source: str = ABOVE
    field: Field = field(default_factory=Field)
    enabled: bool = True


@dataclass
class Layer:
    name: str = "dust"
    count: int = 10000
    pulls: list[Pull] = field(default_factory=list)

    # how it moves
    motion: str = "physics"        # physics | wander | path | attractor | flow3d | grow | slime
                                   # | pendulum | teleport | fixed
    friction: float | None = None  # None = the preset's friction
    damping: float = 0.0           # share of velocity lost every frame; 1 = no momentum at all,
                                   # bodies simply follow the force field (field lines)
    jitter: float = 0.0            # random kick per frame (temperature)
    max_speed: float = 0.0         # 0 = unlimited
    min_speed: float = 0.0         # bodies never slow below this (birds keep flying)
    variety: float = 0.0           # each body feels the pulls 1 +- variety times as strongly,
                                   # so they settle at different places instead of one ring
    wind: float = 1.0              # share of the preset's wind / gravity
    flow: float = 1.0              # share of the preset's flow field
    home: float = 0.0              # spring back to the birth position
    pressure: float = 0.0          # push from crowded to empty (negative: clump together)
    align: float = 0.0             # match the average velocity of neighbours (flocking)
    cell: int = 16                 # neighbourhood size for pressure / align, px

    # path: bodies trace a curve on their own (with home > 0 the curve is elastic: bodies spring
    # toward their point on it, so the cursor can push them off and they snap back)
    path_shape: str = "lissajous"  # lissajous | rose | spiro (a Spirograph hypotrochoid) | sunflower
    path_around: str = CENTER      # center | mouse
    path_center: list[float] = field(default_factory=lambda: [0.5, 0.5])  # when around center
    path_size: list[float] = field(default_factory=lambda: [0.5, 0.4])  # of half the screen
                                   # (rose / spiro: radius, of half the shorter side)
    path_freq: list[float] = field(default_factory=lambda: [1.0, 2.0])  # lissajous
    path_k: float = 0.375          # rose: petal ratio; spiro: small / big circle
    path_d: float = 0.8            # spiro: pen distance / small circle
    path_loops: float = 1.0        # how many turns the bodies spread over (spiro / rose close
                                   # after several turns)
    path_speed: float = 0.1        # turns per second
    path_spread: float = 1.0       # how far apart the bodies sit along the curve (1 = evenly)
    path_spin: float = 0.0         # the whole figure rotates, turns per second
    path_angle: float = 137.508    # sunflower: angle between one seed and the next (the golden angle)
    path_sweep: float = 0.0        # sunflower: the angle swings +- this many degrees ...
    path_sweep_period: float = 120.0  # ... once every this many seconds

    # attractor: bodies hop along the preset's strange attractor
    map_blend: float = 1.0         # 1 = jump onto the map each frame, smaller = drift toward it

    teleport_every: int = 60       # teleport: every N frames all bodies jump somewhere new

    # grow: diffusion-limited aggregation; walkers wander until they touch the crystal
    grow_seed: str = "center"      # center | bottom
    grow_fold: int = 6             # grow one wedge of a 2*fold-fold snowflake (use symmetry
                                   # = fold and mirror for the full flake); 0 = no folding
    grow_walkers: int = 120        # how many walk at once (more = faster growth)
    grow_speed: int = 6            # walking steps per frame
    grow_noise: int = 1            # a site freezes only after this many touches: cleaner, needle-like
                                   # arms along the grid axis (noise-reduced DLA)
    grow_hold: float = 10.0        # seconds to admire the finished crystal before it regrows
    grow_melt: float = 0.0         # a moving cursor melts the crystal within this radius
    grow_walker_light: float = 0.2 # brightness of the walkers

    # slime: agents smell a scent map ahead of them, turn toward the strongest smell and lay
    # more scent where they go (Physarum slime mould): they weave a network of veins
    slime_angle: float = 22.5      # sensor angle, degrees
    slime_dist: float = 9.0        # sensor distance, px
    slime_turn: float = 45.0       # turn per frame toward the scent, degrees
    slime_speed: float = 1.0       # px per frame
    slime_deposit: float = 1.0     # scent laid per agent per frame
    slime_decay: float = 0.1       # share of the scent that evaporates each frame
    slime_blur: float = 1.0        # diffusion: 0 = none, 1 = a full 3 x 3 blur every frame
    slime_cell: int = 2            # scent map resolution, px
    slime_mouse: float = 0.0       # scent added at the cursor each frame (food); hold to invert = poison
    slime_mouse_radius: float = 24.0
    slime_show: float = 0.0        # also paint the scent map itself as a glow (0 = only the agents)

    # pendulum: every body is the tip of its own double pendulum, all hung from one pivot
    pend_pivot: list[float] = field(default_factory=lambda: [0.5, 0.42])
    pend_size: float = 0.42        # both rods together, of the shorter screen side
    pend_angle: float = 120.0      # where they are let go, degrees from hanging straight down
    pend_spread: float = 0.001     # the starting angles differ by this much across the layer, degrees
    pend_ratio: float = 1.0        # second rod / first rod
    pend_mass: float = 1.0         # second bob / first bob
    pend_gravity: float = 9.8
    pend_speed: float = 1.0        # time scale
    pend_arms: int = 1             # draw the rods of this many of them
    pend_click: bool = True        # a click lets every pendulum go again from the cursor

    # text: bodies spring toward the pixels of a line of text (use home > 0)
    text: str = "{time}"           # "|" separates pages that take turns, "\n" breaks a line;
                                   # {time} {seconds} {date} {weekday} are filled in live
    text_period: float = 8.0       # seconds per page
    text_click: bool = False       # a click turns the page (text layers with the same period turn
                                   # together, so a poem and its title stay matched)
    text_size: float = 0.3         # of the screen height
    text_pos: list[float] = field(default_factory=lambda: [0.5, 0.5])
    text_font: str = ""            # system font names, comma separated; empty = the default

    click_burst: int = 0           # a mouse click rebirths this many bodies at the cursor

    # life
    life: int = 0                  # frames; 0 = forever
    life_jitter: float = 0.3       # +- share of life, so deaths don't all line up
    fade: bool = True              # fade in after birth and out before death

    # birth
    spawn: str = "random"          # random | center | mouse | mouse_ring | edges | grid | circle
                                   # | above | above_ring | text
    spawn_radius: float = 200.0    # circle / mouse_ring / above_ring
    spawn_spread: float = 2.0      # how much the ring radius varies, px (large = a fuzzy disk)
    velocity: str = "random"       # zero | random | orbit | outward | sphere | ring | inherit
    start_speed: float = 2.0

    # looks
    look: str = "pixel"            # pixel | dot | none
    size: int = 1                  # pixel square size
    dot: int = 8                   # dot diameter
    dot_soft: float = 0.0          # 0 = a crisp disk, 1 = a soft glow (bokeh)
    color_mode: str = "palette"    # palette | fixed | speed | direction | age | rainbow | birth | index
                                   # (birth: the palette hue at the moment of birth, so every
                                   # burst / click / growth ring gets its own colour;
                                   # index: a gradient across the layer, body 0 to body N)
    color: list[int] = field(default_factory=lambda: [120, 160, 255])
    color2: list[int] = field(default_factory=lambda: [255, 230, 190])
    speed_ref: float = 6.0         # speed that gets the full second colour
    brightness: float = 1.0
    twinkle: float = 0.0           # each body flickers: 0 = steady, 1 = dark between short flashes
    twinkle_period: float = 3.0    # seconds per flicker (each body a little different)
    links: float = 0.0             # draw a line between bodies closer than this (constellations;
                                   # small layers only)
    link_brightness: float = 0.6
    link_mouse: bool = False       # the cursor joins the constellation too
    link_reveal: float = 0.0       # > 0: lines only show within this distance of the cursor (a torch)
    link_max: int = 0              # each body links to at most this many nearest neighbours (0 = all)


@dataclass
class Palette:
    """The shared drifting colour: a hue that slowly turns."""
    hue: float = 210.0             # degrees
    hue_speed: float = 3.0         # degrees per second
    saturation: float = 0.55
    value: float = 0.95
    spread: float = 90.0           # rainbow mode: hue range across a layer


@dataclass
class Flow:
    """A slowly changing, swirling wind over the whole screen."""
    enabled: bool = False
    strength: float = 0.05
    scale: float = 300.0           # swirl size, px
    speed: float = 0.2             # how fast the pattern changes
    mode: str = "force"            # force: a wind that accelerates | carry: moves bodies directly
                                   # along the streamlines (no clumping, like ink in water)


@dataclass
class Attractor:
    """A strange attractor for layers whose motion is 'attractor'."""
    kind: str = "clifford"         # clifford | dejong
    a: float = -1.7
    b: float = 1.8
    c: float = -1.9
    d: float = -0.4
    scale: float = 0.9             # of the screen's shorter side
    morph: float = 0.15            # how far a..d wander over time
    morph_speed: float = 0.02      # cycles per second
    around: str = CENTER           # center | mouse


@dataclass
class Flow3D:
    """A 3D strange attractor (a continuous flow) for layers whose motion is 'flow3d'.
    It is drawn in perspective and turns around; the cursor can turn it too."""
    kind: str = "lorenz"           # lorenz | aizawa | thomas | halvorsen | rossler
    speed: float = 1.0             # time scale
    scale: float = 0.85            # of the screen's shorter side
    spin: float = 0.01             # turns per second around the vertical axis
    tilt: float = 12.0             # degrees: look at it from a little above
    mouse_turn: float = 0.5        # moving the cursor across the screen turns it this many times
    perspective: float = 0.4
    depth_light: float = 0.5       # the far side is this much dimmer
    start: str = "spread"          # spread: all along the attractor | blob: one tight blob that tears apart
    blob: float = 0.0005           # blob size, of the attractor's size (also: rebirth scatter)


@dataclass
class Preset:
    title: str = "Untitled"
    description: str = ""
    layers: list[Layer] = field(default_factory=list)

    friction: float = 0.0005
    friction_shape: str = "round"  # round: by total speed | axis: x and y separately
    wind: list[float] = field(default_factory=lambda: [0.0, 0.0])
    wind_mode: str = "fixed"       # fixed | tilt: gravity points from the screen centre toward the
                                   # cursor (strength = length of wind), like tilting a tray
    edge: str = "wrap"             # wrap | bounce | respawn
    bounce: float = 0.8
    click_invert: bool = True      # hold the left mouse button to flip the mouse's forces

    brightness: float = 1.0
    breathe_period: float = 0.0    # seconds; 0 = off. Fades to dark and back once a period
    breathe_depth: float = 0.9
    breathe_forces: bool = True    # forces fade with the light (everything drifts in the dark)

    background: list[int] = field(default_factory=lambda: [0, 0, 0])
    trail: float = 0.0             # 0 = clear each frame, 1 = keep forever, between = fade
    blend: str = "replace"         # replace | add (overlaps glow)
    glow: float = 0.5              # add: brightness of each hit
    symmetry: int = 1              # kaleidoscope: copies around the centre
    mirror: bool = False

    palette: Palette = field(default_factory=Palette)
    flow: Flow = field(default_factory=Flow)
    attractor: Attractor = field(default_factory=Attractor)
    flow3d: Flow3D = field(default_factory=Flow3D)


# ---------------------------------------------------------------- JSON

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


def layer_template() -> dict:
    """Every layer field with its default, for the panel's "add layer" buttons."""
    return _clean(asdict(Layer()))


def _build(cls, d):
    d = d if isinstance(d, dict) else {}
    names = {f.name for f in fields(cls)}
    return cls(**{k: v for k, v in d.items() if k in names})


def from_dict(d: dict) -> Preset:
    layers = []
    for ld in d.get("layers", []):
        pulls = []
        for pd in ld.get("pulls", []):
            fd = dict(pd.get("field", {}))
            if fd.get("max_dist") is None:
                fd["max_dist"] = math.inf
            src = pd.get("source", ABOVE)
            pulls.append(Pull(src if src in SOURCES else ABOVE, _build(Field, fd),
                              bool(pd.get("enabled", True))))
        layer = _build(Layer, {**ld, "pulls": pulls})
        layer.count = max(0, int(layer.count))
        layers.append(layer)
    return _build(Preset, {**d, "layers": layers,
                           "palette": _build(Palette, d.get("palette")),
                           "flow": _build(Flow, d.get("flow")),
                           "attractor": _build(Attractor, d.get("attractor")),
                           "flow3d": _build(Flow3D, d.get("flow3d"))})


def problems(p: Preset) -> list[str]:
    out = []
    for i, layer in enumerate(p.layers):
        if i and any(pl.enabled and pl.source == ABOVE for pl in layer.pulls):
            above = p.layers[i - 1]
            if above.count * layer.count > MAX_PAIRS:
                out.append(f"{layer.name} ← {above.name}: {above.count} × {layer.count} pairs is too many, "
                           f"so this force is skipped (keep the layer above small)")
    names = [l.name for l in p.layers]
    for n in set(names):
        if names.count(n) > 1:
            out.append(f"Two layers are called {n}")
    return out


# ---------------------------------------------------------------- schema
# kind: num | int | log | sel | bool | color | vec2 | text
# when: {"field": [values]} shows the control only when another field of the
#       same object has one of those values; "preset.x" looks at the preset.

def F(key, label, kind, **kw):
    return {"key": key, "label": label, "kind": kind, **kw}


SCHEMA = {
    "preset": [
        ("About", [
            F("title", "Name", "text"),
            F("description", "Description", "text"),
        ]),
        ("Motion", [
            F("friction", "Friction", "log", min=1e-6, max=0.05),
            F("friction_shape", "Friction shape", "sel", options=[["round", "By total speed (round)"],
                                                                 ["axis", "Per axis (squarish)"]]),
            F("wind", "Gravity / wind", "vec2", min=-0.3, max=0.3, step=0.005, labels=["→", "↓"]),
            F("wind_mode", "Gravity points", "sel", options=[["fixed", "One way"], ["tilt", "Toward the mouse (tilt)"]],
              hint="Tilt: gravity points from the screen centre toward the mouse, as strong as the wind above, "
                   "like tilting a tray"),
            F("edge", "Edges", "sel", options=[["wrap", "Wrap around"], ["bounce", "Bounce"], ["respawn", "Respawn when out"]]),
            F("bounce", "Bounciness", "num", min=0, max=1, step=0.01, when={"edge": ["bounce"]}),
            F("click_invert", "Hold mouse to invert", "bool", hint="While the left button is held, all of the "
                                                                    "mouse's forces flip"),
        ]),
        ("Light", [
            F("brightness", "Brightness", "num", min=0, max=1.5, step=0.01),
            F("breathe_period", "Breathing period s", "num", min=0, max=600, step=1,
              hint="0 = off; once a period everything dims and comes back"),
            F("breathe_depth", "Breathing depth", "num", min=0, max=1, step=0.01, when={"breathe_period": "nonzero"}),
            F("breathe_forces", "Forces fade too", "bool", when={"breathe_period": "nonzero"},
              hint="In the dark the forces fade too, so everything drifts apart and gathers again as it brightens"),
        ]),
        ("Canvas", [
            F("background", "Background", "color"),
            F("trail", "Trails", "num", min=0, max=1, step=0.01, hint="0 = clear every frame, 1 = keep forever, "
                                                                     "in between = fade"),
            F("blend", "Blend", "sel", options=[["replace", "Paint over"], ["add", "Add up (glow)"]]),
            F("glow", "Glow", "num", min=0.02, max=1, step=0.01, when={"blend": ["add"]}),
            F("symmetry", "Kaleidoscope copies", "int", min=1, max=12, step=1, hint="1 = off"),
            F("mirror", "Mirror", "bool"),
        ]),
        ("Palette (for layers coloured by palette / direction / rainbow)", [
            F("palette.hue", "Hue", "num", min=0, max=360, step=1),
            F("palette.hue_speed", "Hue drift °/s", "num", min=-60, max=60, step=0.5, symmetric=True),
            F("palette.saturation", "Saturation", "num", min=0, max=1, step=0.01),
            F("palette.value", "Value", "num", min=0, max=1, step=0.01),
            F("palette.spread", "Rainbow spread °", "num", min=0, max=360, step=1),
        ]),
        ("Flow field (a slow, swirling wind over the whole screen)", [
            F("flow.enabled", "On", "bool"),
            F("flow.strength", "Strength", "num", min=0, max=0.5, step=0.005, when={"flow.enabled": [True]}),
            F("flow.scale", "Swirl size px", "num", min=40, max=1500, step=10, when={"flow.enabled": [True]}),
            F("flow.speed", "Change speed", "num", min=0, max=2, step=0.01, when={"flow.enabled": [True]}),
            F("flow.mode", "Acts as", "sel", options=[["force", "Wind (accelerates)"], ["carry", "Current (carries along)"]],
              when={"flow.enabled": [True]}),
        ]),
        ("Strange attractor (for layers that move by strange attractor)", [
            F("attractor.kind", "Kind", "sel", options=[["clifford", "Clifford"], ["dejong", "de Jong"]]),
            F("attractor.a", "a", "num", min=-3, max=3, step=0.01, symmetric=True),
            F("attractor.b", "b", "num", min=-3, max=3, step=0.01, symmetric=True),
            F("attractor.c", "c", "num", min=-3, max=3, step=0.01, symmetric=True),
            F("attractor.d", "d", "num", min=-3, max=3, step=0.01, symmetric=True),
            F("attractor.scale", "Size", "num", min=0.1, max=2, step=0.01),
            F("attractor.morph", "Morph amount", "num", min=0, max=1, step=0.01),
            F("attractor.morph_speed", "Morph speed", "num", min=0, max=0.3, step=0.001),
            F("attractor.around", "Centre", "sel", options=[["center", "Screen centre"], ["mouse", "Mouse"]]),
        ]),
        ("3D attractor (for layers that move by 3D attractor)", [
            F("flow3d.kind", "Kind", "sel", options=[["lorenz", "Lorenz (butterfly)"], ["aizawa", "Aizawa (apple core)"],
                                                  ["thomas", "Thomas (three lobes)"], ["halvorsen", "Halvorsen (three arms)"],
                                                  ["rossler", "Rössler (a folded band)"]]),
            F("flow3d.speed", "Time speed", "num", min=0.05, max=4, step=0.05),
            F("flow3d.scale", "Size", "num", min=0.2, max=2, step=0.01),
            F("flow3d.spin", "Spin turns/s", "num", min=-0.1, max=0.1, step=0.001, symmetric=True),
            F("flow3d.tilt", "Seen from above °", "num", min=-90, max=90, step=1, symmetric=True),
            F("flow3d.mouse_turn", "Mouse turns it", "num", min=0, max=2, step=0.05,
              hint="Moving the cursor from one side of the screen to the other turns it this many times"),
            F("flow3d.perspective", "Perspective", "num", min=0, max=1, step=0.01),
            F("flow3d.depth_light", "Far side dimmer", "num", min=0, max=1, step=0.01),
            F("flow3d.start", "Starts", "sel", options=[["spread", "Spread over the whole attractor"],
                                                      ["blob", "Squeezed into one blob (watch chaos tear it apart)"]]),
            F("flow3d.blob", "Blob size", "log", min=1e-7, max=0.1, hint="Also the scatter when bodies are reborn"),
        ]),
    ],
    "layer": [
        ("", [
            F("name", "Name", "text"),
            F("count", "Count", "log", min=1, max=200000, int=True),
        ]),
        ("Motion", [
            F("motion", "Moves by", "sel", options=[
                ["physics", "Forces"], ["wander", "Random walk + forces"], ["path", "Following a path"],
                ["attractor", "Strange attractor"], ["flow3d", "3D attractor"], ["grow", "Crystal growth (DLA)"],
                ["slime", "Slime mould (scent)"], ["pendulum", "Double pendulum"], ["teleport", "Teleporting"],
                ["fixed", "Fixed"]]),
            F("damping", "Damping", "num", min=0, max=1, step=0.01,
              hint="Share of the velocity lost every frame; 1 = no momentum, bodies follow the force exactly "
                   "(draws field lines)"),
            F("path_shape", "Path shape", "sel", options=[["lissajous", "Lissajous curve"], ["rose", "Rose"],
                                                         ["spiro", "Spirograph"], ["sunflower", "Sunflower (golden angle)"]],
              when={"motion": ["path"]}, hint="With a home spring above 0 the path turns elastic: the mouse pushes "
                                              "bodies off it and they snap back"),
            F("path_around", "Path centre", "sel", options=[["center", "A fixed point"], ["mouse", "Mouse"]],
              when={"motion": ["path"]}),
            F("path_center", "Fixed point", "vec2", min=0, max=1, step=0.01, labels=["x", "y"],
              when={"motion": ["path"], "path_around": ["center"]}),
            F("path_size", "Path size", "vec2", min=0, max=1.2, step=0.01, labels=["w", "h"], when={"motion": ["path"]},
              hint="Rose / spirograph only use the first number: the radius, of half the shorter side"),
            F("path_freq", "Path frequency", "vec2", min=0, max=7, step=0.25, labels=["x", "y"],
              when={"motion": ["path"], "path_shape": ["lissajous"]}),
            F("path_k", "Ratio k", "num", min=0.02, max=4, step=0.005, when={"motion": ["path"], "path_shape": ["rose", "spiro"]},
              hint="Rose: the petal ratio; spirograph: small circle / big circle"),
            F("path_d", "Pen distance", "num", min=0, max=2, step=0.01, when={"motion": ["path"], "path_shape": ["spiro"]}),
            F("path_loops", "Turns to spread over", "num", min=0.1, max=20, step=0.1,
              when={"motion": ["path"], "path_shape": ["lissajous", "rose", "spiro"]},
              hint="Spirographs and roses often take several turns to close"),
            F("path_speed", "Path speed turns/s", "num", min=-0.5, max=0.5, step=0.001, symmetric=True,
              when={"motion": ["path"]},
              hint="Sunflower: how fast the seeds flow outward (share of the flower per second)"),
            F("path_spread", "Spacing", "num", min=0, max=1, step=0.01,
              when={"motion": ["path"], "path_shape": ["lissajous", "rose", "spiro"]},
              hint="1 = spread evenly along the whole curve"),
            F("path_angle", "Divergence angle °", "num", min=0, max=360, step=0.001,
              when={"motion": ["path"], "path_shape": ["sunflower"]},
              hint="137.508 = the golden angle: the seeds line up in Fibonacci spirals; a hair off and they turn "
                   "into spokes"),
            F("path_sweep", "Angle swing ±°", "num", min=0, max=5, step=0.001,
              when={"motion": ["path"], "path_shape": ["sunflower"]}),
            F("path_sweep_period", "Swing period s", "num", min=5, max=1200, step=1,
              when={"motion": ["path"], "path_shape": ["sunflower"], "path_sweep": "nonzero"}),
            F("path_spin", "Spin turns/s", "num", min=-0.1, max=0.1, step=0.001, symmetric=True, when={"motion": ["path"]}),
            F("map_blend", "Stick to the attractor", "num", min=0, max=1, step=0.01, when={"motion": ["attractor"]}),
            F("grow_seed", "Seed", "sel", options=[["center", "Screen centre (snowflake)"], ["bottom", "Bottom edge (coral)"]],
              when={"motion": ["grow"]}),
            F("grow_fold", "Symmetry fold", "int", min=0, max=12, step=1, when={"motion": ["grow"]},
              hint="Grows one wedge only; with the same number of kaleidoscope copies plus mirror on the canvas you "
                   "get a perfect snowflake; 0 = no folding"),
            F("grow_walkers", "Walkers at once", "int", min=1, max=3000, step=1, when={"motion": ["grow"]}),
            F("grow_speed", "Steps per frame", "int", min=1, max=40, step=1, when={"motion": ["grow"]}),
            F("grow_noise", "Touches to freeze", "int", min=1, max=20, step=1, when={"motion": ["grow"]},
              hint="Noise reduction: above 1 the arms grow cleaner and more needle-like, along the main axes"),
            F("grow_hold", "Hold when grown s", "num", min=0, max=120, step=1, when={"motion": ["grow"]}),
            F("grow_melt", "Mouse melt radius", "num", min=0, max=300, step=1, when={"motion": ["grow"]}),
            F("grow_walker_light", "Walker brightness", "num", min=0, max=1, step=0.01, when={"motion": ["grow"]}),
            F("slime_angle", "Sensor angle °", "num", min=1, max=90, step=0.5, when={"motion": ["slime"]}),
            F("slime_dist", "Sensor distance px", "num", min=1, max=60, step=0.5, when={"motion": ["slime"]}),
            F("slime_turn", "Turn °/frame", "num", min=1, max=90, step=0.5, when={"motion": ["slime"]}),
            F("slime_speed", "Crawl speed", "num", min=0.1, max=6, step=0.05, when={"motion": ["slime"]}),
            F("slime_deposit", "Scent laid", "num", min=0.01, max=10, step=0.01, when={"motion": ["slime"]}),
            F("slime_decay", "Evaporation", "num", min=0.001, max=0.5, step=0.001, when={"motion": ["slime"]}),
            F("slime_blur", "Diffusion", "num", min=0, max=1, step=0.01, when={"motion": ["slime"]}),
            F("slime_cell", "Scent grid px", "int", min=1, max=8, step=1, when={"motion": ["slime"]}),
            F("slime_mouse", "Food at the mouse", "num", min=-50, max=50, step=0.5, symmetric=True,
              when={"motion": ["slime"]},
              hint="Positive = food, the mould grows toward it; negative = it keeps away. Hold the mouse to invert"),
            F("slime_mouse_radius", "Food radius px", "num", min=2, max=200, step=1,
              when={"motion": ["slime"], "slime_mouse": "nonzero"}),
            F("slime_show", "Draw the scent", "num", min=0, max=5, step=0.01, when={"motion": ["slime"]},
              hint="Paints the scent map itself as a soft glow; 0 = only the mould"),
            F("pend_pivot", "Pivot", "vec2", min=0, max=1, step=0.01, labels=["x", "y"], when={"motion": ["pendulum"]}),
            F("pend_size", "Length (of short side)", "num", min=0.05, max=1, step=0.01, when={"motion": ["pendulum"]}),
            F("pend_angle", "Let go at °", "num", min=-180, max=180, step=1, symmetric=True, when={"motion": ["pendulum"]}),
            F("pend_spread", "Starting spread °", "log", min=1e-9, max=30, when={"motion": ["pendulum"]},
              hint="The pendulums start only this far apart: the smaller, the longer they swing as one before chaos "
                   "splits them"),
            F("pend_ratio", "Lower rod / upper rod", "num", min=0.1, max=3, step=0.01, when={"motion": ["pendulum"]}),
            F("pend_mass", "Lower / upper bob mass", "num", min=0.05, max=10, step=0.05, when={"motion": ["pendulum"]}),
            F("pend_gravity", "Gravity", "num", min=0.5, max=40, step=0.1, when={"motion": ["pendulum"]}),
            F("pend_speed", "Time speed", "num", min=0.05, max=4, step=0.05, when={"motion": ["pendulum"]}),
            F("pend_arms", "Rods drawn", "int", min=0, max=50, step=1, when={"motion": ["pendulum"]}),
            F("pend_click", "Click lets go at cursor", "bool", when={"motion": ["pendulum"]}),
            F("teleport_every", "Teleport every N frames", "int", min=1, max=600, step=1, when={"motion": ["teleport"]}),
        ]),
        ("Drag and noise", [
            F("friction", "Friction", "log", min=1e-6, max=0.05, nullable_label="Use the preset's"),
            F("jitter", "Jitter (temperature)", "num", min=0, max=1, step=0.005),
            F("max_speed", "Speed limit", "num", min=0, max=30, step=0.1, hint="0 = none"),
            F("min_speed", "Minimum speed", "num", min=0, max=10, step=0.05,
              hint="Never slower than this (the birds keep flying)"),
            F("variety", "Variety", "num", min=0, max=1, step=0.01,
              hint="Each body feels the forces 1 ± variety times as strongly, so they don't all crowd onto one ring"),
            F("wind", "Feels gravity / wind", "num", min=0, max=3, step=0.05),
            F("flow", "Feels the flow field", "num", min=0, max=3, step=0.05),
        ]),
        ("Neighbours", [
            F("home", "Home spring", "num", min=0, max=0.1, step=0.001,
              hint="Pulls bodies back to where they were born: grid birth + home spring = an elastic fabric"),
            F("pressure", "Pressure", "num", min=-3, max=3, step=0.05, symmetric=True,
              hint="Positive = pushes from crowded to empty (fluids, piles), negative = clumping"),
            F("align", "Alignment", "num", min=0, max=0.3, step=0.005, hint="Follow the neighbours' average velocity "
                                                                            "(flocking)"),
            F("cell", "Neighbourhood px", "int", min=4, max=120, step=1),
        ]),
        ("Life", [
            F("life", "Lifetime frames", "int", min=0, max=1200, step=1,
              hint="0 = forever; when a body dies it is reborn by the birth rule"),
            F("life_jitter", "Lifetime jitter", "num", min=0, max=1, step=0.01, when={"life": "nonzero"}),
            F("fade", "Fade in and out", "bool", when={"life": "nonzero"}),
        ]),
        ("Birth", [
            F("spawn", "Where", "sel", options=[
                ["random", "Anywhere"], ["center", "Screen centre"], ["mouse", "At the mouse"],
                ["mouse_ring", "A ring around the mouse"], ["edges", "Screen edges"], ["grid", "A grid"],
                ["circle", "A ring around the centre"], ["above", "On the layer above (emitters)"],
                ["above_ring", "A ring around the layer above (moons)"], ["text", "Text (with a home spring)"]]),
            F("spawn_radius", "Ring radius", "num", min=0, max=1000, step=1,
              when={"spawn": ["circle", "above_ring", "mouse_ring"]}),
            F("spawn_spread", "Ring thickness", "num", min=0, max=500, step=1,
              when={"spawn": ["circle", "above_ring", "mouse_ring"]},
              hint="How much the radius varies; large values give a fuzzy disk"),
            F("text", "Text", "text", when={"spawn": ["text"]},
              hint="Pages separated by | take turns, \\n breaks a line; {time} {seconds} {date} {weekday} fill in "
                   "live"),
            F("text_period", "Seconds per page", "num", min=1, max=120, step=0.5, when={"spawn": ["text"]}),
            F("text_click", "A click turns the page", "bool", when={"spawn": ["text"]},
              hint="Text layers with the same seconds per page turn together, so a poem keeps its title"),
            F("text_size", "Text size (of height)", "num", min=0.03, max=0.8, step=0.01,
              when={"spawn": ["text"]}),
            F("text_pos", "Text position", "vec2", min=0, max=1, step=0.01, labels=["x", "y"], when={"spawn": ["text"]}),
            F("text_font", "Font", "text", when={"spawn": ["text"]},
              hint="System font names, comma separated; empty = the default"),
            F("click_burst", "Click burst", "int", min=0, max=20000, step=10,
              hint="A click rebirths this many bodies at the cursor (with an outward start velocity: an explosion)"),
            F("velocity", "Start velocity", "sel", options=[
                ["zero", "At rest"], ["random", "Random direction"], ["orbit", "Orbiting (sideways)"],
                ["outward", "Bursting outward"], ["sphere", "A bursting shell (fireworks)"], ["ring", "A bursting ring (tilted)"],
                ["inherit", "Inherited from the layer above"]]),
            F("start_speed", "Start speed", "num", min=0, max=20, step=0.1),
        ]),
        ("Looks", [
            F("look", "Drawn as", "sel", options=[["pixel", "Pixels"], ["dot", "Dots"], ["none", "Not drawn"]]),
            F("size", "Pixel size", "int", min=1, max=4, step=1, when={"look": ["pixel"]}),
            F("dot", "Dot diameter", "int", min=2, max=120, step=1, when={"look": ["dot"]}),
            F("dot_soft", "Softness", "num", min=0, max=1, step=0.01, when={"look": ["dot"]},
              hint="0 = a crisp disk, 1 = a soft glow (bokeh)"),
            F("color_mode", "Colour", "sel", options=[
                ["palette", "Palette (drifting)"], ["fixed", "Fixed"], ["speed", "By speed"],
                ["direction", "By direction (colour wheel)"], ["age", "By age"], ["rainbow", "Rainbow spread"],
                ["birth", "The colour at birth"], ["index", "Gradient across the layer"]]),
            F("color", "Colour 1", "color", when={"color_mode": ["fixed", "speed", "age"]}),
            F("color2", "Colour 2", "color", when={"color_mode": ["speed", "age"]}),
            F("speed_ref", "Full-colour speed", "num", min=0.2, max=20, step=0.1, when={"color_mode": ["speed"]}),
            F("brightness", "Brightness", "num", min=0, max=2, step=0.01),
            F("twinkle", "Twinkle", "num", min=0, max=1, step=0.01,
              hint="Each body flickers to its own rhythm; 1 = dark with the occasional flash (fireflies)"),
            F("twinkle_period", "Twinkle period s", "num", min=0.1, max=20, step=0.1, when={"twinkle": "nonzero"}),
            F("links", "Link distance", "num", min=0, max=400, step=1,
              hint="Draws a line between bodies closer than this (constellations); only for layers of a few hundred"),
            F("link_brightness", "Link brightness", "num", min=0, max=1.5, step=0.01, when={"links": "nonzero"}),
            F("link_mouse", "Link the mouse too", "bool", when={"links": "nonzero"}),
            F("link_max", "Links per body", "int", min=0, max=12, step=1, when={"links": "nonzero"},
              hint="Only the nearest few, like a real constellation; 0 = everything in range"),
            F("link_reveal", "Only near the mouse px", "num", min=0, max=1200, step=10, when={"links": "nonzero"},
              hint="Above 0 the lines only show up this close to the cursor, like a torch on the night sky; "
                   "0 = everywhere"),
        ]),
    ],
    "field": [
        F("law", "Law", "sel", options=[["classic", "Gravity"], ["vortex", "Vortex"], ["ring", "Orbit ring"],
                                         ["drag", "Drag (match speed)"], ["wake", "Wake (push along)"],
                                         ["startle", "Startle (pushed off by the source's speed)"]]),
        F("strength", "Strength", "num", min=-200, max=200, symmetric=True),
        F("power", "Falloff power", "num", min=-1, max=3, step=0.05, when={"law": ["classic", "vortex"]},
          hint="1 = gentle and long range, 2 = Newton, negative = a spring"),
        F("radius", "Ring radius px", "num", min=0, max=900, step=1, when={"law": ["ring"]}),
        F("min_dist", "Min distance", "num", min=0, max=500, step=1),
        F("max_dist", "Max distance", "num", min=0, max=3000, step=1, nullable=True),
        F("inner_radius", "Inner radius", "num", min=0, max=1000, step=1, when={"law": ["classic", "vortex"]}),
        F("inner_gain", "Inner gain", "num", min=-3, max=3, step=0.05, symmetric=True, when={"law": ["classic", "vortex"]},
          hint="Negative = the inner zone pushes away"),
        F("outer_gain", "Outer gain", "num", min=-3, max=3, step=0.05, symmetric=True, when={"law": ["classic", "vortex"]}),
        F("pulse", "Pulse", "num", min=0, max=3, step=0.01,
          hint="Above 1 it swings between pulling and pushing; for an orbit ring the radius breathes instead"),
        F("period", "Pulse period s", "num", min=0.2, max=60, step=0.1, when={"pulse": "nonzero"}),
        F("phase", "Pulse phase", "num", min=0, max=1, step=0.01, when={"pulse": "nonzero"}),
        F("absorb", "Swallow radius", "num", min=0, max=200, step=1,
          hint="Bodies that come this close are swallowed and reborn by their birth rule"),
    ],
}

LAW_HINTS = {
    "classic": "strength / r^power, toward the source. With a negative inner gain, coming close pushes bodies away",
    "vortex": "A sideways force: bodies swirl around the source. Add gravity and you have a galaxy",
    "ring": "A spring toward a circle of fixed radius around the source. Add a vortex and you have Saturn's rings",
    "drag": "Pulls each body's velocity toward the source's, so the source carries them along; a still source "
            "acts as a brake (strength = % per frame)",
    "wake": "Pushes bodies the way the source moves: a passing mouse stirs everything it crosses, a still one "
            "does nothing (strength = % per frame)",
    "startle": "Pushes bodies away by how fast the source moves: a still mouse is ignored, a sudden move scares "
               "everything off",
}
