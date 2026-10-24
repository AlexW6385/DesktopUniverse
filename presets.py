"""
The built-in presets (side by side; the first nine have hotkeys 1-9) and the library of your own.

Your presets live in presets_user/<key>.json, one file each, created by the
panel (or by hand: any field you leave out takes its default). The library
also keeps _autosave.json (your latest unsaved experiment) and _state.json
(which preset was showing last).
"""

from __future__ import annotations

import copy
import json
import re
from pathlib import Path

from config import ABOVE, CENTER, MOUSE, Field, Flow, Flow3D, Layer, Palette, Preset, Pull, from_dict, to_dict

USER_DIR = Path(__file__).with_name("presets_user")
AUTOSAVE = "_autosave"
STATE = "_state"
MINE, AUTOSAVED = "Mine", "Autosaved"          # your own presets are listed under these


def push(strength=250, radius=150):
    """The cursor shoves things out of a circle around it."""
    return Field("classic", strength, min_dist=3, inner_radius=radius, inner_gain=-1, outer_gain=0)


def sweep(strength=10, reach=220):
    """Moving the cursor stirs whatever it passes (a still cursor does nothing)."""
    return Field("wake", strength, max_dist=reach)


# ------------------------------------------------------------------ the presets

def starfield(count=900, brightness=0.45):
    """A still, faintly twinkling sky behind a cosmic preset (drawn last, touches nothing)."""
    return Layer("sky", count, [], motion="fixed", velocity="zero", twinkle=0.5, twinkle_period=4.0,
                 color_mode="fixed", color=[200, 210, 255], brightness=brightness)


def galaxy():
    return Preset(
        "Binary Galaxy", "Two gravitational cores chase each other around the same ellipse while thirty-six "
        "thousand stars are pulled in and swirled about, drawn out into spiral arms and a bridge of stars "
        "between the two. Moving the mouse stirs them up.",
        layers=[
            Layer("core", 2, motion="path", path_size=[0.4, 0.28], path_freq=[1, 1],
                  path_speed=0.01, path_spread=0.5, look="dot", dot=12, dot_soft=1.0,
                  color_mode="fixed", color=[255, 236, 200], brightness=0.6),
            Layer("stars", 36000, [
                Pull(ABOVE, Field("classic", 22, min_dist=10)),
                Pull(ABOVE, Field("vortex", 6, min_dist=10)),
                Pull(MOUSE, sweep(8, 260)),
            ], velocity="orbit", start_speed=4, jitter=0.05, variety=0.9,
                color_mode="speed", color=[70, 90, 220], color2=[255, 220, 170], speed_ref=5.5, brightness=1.15),
            starfield(),
        ],
        friction=0.0004, trail=0.6, blend="add", glow=0.45,
    )


def black_hole():
    return Preset(
        "Black Hole", "Stardust is born at the edges of the screen and spirals into the black hole at the "
        "centre, faster and hotter the closer it gets, until the event horizon swallows it; a thin ring of "
        "light circles just outside. It is reborn at the edge, so the accretion disk never runs dry.",
        layers=[
            Layer("disk", 30000, [
                Pull(CENTER, Field("classic", 90, min_dist=18, absorb=16)),
                Pull(CENTER, Field("vortex", 30, min_dist=18)),
                Pull(MOUSE, push(180, 120)),
            ], spawn="edges", velocity="orbit", start_speed=3, variety=0.5, jitter=0.02,
                life=700, life_jitter=0.8, fade=False,
                color_mode="speed", color=[120, 45, 25], color2=[255, 248, 225], speed_ref=7, brightness=1.3),
            Layer("photon ring", 1500, [Pull(CENTER, Field("ring", 3.0, radius=30)),
                                        Pull(CENTER, Field("vortex", 40, min_dist=10))],
                  spawn="circle", spawn_radius=30, spawn_spread=3, velocity="orbit", start_speed=6, jitter=0.25,
                  variety=0.3, color_mode="fixed", color=[255, 215, 170], brightness=0.4),
            starfield(700, 0.35),
        ],
        friction=0.004, trail=0.7, blend="add", glow=0.45,
    )


def saturn():
    return Preset(
        "Saturn's Rings", "A pale planet hangs in the middle of three rings, each turning at its own speed. A "
        "shepherd moon patrols the inner ring and clears a gap wherever it passes. The mouse pushes the rings "
        "out of shape and they slowly settle back.",
        layers=[
            Layer("planet", 1, motion="fixed", spawn="center", look="dot", dot=120, dot_soft=0.35,
                  color_mode="fixed", color=[214, 180, 130], brightness=0.75),
            Layer("shepherd", 1, motion="path", path_size=[0.236, 0.378], path_freq=[1, 1], path_speed=0.05,
                  look="dot", dot=6, color_mode="fixed", color=[255, 230, 200]),
            Layer("inner", 9000, [Pull(CENTER, Field("ring", 2.0, radius=170)), Pull(CENTER, Field("vortex", 9, min_dist=30)),
                                  Pull(ABOVE, push(90, 40)), Pull(MOUSE, push(200, 120))],
                  variety=0.5, jitter=0.04, velocity="orbit", start_speed=3.5, spawn="circle", spawn_radius=170,
                  color_mode="speed", color=[170, 140, 100], color2=[255, 240, 210], speed_ref=5, brightness=1.6),
            Layer("middle", 14000, [Pull(CENTER, Field("ring", 2.0, radius=235)), Pull(CENTER, Field("vortex", 7, min_dist=30)),
                                    Pull(MOUSE, push(200, 120))],
                  variety=0.5, jitter=0.04, velocity="orbit", start_speed=3, spawn="circle", spawn_radius=235,
                  color_mode="speed", color=[150, 130, 110], color2=[240, 230, 220], speed_ref=4.5, brightness=1.6),
            Layer("outer", 10000, [Pull(CENTER, Field("ring", 2.0, radius=310)), Pull(CENTER, Field("vortex", 5.5, min_dist=30)),
                                   Pull(MOUSE, push(200, 120))],
                  variety=0.5, jitter=0.04, velocity="orbit", start_speed=2.6, spawn="circle", spawn_radius=310,
                  color_mode="speed", color=[120, 110, 100], color2=[220, 215, 210], speed_ref=4, brightness=1.6),
            starfield(700, 0.35),
        ],
        friction=0.004, trail=0.3, blend="add", glow=0.35,
    )


def constellation():
    return Preset(
        "Constellations", "A slowly drifting, softly twinkling night sky. The cursor is a torch: wherever it "
        "shines, each bright star joins up with its two nearest neighbours into constellations, which go dark "
        "again once you move on.",
        layers=[
            Layer("star", 420, [], jitter=0.006, max_speed=0.2, friction=0.0, look="dot", dot=4, dot_soft=0.4,
                  links=130, link_max=2, link_brightness=0.8, link_reveal=340, twinkle=0.3, twinkle_period=2.5,
                  color_mode="rainbow", velocity="random", start_speed=0.1, brightness=1.1),
            Layer("dust", 2500, [], jitter=0.004, max_speed=0.15, friction=0.0, twinkle=0.5, twinkle_period=3.0,
                  color_mode="rainbow", brightness=0.55, velocity="random", start_speed=0.05),
        ],
        background=[3, 5, 14], click_invert=False,
        palette=Palette(hue=220, hue_speed=0, saturation=0.22, value=1.0, spread=140),
    )


def murmuration():
    return Preset(
        "Murmuration", "Dusk. Three lead birds fly along invisible curves; fifteen thousand starlings are drawn "
        "to them, following their neighbours, keeping their distance and never stopping, so the flock folds "
        "and pours across the sky. The mouse is a hawk.",
        layers=[
            Layer("leader", 3, motion="path", path_size=[0.75, 0.6], path_freq=[2, 3], path_speed=0.012,
                  path_spread=0.12, look="none"),
            Layer("birds", 15000, [
                Pull(ABOVE, Field("classic", 5, power=0.5, min_dist=10, inner_radius=60, inner_gain=0.2)),
                Pull(MOUSE, push(320, 170)),
            ], align=0.1, pressure=0.06, cell=20, jitter=0.06, max_speed=4.5, min_speed=2.2,
                variety=0.5, velocity="random", start_speed=2,
                color_mode="speed", color=[120, 130, 170], color2=[235, 225, 215], speed_ref=4.5),
        ],
        friction=0.0002, background=[9, 11, 22], trail=0.35, click_invert=False,
    )


def snow_globe():
    return Preset(
        "Snow Globe", "Gravity pulls down, the walls are solid and pressure lets the snow really pile up. "
        "Every flake melts after a while and falls again from the sky, so it never stops snowing, and a few "
        "big soft flakes drift past close up. A slow wind lifts the snow; the mouse sweeps it away.",
        layers=[
            Layer("snow", 22000, [
                Pull(MOUSE, push(240, 150)),
                Pull(MOUSE, sweep(14, 220)),
            ], pressure=0.25, cell=10, jitter=0.02, velocity="zero", life=1200, life_jitter=0.6,
                color_mode="speed", color=[190, 205, 240], color2=[255, 255, 255], speed_ref=3, brightness=1.2),
            Layer("near", 90, [Pull(MOUSE, sweep(10, 260))], spawn="random", velocity="zero", wind=0.4,
                  flow=1.5, life=900, life_jitter=0.5, look="dot", dot=30, dot_soft=1.0,
                  color_mode="fixed", color=[220, 230, 255], brightness=0.4),
        ],
        friction=0.002, wind=[0.0, 0.05], edge="bounce", bounce=0.3,
        background=[8, 10, 22], flow=Flow(True, 0.1, 450, 0.12),
    )


def fireworks():
    return Preset(
        "Fireworks", "A night of different shells: big round peonies, tilted rings, golden willows that "
        "glitter and droop, and quick crackling chrysanthemums, each on its own fuse so they never go off in "
        "step. Every burst has its own colour. Click to launch a peony at the cursor.",
        layers=[
            Layer("peony fuse", 1, motion="teleport", teleport_every=97, look="none"),
            Layer("peony", 9000, [Pull(MOUSE, sweep(10, 200))], spawn="above", velocity="sphere",
                  start_speed=6.5, life=97, life_jitter=0.0, friction=0.003, click_burst=2500,
                  color_mode="birth"),
            Layer("ring fuse", 1, motion="teleport", teleport_every=131, look="none"),
            Layer("ring", 2600, [Pull(MOUSE, sweep(10, 200))], spawn="above", velocity="ring",
                  start_speed=5.5, life=131, life_jitter=0.0, friction=0.006, size=2,
                  color_mode="birth", brightness=1.1),
            Layer("willow fuse", 1, motion="teleport", teleport_every=173, look="none"),
            Layer("willow", 7000, [Pull(MOUSE, sweep(10, 200))], spawn="above", velocity="sphere",
                  start_speed=4.2, life=173, life_jitter=0.0, friction=0.016, twinkle=0.45, twinkle_period=0.5,
                  color_mode="age", color=[255, 214, 140], color2=[150, 60, 20], brightness=1.2),
            Layer("crackle fuse", 1, motion="teleport", teleport_every=151, look="none"),
            Layer("crackle", 4000, [Pull(MOUSE, sweep(10, 200))], spawn="above", velocity="sphere",
                  start_speed=8.5, life=151, life_jitter=0.0, friction=0.03, twinkle=1.0, twinkle_period=0.3,
                  color_mode="birth", brightness=1.4),
        ],
        wind=[0.0, 0.09], trail=0.8, blend="add", glow=0.55, click_invert=False,
        palette=Palette(hue=20, hue_speed=37, saturation=0.65, value=1.0),
    )


def campfire():
    return Preset(
        "Campfire", "A fire burns low in the dark: flames rise, turbulence twists them into tongues that go "
        "from white to orange to ash, and sparks spiral up far above them, flickering out on the way. The "
        "mouse stirs the flames.",
        layers=[
            Layer("hearth", 1, motion="path", path_center=[0.5, 0.8], path_size=[0.0, 0.0], path_speed=0.0,
                  look="dot", dot=90, dot_soft=1.0, color_mode="fixed", color=[255, 110, 30], brightness=0.35),
            Layer("flame", 22000, [Pull(MOUSE, push(200, 110)), Pull(MOUSE, sweep(14, 200))],
                  spawn="above_ring", spawn_radius=22, spawn_spread=14, velocity="random", start_speed=1.8,
                  life=150, life_jitter=0.5, jitter=0.08, friction=0.004, wind=1.0, flow=1.0,
                  color_mode="age", color=[255, 240, 190], color2=[160, 30, 10], brightness=1.6),
            Layer("spark", 500, [Pull(MOUSE, sweep(14, 200))], spawn="above", velocity="random", start_speed=2.5,
                  life=260, life_jitter=0.6, jitter=0.15, friction=0.01, wind=1.6, flow=2.0, size=2,
                  twinkle=0.6, twinkle_period=0.8, color_mode="age", color=[255, 220, 140], color2=[200, 50, 10],
                  brightness=1.5),
        ],
        wind=[0.0, -0.08], flow=Flow(True, 0.08, 140, 0.6), trail=0.6, blend="add", glow=0.5,
    )


def butterfly():
    return Preset(
        "Butterfly Effect", "Thirty thousand points start squeezed into one tiny stretch of the Lorenz "
        "attractor, almost a single point. Within seconds they are drawn out into a rainbow ribbon and folded "
        "again and again; half a minute later they fill the whole butterfly. A tiny difference at the start, a "
        "completely different ending. It turns slowly in 3D; move the cursor left and right to turn it "
        "yourself. It starts over every thirty seconds.",
        layers=[Layer("air", 30000, [], motion="flow3d", life=1800, life_jitter=0.0, fade=False,
                      color_mode="index", brightness=1.4)],
        trail=0.8, blend="add", glow=0.45, click_invert=False,
        flow3d=Flow3D("lorenz", spin=0.005, start="blob", blob=0.01),
        palette=Palette(hue=0, hue_speed=0, saturation=0.75, value=1.0, spread=300),
    )


def field_lines():
    return Preset(
        "Field Lines", "Three positive charges drift along their paths and the cursor is a negative charge. "
        "Tiny particles leave the positive charges and follow the electric field exactly, step by step, "
        "drawing field lines until the cursor absorbs them. Move the cursor and the whole map bends with it; "
        "hold the mouse and the cursor turns positive.",
        layers=[
            Layer("charge", 3, motion="path", path_size=[0.55, 0.42], path_freq=[1, 2], path_speed=0.006,
                  path_spread=0.33, look="dot", dot=10, color_mode="fixed", color=[255, 150, 120]),
            Layer("line", 9000, [Pull(ABOVE, Field("classic", -40, min_dist=2)),
                                 Pull(MOUSE, Field("classic", 120, min_dist=2, absorb=14))],
                  spawn="above_ring", spawn_radius=12, velocity="outward", start_speed=2.5, damping=1.0,
                  min_speed=2.5, max_speed=2.5, life=500, life_jitter=0.3, color_mode="birth", brightness=1.5),
        ],
        edge="respawn", trail=0.93, blend="add", glow=0.7, background=[4, 4, 10],
        palette=Palette(hue=20, hue_speed=0.0, saturation=0.55, value=1.0),
    )


def kaleidoscope():
    return Preset(
        "Kaleidoscope", "Stardust swirls around your mouse and the picture is copied six times round, "
        "mirrored: move the cursor and you are turning the kaleidoscope. Hold the mouse to let the dust fly "
        "outward and redraw the pattern.",
        layers=[Layer("dust", 10000, [
            Pull(ABOVE, Field("classic", 24, min_dist=12)),
            Pull(ABOVE, Field("vortex", 10, min_dist=12)),
        ], variety=0.8, jitter=0.04, spawn="mouse", velocity="orbit", start_speed=4,
            color_mode="rainbow", brightness=1.2)],
        friction=0.0015, trail=0.88, blend="add", glow=0.28, symmetry=6, mirror=True, click_invert=True,
        palette=Palette(hue=320, hue_speed=4, saturation=0.75, value=1.0, spread=150),
    )


def heartbeat():
    return Preset(
        "Heartbeat", "A red ring beats like a heart, a quick double beat and a rest, once a second; every beat "
        "throws a ripple of light outward that falls back in.",
        layers=[Layer("pulse", 24000, [
            Pull(CENTER, Field("ring", 1.2, radius=180, pulse=0.3, period=1.0)),
            Pull(CENTER, Field("ring", 0.7, radius=180, pulse=0.3, period=0.5, phase=0.25)),
            Pull(CENTER, Field("vortex", 5, min_dist=20)),
            Pull(MOUSE, push(200, 120)),
        ], variety=0.7, jitter=0.06, spawn="circle", spawn_radius=180, spawn_spread=10, velocity="orbit",
            start_speed=3, color_mode="speed", color=[140, 20, 40], color2=[255, 130, 150], speed_ref=7,
            brightness=1.6)],
        friction=0.003, trail=0.55, blend="add", glow=0.4,
    )


def ink():
    return Preset(
        "Marbled Ink", "No gravity, only a slowly changing field of eddies. Twenty-five thousand points flow "
        "along it, coloured by their direction, and long-exposure trails paint the streamlines into marble. "
        "The mouse is a pen dipped in the ink: drag it and the ink is pulled along behind the nib and curls "
        "into new swirls; hold still and nothing moves.",
        layers=[Layer("ink", 25000, [Pull(MOUSE, Field("drag", 60, max_dist=40)),     # the nib carries ink along
                                     Pull(MOUSE, Field("drag", 8, max_dist=130))],    # and drags the ink around it
                      flow=1.0, velocity="zero", color_mode="direction")],
        friction=0.03, trail=0.94, blend="add", glow=0.28,
        flow=Flow(True, 0.12, 420, 0.06, mode="carry"),
        palette=Palette(hue=190, hue_speed=2, saturation=0.75, value=1.0),
    )


# ------------------------------------------------------------------ the list

# side by side, no categories; the first nine are on the hotkeys 1-9
BUILTIN = [
    ("galaxy", galaxy),
    ("black_hole", black_hole),
    ("saturn", saturn),
    ("constellation", constellation),
    ("murmuration", murmuration),
    ("snow_globe", snow_globe),
    ("fireworks", fireworks),
    ("campfire", campfire),
    ("butterfly", butterfly),
    ("field_lines", field_lines),
    ("kaleidoscope", kaleidoscope),
    ("heartbeat", heartbeat),
    ("ink", ink),
]
BUILTIN_KEYS = [k for k, _ in BUILTIN]
SLOTS = BUILTIN_KEYS[:9]
DEFAULT = SLOTS[0]


def blank() -> Preset:
    """A starting point for a new preset: one layer of dust around the cursor."""
    return Preset("New preset", layers=[Layer("dust", 15000, [Pull(ABOVE, Field("classic", 20, min_dist=10))])])


# ------------------------------------------------------------------ library

def slug(name: str) -> str:
    return re.sub(r"[^\w\-]+", "_", name, flags=re.UNICODE).strip("_")[:60]


class Library:
    """Built-ins (read only) plus your presets in presets_user/ (create, read,
    update, rename, delete)."""

    def __init__(self, folder: Path = USER_DIR):
        self.folder = Path(folder)
        self.reload()

    def _path(self, key):
        return self.folder / f"{key}.json"

    def reload(self):
        self.builtin = {k: make() for k, make in BUILTIN}
        self.custom: dict[str, Preset] = {}
        self.autosaved = None
        if self.folder.is_dir():
            for path in sorted(self.folder.glob("*.json")):
                if path.stem == STATE:
                    continue
                try:
                    p = from_dict(json.loads(path.read_text(encoding="utf-8")))
                except Exception as e:                 # a broken file must not stop the show
                    print(f"skipping {path.name}: {e}")
                    continue
                if path.stem == AUTOSAVE:
                    self.autosaved = p
                elif path.stem not in self.builtin:
                    self.custom[path.stem] = p

    # -- read
    def __contains__(self, key):
        return key in self.builtin or key in self.custom or (key == AUTOSAVE and self.autosaved)

    def get(self, key) -> Preset:
        if key in self.builtin:
            return copy.deepcopy(self.builtin[key])
        if key in self.custom:
            return copy.deepcopy(self.custom[key])
        if key == AUTOSAVE and self.autosaved:
            return copy.deepcopy(self.autosaved)
        raise KeyError(key)

    def keys(self):
        return BUILTIN_KEYS + sorted(self.custom) + ([AUTOSAVE] if self.autosaved else [])

    def listing(self):
        """[key, title, group, slot (1-9 or None), editable] for the panel and menus; the built-ins
        have no group (""), your own are under MINE / AUTOSAVED."""
        out = [[k, self.builtin[k].title, "", SLOTS.index(k) + 1 if k in SLOTS else None, False]
               for k in BUILTIN_KEYS]
        out += [[k, self.custom[k].title, MINE, None, True] for k in sorted(self.custom)]
        if self.autosaved:
            out.append([AUTOSAVE, "Last experiment (autosaved)", AUTOSAVED, None, False])
        return out

    def is_custom(self, key):
        return key in self.custom

    # -- write
    def _write(self, key, preset):
        self.folder.mkdir(exist_ok=True)
        self._path(key).write_text(json.dumps(to_dict(preset), ensure_ascii=False, indent=2),
                                   encoding="utf-8")

    def save(self, name: str, preset: Preset) -> str:
        """Create or update a custom preset; returns its key."""
        key = slug(name)
        if not key or key in self.builtin or key.startswith("_"):
            raise ValueError(f"'{name}' can't be used as a name (the built-in presets' names are taken)")
        preset = copy.deepcopy(preset)
        if key not in self.custom:
            preset.title = name.strip() or key
        self._write(key, preset)
        self.custom[key] = preset
        return key

    def rename(self, key: str, new_name: str) -> str:
        if key not in self.custom:
            raise KeyError(key)
        new_key = slug(new_name)
        if not new_key or new_key in self.builtin or new_key.startswith("_") or (
                new_key in self.custom and new_key != key):
            raise ValueError(f"'{new_name}' can't be used as a name")
        preset = self.custom.pop(key)
        preset.title = new_name.strip()
        if new_key != key:
            self._path(key).unlink(missing_ok=True)
        self._write(new_key, preset)
        self.custom[new_key] = preset
        return new_key

    def delete(self, key: str) -> bool:
        if key not in self.custom:
            return False
        self._path(key).unlink(missing_ok=True)
        del self.custom[key]
        return True

    def autosave(self, preset: Preset):
        self._write(AUTOSAVE, preset)
        self.autosaved = copy.deepcopy(preset)

    # -- remember what was showing (and other app settings)
    def state(self) -> dict:
        try:
            return json.loads(self._path(STATE).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}

    def set_state(self, **values):
        try:
            self.folder.mkdir(exist_ok=True)
            st = {**self.state(), **values}
            self._path(STATE).write_text(json.dumps(st), encoding="utf-8")
        except OSError:
            pass

    def last(self):
        key = self.state().get("last")
        return key if key in self else None

    def remember(self, key):
        self.set_state(last=key)


def get(key: str) -> Preset:
    return Library().get(key)
