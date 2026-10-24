"""
The built-in presets (grouped; the first nine have hotkeys 1-9) and the library of your own.

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

from config import ABOVE, CENTER, MOUSE, Attractor, Field, Flow, Flow3D, Layer, Palette, Preset, Pull, from_dict, to_dict

USER_DIR = Path(__file__).with_name("presets_user")
AUTOSAVE = "_autosave"
STATE = "_state"
MINE, AUTOSAVED = "Mine", "Autosaved"          # the groups of your own presets


def push(strength=250, radius=150):
    """The cursor shoves things out of a circle around it."""
    return Field("classic", strength, min_dist=3, inner_radius=radius, inner_gain=-1, outer_gain=0)


def sweep(strength=10, reach=220):
    """Moving the cursor stirs whatever it passes (a still cursor does nothing)."""
    return Field("wake", strength, max_dist=reach)


# ------------------------------------------------------------------ 1-9

def galaxy():
    return Preset(
        "Binary Galaxy", "Two gravitational cores chase each other around the same ellipse while thirty-four "
        "thousand stars are pulled in and swirled about, drawn out into spiral arms and a bridge of stars "
        "between the two. Moving the mouse stirs them up.",
        layers=[
            Layer("core", 2, motion="path", path_size=[0.36, 0.26], path_freq=[1, 1],
                  path_speed=0.01, path_spread=0.5, look="none"),
            Layer("stars", 34000, [
                Pull(ABOVE, Field("classic", 22, min_dist=10)),
                Pull(ABOVE, Field("vortex", 6, min_dist=10)),
                Pull(MOUSE, sweep(8, 260)),
            ], velocity="orbit", start_speed=4, jitter=0.05, variety=0.9,
                color_mode="speed", color=[60, 80, 200], color2=[255, 214, 160], speed_ref=5.5),
        ],
        friction=0.0004, trail=0.55, blend="add", glow=0.45,
    )


def strange_attractor():
    return Preset(
        "Strange Attractor", "Sixty thousand points each hop one step of the Clifford map every frame and "
        "gather into a fractal that slowly changes shape. The mouse pushes it aside.",
        layers=[Layer("dust", 60000, [Pull(MOUSE, push(220, 140))], motion="attractor",
                      friction=0.05, color_mode="rainbow")],
        trail=0.82, blend="add", glow=0.22,
        palette=Palette(hue=200, hue_speed=5, saturation=0.65, value=0.9, spread=140),
        attractor=Attractor("clifford", -1.7, 1.8, -1.9, -0.4, scale=0.92, morph=0.18, morph_speed=0.012),
    )


def orrery():
    return Preset(
        "Orrery", "Four levels deep: a sun drifts along its path, planets orbit the sun, moons orbit the "
        "planets, and the moons shed fading dust that traces loop after loop of spirals.",
        layers=[
            Layer("sun", 1, motion="path", path_size=[0.22, 0.16], path_freq=[1, 1], path_speed=0.015,
                  look="dot", dot=16, color_mode="fixed", color=[255, 210, 140]),
            Layer("planet", 4, [Pull(ABOVE, Field("classic", 26, min_dist=20))],
                  spawn="above_ring", spawn_radius=170, velocity="orbit", start_speed=5.1, friction=0.0,
                  look="dot", dot=8, color_mode="fixed", color=[140, 190, 255]),
            Layer("moon", 12, [Pull(ABOVE, Field("classic", 40, min_dist=4, max_dist=80))],
                  spawn="above_ring", spawn_radius=18, velocity="orbit", start_speed=6.3, friction=0.0,
                  life=600, life_jitter=0.5, fade=False,
                  look="dot", dot=4, color_mode="fixed", color=[230, 230, 255]),
            Layer("dust", 30000, [Pull(MOUSE, sweep(12, 220))], spawn="above", velocity="inherit",
                  start_speed=0.4, life=260, life_jitter=0.5, friction=0.02,
                  color_mode="age", color=[255, 240, 210], color2=[60, 90, 220], brightness=1.3),
        ],
        friction=0.0005, blend="add", glow=0.6, trail=0.3, edge="respawn",
    )


def murmuration():
    return Preset(
        "Murmuration", "Three lead birds fly along invisible curves. Fifteen thousand starlings are drawn to "
        "them, following their neighbours, keeping their distance and never stopping. The mouse is a hawk.",
        layers=[
            Layer("leader", 3, motion="path", path_size=[0.75, 0.6], path_freq=[2, 3], path_speed=0.012,
                  path_spread=0.12, look="none"),
            Layer("birds", 15000, [
                Pull(ABOVE, Field("classic", 5, power=0.5, min_dist=10, inner_radius=60, inner_gain=0.2)),
                Pull(MOUSE, push(320, 170)),
            ], align=0.1, pressure=0.06, cell=20, jitter=0.06, max_speed=4.5, min_speed=2.2,
                variety=0.5, velocity="random", start_speed=2, color_mode="fixed", color=[24, 20, 32]),
        ],
        friction=0.0002, background=[214, 178, 160], click_invert=False,
    )


def fabric():
    return Preset(
        "Elastic Fabric", "A cloth of grid points, each held in place by a spring. An invisible spirit twists "
        "it into whorls as it wanders; your mouse leaves ripples that slowly heal once you move on.",
        layers=[
            Layer("wisp", 1, motion="path", path_size=[0.8, 0.7], path_freq=[2, 3], path_speed=0.01,
                  look="none"),
            Layer("cloth", 16000, [
                Pull(ABOVE, Field("vortex", 40, min_dist=5, max_dist=230)),
                Pull(ABOVE, push(120, 70)),
                Pull(MOUSE, push(300, 130)),
                Pull(MOUSE, sweep(18, 200)),
            ], spawn="grid", velocity="zero", home=0.03, friction=0.02, size=2,
                color_mode="speed", color=[80, 95, 150], color2=[255, 215, 150], speed_ref=2.5),
        ],
        flow=Flow(True, 0.02, 420, 0.15),
    )


def mandala():
    return Preset(
        "Mandala", "Three seeds wander along Lissajous curves while stardust swirls around them (the swirl "
        "ebbs and flows every 11 seconds). Six rotated, mirrored copies turn it into a kaleidoscope.",
        layers=[
            Layer("seed", 3, motion="path", path_size=[0.42, 0.42], path_freq=[2, 3], path_speed=0.02,
                  path_spread=1.0, look="none"),
            Layer("dust", 9000, [
                Pull(ABOVE, Field("classic", 18, min_dist=8)),
                Pull(ABOVE, Field("vortex", 9, min_dist=8, pulse=0.8, period=11)),
            ], jitter=0.03, velocity="random", start_speed=2, color_mode="direction"),
        ],
        friction=0.001, trail=0.88, blend="add", glow=0.25, symmetry=6, mirror=True,
        palette=Palette(hue=280, hue_speed=4, saturation=0.6, value=0.9),
    )


def ink():
    return Preset(
        "Marbled Ink", "No gravity, only a slowly changing field of eddies. Twenty-five thousand points flow "
        "along it, coloured by their direction, and long-exposure trails paint the streamlines into marble.",
        layers=[Layer("ink", 25000, [Pull(MOUSE, push(220, 140)), Pull(MOUSE, sweep(14, 240))],
                      flow=1.0, velocity="zero", color_mode="direction")],
        friction=0.05, trail=0.94, blend="add", glow=0.28,
        flow=Flow(True, 0.12, 420, 0.06, mode="carry"),
        palette=Palette(hue=190, hue_speed=2, saturation=0.75, value=1.0),
    )


def snow_globe():
    return Preset(
        "Snow Globe", "Gravity pulls down, the walls are solid and pressure lets the snow really pile up. "
        "Every flake melts after a while and falls again from the sky, so it never stops snowing. A slow wind "
        "lifts the snow; the mouse sweeps it away.",
        layers=[Layer("snow", 22000, [
            Pull(MOUSE, push(240, 150)),
            Pull(MOUSE, sweep(14, 220)),
        ], pressure=0.25, cell=10, jitter=0.02, velocity="zero", life=1500, life_jitter=0.6,
            color_mode="speed", color=[190, 205, 240], color2=[255, 255, 255], speed_ref=3, brightness=1.2)],
        friction=0.002, wind=[0.0, 0.05], edge="bounce", bounce=0.3,
        background=[8, 10, 22], flow=Flow(True, 0.1, 450, 0.12),
    )


def fireworks():
    return Preset(
        "Fireworks", "Three invisible fuses jump somewhere new every so often. All the sparks share one "
        "lifetime, so they die together and burst together into a shell at the new spot, each one in the "
        "colour of the moment it was born. Click to launch one at the cursor.",
        layers=[
            Layer("shell", 3, motion="teleport", teleport_every=110, look="none"),
            Layer("spark", 24000, [Pull(MOUSE, sweep(10, 200))], spawn="above", velocity="sphere",
                  start_speed=6, life=110, life_jitter=0.0, friction=0.002, click_burst=2500,
                  color_mode="birth"),
        ],
        wind=[0.0, 0.09], trail=0.8, blend="add", glow=0.55, click_invert=False,
        palette=Palette(hue=20, hue_speed=25, saturation=0.6, value=1.0),
    )



# ------------------------------------------------------------------ cosmos

def black_hole():
    return Preset(
        "Black Hole", "Stardust is born at the edges of the screen and spirals into the black hole at the "
        "centre, faster and brighter the closer it gets, until the event horizon swallows it. It is reborn at "
        "the edge, so the accretion disk never runs dry.",
        layers=[Layer("disk", 30000, [
            Pull(CENTER, Field("classic", 90, min_dist=18, absorb=16)),
            Pull(CENTER, Field("vortex", 30, min_dist=18)),
            Pull(MOUSE, push(180, 120)),
        ], spawn="edges", velocity="orbit", start_speed=3, variety=0.5, jitter=0.02,
            life=700, life_jitter=0.8, fade=False,
            color_mode="speed", color=[120, 50, 30], color2=[255, 250, 230], speed_ref=7, brightness=1.3)],
        friction=0.004, trail=0.7, blend="add", glow=0.45,
    )


def comets():
    return Preset(
        "Comets", "Five comets fly in formation along one great curve, trailing tails that the solar wind "
        "blows back and slowly puts out. The mouse scatters the tails.",
        layers=[
            Layer("comet", 5, motion="path", path_size=[0.85, 0.7], path_freq=[1, 2], path_speed=0.03,
                  path_spread=0.18, look="dot", dot=7, color_mode="fixed", color=[255, 255, 240]),
            Layer("tail", 26000, [Pull(MOUSE, sweep(14, 220))], spawn="above", velocity="inherit",
                  start_speed=0.8, life=140, life_jitter=0.4, friction=0.01, jitter=0.03, wind=1.0,
                  color_mode="age", color=[200, 235, 255], color2=[60, 60, 160], brightness=1.2),
        ],
        wind=[0.03, -0.015], trail=0.5, blend="add", glow=0.5,
    )


def supernova():
    return Preset(
        "Supernova", "Every particle shares the same lifetime: they burst out of the centre together, an "
        "invisible spring slows them down and pulls them back, and the instant they fall in they die together "
        "and burst out again.",
        layers=[Layer("ejecta", 30000, [
            Pull(CENTER, Field("classic", 0.0004, power=-1, min_dist=2)),
            Pull(MOUSE, push(40, 110)),
        ], spawn="center", velocity="outward", start_speed=9, life=320, life_jitter=0.0, fade=True,
            variety=0.3, color_mode="age", color=[255, 250, 220], color2=[200, 40, 60], brightness=1.5)],
        friction=0.0001, trail=0.75, blend="add", glow=0.4,
    )


def saturn():
    return Preset(
        "Saturn's Rings", "Three rings turn around the centre of the screen, each at its own speed. A shepherd "
        "moon patrols the inner ring and clears a gap wherever it passes.",
        layers=[
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
        ],
        friction=0.004, trail=0.3, blend="add", glow=0.35,
    )


def pocket_universe():
    return Preset(
        "Pocket Universe", "A de Jong strange attractor follows your mouse: the fractal wanders across the "
        "desktop with the cursor, slowly changing shape as it goes.",
        layers=[Layer("dust", 40000, [], motion="attractor", color_mode="rainbow")],
        trail=0.8, blend="add", glow=0.25, click_invert=False,
        palette=Palette(hue=30, hue_speed=6, saturation=0.7, value=0.95, spread=90),
        attractor=Attractor("dejong", 1.4, -2.3, 2.4, -2.1, scale=0.62, morph=0.3, morph_speed=0.01,
                            around=MOUSE),
    )


# ------------------------------------------------------------------ nature

def fish():
    return Preset(
        "School of Fish", "Ten thousand fish in an aquarium follow their neighbours, keep their distance and "
        "turn when they meet the glass, while a few leaders take the whole school round and round. Move the "
        "cursor slowly and they simply swim around it; swipe fast and the school bursts apart, then gathers "
        "again.",
        layers=[
            Layer("leader", 4, motion="path", path_size=[0.7, 0.6], path_freq=[3, 2], path_speed=0.01,
                  path_spread=0.25, look="none"),
            Layer("fish", 10000, [
                Pull(ABOVE, Field("classic", 4, power=0.5, min_dist=10, inner_radius=50, inner_gain=0.1)),
                Pull(MOUSE, Field("startle", 0.45, max_dist=280)),
                Pull(MOUSE, push(160, 60)),
            ], align=0.14, pressure=0.1, cell=18, jitter=0.04, max_speed=3.8, min_speed=1.6, variety=0.4,
                velocity="random", start_speed=2, size=2,
                color_mode="speed", color=[40, 110, 150], color2=[220, 240, 255], speed_ref=4),
        ],
        friction=0.0003, edge="bounce", bounce=0.6, background=[4, 18, 34], click_invert=False,
    )


def fireflies():
    return Preset(
        "Fireflies", "A meadow on a summer night: three hundred fireflies drift about, dark most of the time, "
        "each flashing to its own rhythm. They scatter when the mouse comes near.",
        layers=[Layer("fly", 320, [Pull(MOUSE, push(140, 120))], motion="wander", max_speed=0.6, friction=0.05,
                      look="dot", dot=26, dot_soft=1.0, twinkle=1.0, twinkle_period=4.0,
                      color_mode="fixed", color=[255, 220, 100], brightness=1.0)],
        trail=0.4, blend="add", glow=0.8, background=[3, 8, 5], click_invert=False,
    )


def dandelion():
    return Preset(
        "Dandelion", "A dandelion stands in the middle of the screen, letting go of its seeds one by one; the "
        "breeze carries them off until they fade. Blow on it (swipe the mouse).",
        layers=[
            Layer("head", 1, motion="fixed", spawn="center", look="dot", dot=10, color_mode="fixed",
                  color=[240, 235, 210]),
            Layer("seed", 3000, [Pull(MOUSE, sweep(22, 260))], spawn="above", velocity="outward",
                  start_speed=0.6, life=700, life_jitter=0.6, friction=0.03, flow=1.0, wind=1.0,
                  look="dot", dot=3, color_mode="fixed", color=[250, 250, 240], brightness=0.9),
        ],
        wind=[0.004, -0.003], flow=Flow(True, 0.04, 380, 0.1, mode="carry"),
        background=[20, 28, 40], click_invert=False,
    )


def campfire():
    return Preset(
        "Campfire", "A fire burns in the middle of the screen: sparks rise, turbulence twists them into "
        "tongues of flame, and they go from white to orange to ash. The mouse stirs the flames.",
        layers=[
            Layer("ember", 1, motion="fixed", spawn="center", look="none"),
            Layer("flame", 16000, [Pull(MOUSE, push(200, 110)), Pull(MOUSE, sweep(14, 200))],
                  spawn="above", velocity="random", start_speed=1.8, life=170, life_jitter=0.5,
                  jitter=0.08, friction=0.004, wind=1.0, flow=1.0,
                  color_mode="age", color=[255, 240, 190], color2=[160, 30, 10], brightness=1.6),
        ],
        wind=[0.0, -0.08], flow=Flow(True, 0.08, 140, 0.6), trail=0.6, blend="add", glow=0.5,
    )


def will_o_wisp():
    return Preset(
        "Will-o'-the-Wisp", "A few ghostly green lights wander in the dark, trailing wisps of smoke that "
        "slowly drift away. Bring the mouse close and they shy away.",
        layers=[
            Layer("wisp", 6, [Pull(MOUSE, push(260, 160))], motion="wander", max_speed=1.6, friction=0.03,
                  look="dot", dot=18, dot_soft=0.85, color_mode="fixed", color=[150, 255, 190], brightness=1.4),
            Layer("smoke", 9000, [], spawn="above", velocity="random", start_speed=0.5, life=220,
                  life_jitter=0.4, friction=0.02, jitter=0.03, flow=1.0,
                  color_mode="age", color=[120, 230, 170], color2=[20, 50, 60], brightness=1.2),
        ],
        flow=Flow(True, 0.03, 300, 0.2), trail=0.5, blend="add", glow=0.5, background=[4, 6, 8],
        click_invert=False,
    )


def harmonics():
    return Preset(
        "Harmonics", "The centre of the screen is one linear spring, and every particle's springiness is a "
        "little different: each draws its own ellipse, and together they make an ever-changing pattern of "
        "beats.",
        layers=[Layer("dust", 24000, [
            Pull(CENTER, Field("classic", 0.0005, power=-1, min_dist=1)),
            Pull(MOUSE, push(120, 110)),
        ], variety=0.3, spawn="circle", spawn_radius=230, velocity="orbit", start_speed=2.5,
            color_mode="direction", brightness=1.4)],
        friction=0.0, trail=0.88, blend="add", glow=0.3,
        palette=Palette(hue=160, hue_speed=3, saturation=0.65, value=0.9),
    )


def kaleidoscope():
    return Preset(
        "Kaleidoscope", "Stardust swirls around your mouse and the picture is copied six times round, "
        "mirrored: move the cursor and you are turning the kaleidoscope.",
        layers=[Layer("dust", 7000, [
            Pull(ABOVE, Field("classic", 24, min_dist=12)),
            Pull(ABOVE, Field("vortex", 10, min_dist=12)),
        ], variety=0.8, jitter=0.04, spawn="mouse", velocity="orbit", start_speed=4,
            color_mode="rainbow", brightness=1.3)],
        friction=0.0015, trail=0.85, blend="add", glow=0.3, symmetry=6, mirror=True, click_invert=True,
        palette=Palette(hue=320, hue_speed=4, saturation=0.75, value=1.0, spread=120),
    )


def atom():
    return Preset(
        "Atom", "Three electron shells orbit the nucleus, each at its own speed and in its own colour; the "
        "nucleus is a knot of particles that cling to each other. The mouse pushes the shells out of shape.",
        layers=[
            Layer("nucleus", 400, [Pull(CENTER, Field("classic", 30, min_dist=4))], pressure=-0.6, cell=10,
                  jitter=0.15, friction=0.02, spawn="circle", spawn_radius=30, size=2,
                  color_mode="fixed", color=[255, 120, 90]),
            Layer("shell1", 3000, [Pull(CENTER, Field("ring", 2.5, radius=110)), Pull(CENTER, Field("vortex", 10, min_dist=20)),
                                   Pull(MOUSE, push(160, 100))],
                  spawn="circle", spawn_radius=110, velocity="orbit", start_speed=4, jitter=0.03,
                  color_mode="fixed", color=[120, 220, 255]),
            Layer("shell2", 5000, [Pull(CENTER, Field("ring", 2.5, radius=210)), Pull(CENTER, Field("vortex", -8, min_dist=20)),
                                   Pull(MOUSE, push(160, 100))],
                  spawn="circle", spawn_radius=210, velocity="orbit", start_speed=-3, jitter=0.03,
                  color_mode="fixed", color=[200, 160, 255]),
            Layer("shell3", 8000, [Pull(CENTER, Field("ring", 2.5, radius=320)), Pull(CENTER, Field("vortex", 6, min_dist=20)),
                                   Pull(MOUSE, push(160, 100))],
                  spawn="circle", spawn_radius=320, velocity="orbit", start_speed=2.5, jitter=0.03,
                  color_mode="fixed", color=[150, 255, 200]),
        ],
        friction=0.003, trail=0.6, blend="add", glow=0.45,
    )


def heartbeat():
    return Preset(
        "Heartbeat", "A red ring swells and shrinks to the rhythm of a heartbeat, and every beat sends a "
        "ripple of light outward.",
        layers=[Layer("pulse", 24000, [
            Pull(CENTER, Field("ring", 1.6, radius=180, pulse=0.35, period=1.6)),
            Pull(CENTER, Field("vortex", 5, min_dist=20)),
            Pull(MOUSE, push(200, 120)),
        ], variety=0.7, jitter=0.06, velocity="orbit", start_speed=3,
            color_mode="speed", color=[140, 20, 40], color2=[255, 120, 140], speed_ref=7, brightness=1.6)],
        friction=0.003, trail=0.55, blend="add", glow=0.4,
    )


# ------------------------------------------------------------------ fluid & interaction

def incense():
    return Preset(
        "Incense", "A wisp of smoke rises from the tip of your cursor, twisted into ribbons by turbulence and "
        "fainter the higher it climbs. Move the mouse slowly and the smoke leaves a wall hanging in the air.",
        layers=[Layer("smoke", 14000, [], spawn="mouse", velocity="random", start_speed=0.5, life=260,
                      life_jitter=0.4, friction=0.01, jitter=0.02, wind=1.0, flow=1.0, size=1,
                      color_mode="age", color=[230, 230, 240], color2=[40, 40, 60], brightness=0.8)],
        wind=[0.0, -0.035], flow=Flow(True, 0.06, 200, 0.5), trail=0.6, blend="add", glow=0.35,
        click_invert=False,
    )


def ripples():
    return Preset(
        "Ripples", "A still pond. Raindrops fall at random, each one spreading a ring of ripples before the "
        "water settles again. Drag the mouse across the surface to leave a wake.",
        layers=[
            Layer("drop", 3, motion="teleport", teleport_every=45, look="none"),
            Layer("water", 18000, [
                Pull(ABOVE, Field("classic", 4000, min_dist=2, inner_radius=120, inner_gain=-1, outer_gain=0)),
                Pull(MOUSE, sweep(40, 160)),
            ], spawn="grid", velocity="zero", home=0.02, friction=0.03, size=2,
                color_mode="speed", color=[40, 80, 130], color2=[220, 245, 255], speed_ref=2.5, brightness=1.6),
        ],
        background=[3, 8, 18], click_invert=False,
    )


def stardust_pen():
    return Preset(
        "Stardust Pen", "The mouse is a pen: wherever you draw it leaves a glowing trail of stardust that "
        "flies off at the pen's speed and is slowly curled away by gentle eddies until it fades. Hold still "
        "and it only gathers into a small cloud at the tip.",
        layers=[Layer("dust", 20000, [], spawn="mouse", velocity="inherit", start_speed=0.8, life=420,
                      life_jitter=0.5, friction=0.01, jitter=0.02, flow=1.0,
                      color_mode="rainbow", brightness=1.2)],
        trail=0.7, blend="add", glow=0.4, click_invert=False,
        flow=Flow(True, 0.05, 360, 0.1, mode="carry"),
        palette=Palette(hue=200, hue_speed=12, saturation=0.7, value=1.0, spread=60),
    )


def sprites():
    return Preset(
        "Sprites", "Three little sprites chase your mouse: move fast and they fall behind, let them catch up "
        "and they circle the cursor. Each one trails a tail of light that fades.",
        layers=[
            Layer("sprite", 3, [
                Pull(ABOVE, Field("classic", 20, power=0.5, min_dist=30)),
                Pull(ABOVE, Field("vortex", 14, min_dist=30, max_dist=160)),
                Pull(ABOVE, Field("drag", 2, max_dist=400)),
            ], spawn="mouse", velocity="orbit", start_speed=3, friction=0.0015, variety=0.4,
                look="dot", dot=7, color_mode="fixed", color=[255, 250, 230]),
            Layer("trail", 9000, [], spawn="above", velocity="inherit", start_speed=0.3, life=150,
                  life_jitter=0.3, friction=0.03, color_mode="age", color=[255, 220, 150], color2=[120, 60, 200],
                  brightness=1.3),
        ],
        trail=0.4, blend="add", glow=0.6, click_invert=False,
    )


def marbles():
    return Preset(
        "Marbles", "Three hundred marbles bounce around the desktop and off its edges without ever stopping. "
        "The mouse is a cue: swipe through them to send them flying. Fast ones glow white, slow ones dim.",
        layers=[Layer("marble", 300, [Pull(MOUSE, push(400, 90)), Pull(MOUSE, sweep(60, 120))],
                      velocity="random", start_speed=3, min_speed=1.2, max_speed=14, look="dot", dot=9,
                      color_mode="speed", color=[70, 90, 140], color2=[255, 255, 255], speed_ref=9)],
        friction=0.0003, edge="bounce", bounce=1.0, trail=0.5, blend="add", glow=0.5,
        background=[8, 10, 16], click_invert=False,
    )


# ------------------------------------------------------------------ new: cosmos

def warp():
    return Preset(
        "Warp Speed", "Stars pour out around the cursor, faster and faster until they stretch into streaks of "
        "light, like a ship jumping to hyperspace. The cursor is your heading: wherever you point it, that's "
        "where you fly. Hold the mouse to reverse.",
        layers=[Layer("star", 2500, [Pull(MOUSE, Field("classic", -0.0025, power=-1))],
                      spawn="mouse_ring", spawn_radius=70, spawn_spread=55, velocity="outward", start_speed=0.4,
                      life=400, life_jitter=0.5,
                      color_mode="speed", color=[30, 45, 110], color2=[255, 255, 255], speed_ref=14, size=2)],
        friction=0.0, edge="respawn", trail=0.8, blend="add", glow=0.6,
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


# ------------------------------------------------------------------ new: nature

def aurora():
    return Preset(
        "Aurora", "A curtain of light hangs from an invisible wavy line: it rises from the bottom edge, turns "
        "from green to violet and fades, and winds high above slowly fold the whole curtain. Moving the mouse "
        "stirs it.",
        layers=[
            Layer("band", 400, motion="path", path_size=[1.0, 0.12], path_freq=[1, 3], path_center=[0.5, 0.7],
                  path_speed=0.01, path_spread=0.5, look="none"),
            Layer("light", 30000, [Pull(MOUSE, sweep(10, 260))], spawn="above", velocity="zero", life=220,
                  life_jitter=0.5, wind=1.0, flow=1.0, friction=0.01,
                  color_mode="age", color=[90, 255, 150], color2=[150, 60, 255]),
        ],
        wind=[0.0, -0.05], flow=Flow(True, 0.03, 500, 0.1), trail=0.8, blend="add", glow=0.35,
        background=[2, 4, 12], click_invert=False,
    )


def snowflake():
    return Preset(
        "Snowflake", "A snowflake slowly grows from the centre: water molecules wander at random and freeze "
        "when they touch the ice (diffusion-limited aggregation). A spot must be touched four times before it "
        "freezes, so the arms grow thin and straight. Only one wedge grows; six rotated, mirrored copies make "
        "the whole flake. Once grown it stays for a dozen seconds, melts, and a new one grows. A quiet one "
        "that leaves the mouse alone (melting with the mouse can be turned on in the panel).",
        layers=[Layer("ice", 5500, [], motion="grow", grow_seed="center", grow_fold=6, grow_walkers=220,
                      grow_speed=6, grow_noise=4, grow_hold=12, grow_walker_light=0.25,
                      color_mode="birth", size=2)],
        symmetry=6, mirror=True, blend="add", glow=0.7, background=[3, 6, 16], click_invert=False,
        palette=Palette(hue=190, hue_speed=1.2, saturation=0.4, value=1.0),
    )


def slime_mould():
    return Preset(
        "Slime Mould", "Sixty thousand brainless slime-mould cells. Each one only smells left, ahead and "
        "right, turns toward the strongest scent and leaves more scent as it crawls. Together they weave a "
        "transport network that keeps rebuilding itself. The cursor is food and the network grows toward it; "
        "hold the mouse and it turns into repellent.",
        layers=[Layer("mould", 60000, [], motion="slime", spawn="random", velocity="random",
                      slime_angle=45, slime_turn=22.5, slime_dist=27, slime_speed=3, slime_decay=0.1,
                      slime_cell=3, slime_show=0.35, slime_mouse=30, slime_mouse_radius=30,
                      life=350, life_jitter=0.9, fade=False, look="none",
                      color_mode="fixed", color=[255, 200, 90])],
        background=[5, 4, 2],
    )


# ------------------------------------------------------------------ new: chaos

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


def apple_core():
    return Preset(
        "Apple Core", "The Aizawa attractor: thirty thousand points flow through 3D space along the same "
        "equations, winding into a ball with a tube through its middle, like an apple core. It slowly spins, "
        "the far side dimmer; move the cursor to turn it and look.",
        layers=[Layer("air", 30000, [], motion="flow3d", color_mode="speed", color=[60, 120, 230],
                      color2=[255, 200, 150], speed_ref=9, brightness=1.4)],
        trail=0.7, blend="add", glow=0.45, click_invert=False,
        flow3d=Flow3D("aizawa", spin=0.01, tilt=20),
    )


def pendulums():
    return Preset(
        "Chaos Pendulums", "Nine hundred double pendulums hang from one pivot, let go at angles only a "
        "thousandth of a degree apart. At first they swing as one; a few seconds later they suddenly fan out "
        "into a rainbow and then fall into utter chaos. Twenty seconds on they are let go again. Click to "
        "release them all from the cursor.",
        layers=[Layer("bob", 900, [], motion="pendulum", pend_pivot=[0.5, 0.47], pend_size=0.45, pend_angle=125,
                      pend_spread=0.001, pend_arms=250, pend_speed=0.8, life=1200, life_jitter=0.0,
                      color_mode="index", size=2)],
        trail=0.3, blend="add", glow=0.6,
        palette=Palette(hue=0, hue_speed=0, saturation=0.75, value=1.0, spread=300),
    )


# ------------------------------------------------------------------ new: geometry

def sunflower():
    return Preset(
        "Sunflower", "Six thousand seeds laid out the way a sunflower does it: each one turned 137.5° (the "
        "golden angle) further than the last, which falls into Fibonacci spirals all by itself. The angle "
        "slowly swings back and forth, and a hair off it the spirals turn into spokes, whirls and galaxies. "
        "The seeds are springy; the mouse brushes them aside.",
        layers=[Layer("seed", 6000, [Pull(MOUSE, push(300, 100))], motion="path", path_shape="sunflower",
                      path_size=[0.92, 0.92], path_speed=0.0, path_angle=137.508, path_sweep=0.15,
                      path_sweep_period=120, home=0.06, damping=0.15, look="dot", dot=4,
                      color_mode="index")],
        trail=0.5, blend="add", glow=0.5, background=[8, 6, 4],
        palette=Palette(hue=30, hue_speed=2, saturation=0.75, value=0.95, spread=360),
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


# ------------------------------------------------------------------ new: interaction

def watercolor():
    return Preset(
        "Watercolour", "On cream paper, three drops of paint fall in turn and invisible currents spread them "
        "out and draw them into threads, while older colours slowly fade back into the paper. Click to drop a "
        "new colour at the cursor; drag to stir the paint.",
        layers=[
            Layer("drop", 3, motion="teleport", teleport_every=240, look="none"),
            Layer("paint", 30000, [Pull(MOUSE, sweep(12, 220))], spawn="above", velocity="random",
                  start_speed=1.5, life=400, life_jitter=0.6, flow=1.0, click_burst=1500, friction=0.02,
                  color_mode="birth", size=2),
        ],
        trail=0.985, background=[236, 230, 218], click_invert=False,
        flow=Flow(True, 0.06, 300, 0.08, mode="carry"),
        palette=Palette(hue=200, hue_speed=6, saturation=0.6, value=0.7),
    )


# ------------------------------------------------------------------ new: words

# (poem, title · poet), all long in the public domain; one page each, the title layer turns with it
POEMS = [
    ("To see a World in a Grain of Sand\\nAnd a Heaven in a Wild Flower\\n"
     "Hold Infinity in the palm of your hand\\nAnd Eternity in an hour",
     "Auguries of Innocence · William Blake"),
    ("Who has seen the wind?\\nNeither I nor you:\\nBut when the leaves hang trembling,\\n"
     "The wind is passing through.",
     "Who Has Seen the Wind? · Christina Rossetti"),
    ("Tyger Tyger, burning bright,\\nIn the forests of the night;\\nWhat immortal hand or eye,\\n"
     "Could frame thy fearful symmetry?",
     "The Tyger · William Blake"),
    ("Hope is the thing with feathers\\nThat perches in the soul,\\n"
     "And sings the tune without the words,\\nAnd never stops at all",
     "Hope · Emily Dickinson"),
    ("I wandered lonely as a cloud\\nThat floats on high o'er vales and hills,\\n"
     "When all at once I saw a crowd,\\nA host, of golden daffodils",
     "I Wandered Lonely as a Cloud · William Wordsworth"),
    ("Nothing beside remains. Round the decay\\nOf that colossal Wreck, boundless and bare\\n"
     "The lone and level sands stretch far away.",
     "Ozymandias · Percy Bysshe Shelley"),
    ("Till rising and gliding out I wander'd off by myself,\\nIn the mystical moist night-air, "
     "and from time to time,\\nLook'd up in perfect silence at the stars.",
     "When I Heard the Learn'd Astronomer · Walt Whitman"),
    ("We are such stuff\\nAs dreams are made on, and our little life\\nIs rounded with a sleep.",
     "The Tempest · William Shakespeare"),
]
SERIF = "baskerville,palatino,georgia,hoeflertext,timesnewroman,notoserif,dejavuserif,liberationserif"


def stardust_clock():
    hand = [Pull(MOUSE, push(320, 150)), Pull(MOUSE, sweep(14, 220))]
    return Preset(
        "Stardust Clock", "Nearly twenty thousand grains of stardust spell out the time, with the weekday and "
        "date below. Every minute the stardust flies from the old digits to the new. The mouse blows the "
        "digits apart; move away and they find their way back.",
        layers=[
            Layer("time", 16000, hand, spawn="text", text="{time}", text_size=0.36, text_pos=[0.5, 0.44],
                  home=0.012, damping=0.06, jitter=0.03, velocity="zero",
                  color_mode="speed", color=[110, 150, 255], color2=[255, 225, 170], speed_ref=4, brightness=1.2),
            Layer("date", 3500, hand, spawn="text", text="{weekday}, {date}", text_size=0.065,
                  text_pos=[0.5, 0.74], home=0.015, damping=0.08, jitter=0.02, velocity="zero",
                  color_mode="speed", color=[100, 120, 210], color2=[255, 225, 170], speed_ref=4),
        ],
        friction=0.0, trail=0.45, blend="add", glow=0.5,
    )


def poem():
    hand = [Pull(MOUSE, sweep(16, 240)), Pull(MOUSE, push(220, 120))]
    return Preset(
        "Poems", "Stardust writes out a few lines of a poem, holds them for twelve seconds, then lifts off "
        "like sand in the wind and settles into the next one, with the title and poet underneath. Blake, "
        "Rossetti, Dickinson, Wordsworth, Shelley, Whitman and Shakespeare take turns. Click for the next "
        "poem; swipe the mouse for a gust of wind.",
        layers=[
            Layer("poem", 24000, hand, spawn="text", text="|".join(p for p, _ in POEMS), text_period=12,
                  text_click=True, text_size=0.075, text_pos=[0.5, 0.44], text_font=SERIF, home=0.01,
                  damping=0.05, jitter=0.02, flow=1.0, velocity="zero",
                  color_mode="speed", color=[230, 200, 150], color2=[255, 250, 235], speed_ref=4, brightness=0.9),
            Layer("title", 3000, hand, spawn="text", text="|".join(t for _, t in POEMS), text_period=12,
                  text_click=True, text_size=0.04, text_pos=[0.5, 0.76], text_font=SERIF, home=0.012,
                  damping=0.06, jitter=0.015, velocity="zero", color_mode="fixed", color=[170, 140, 110]),
        ],
        friction=0.0, trail=0.55, blend="add", glow=0.45, background=[6, 8, 16], click_invert=False,
        flow=Flow(True, 0.05, 260, 0.12),
    )


GROUPS = [
    ("Cosmos", [
        ("galaxy", galaxy), ("orrery", orrery), ("black_hole", black_hole), ("comets", comets),
        ("supernova", supernova), ("saturn", saturn), ("warp", warp), ("constellation", constellation),
    ]),
    ("Nature", [
        ("murmuration", murmuration), ("snow_globe", snow_globe), ("fireworks", fireworks),
        ("snowflake", snowflake), ("slime", slime_mould), ("aurora", aurora), ("fish", fish),
        ("fireflies", fireflies), ("dandelion", dandelion), ("campfire", campfire), ("will_o_wisp", will_o_wisp),
    ]),
    ("Chaos", [
        ("attractor", strange_attractor), ("butterfly", butterfly), ("apple_core", apple_core),
        ("pendulums", pendulums), ("pocket_universe", pocket_universe),
    ]),
    ("Geometry", [
        ("mandala", mandala), ("sunflower", sunflower), ("field_lines", field_lines),
        ("kaleidoscope", kaleidoscope), ("harmonics", harmonics), ("atom", atom), ("heartbeat", heartbeat),
    ]),
    ("Interactive", [
        ("fabric", fabric), ("ink", ink), ("watercolor", watercolor), ("stardust_pen", stardust_pen),
        ("incense", incense), ("ripples", ripples), ("sprites", sprites), ("marbles", marbles),
    ]),
    ("Words", [
        ("clock", stardust_clock), ("poem", poem),
    ]),
]

# keys 1-9 (hotkeys and the first nine of the menu) stay where they were
SLOTS = ["galaxy", "attractor", "mandala", "orrery", "murmuration", "fabric", "ink", "snow_globe", "fireworks"]

BUILTIN = [(k, make) for _, members in GROUPS for k, make in members]
BUILTIN_KEYS = [k for k, _ in BUILTIN]
GROUP_OF = {k: g for g, members in GROUPS for k, _ in members}
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
        """[key, title, group, slot (1-9 or None), editable] for the panel and menus."""
        out = [[k, self.builtin[k].title, GROUP_OF[k], SLOTS.index(k) + 1 if k in SLOTS else None, False]
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
