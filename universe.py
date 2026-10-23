"""
DesktopUniverse — OOP + NumPy rewrite.

    python universe.py                 # default preset (随波逐流)
    python universe.py waves           # pick a preset by key
    python universe.py --list          # show all presets
    python universe.py --fps 30        # frame cap (0 = uncapped)

Controls
    Esc / Q        quit
    1-7, ← →       switch preset
    R              restart current preset
    C              clear the screen (handy in trail presets)
    Space          pause
    F              show / hide info (preset, fps)
    [  ]           lower / raise the frame cap

All tunable numbers live in presets.py.
"""

import argparse
import math
import os
import sys
import time

import numpy as np
import pygame

from presets import DEFAULT, PRESETS, Field, Preset


# ------------------------------------------------------------------ sprites
# The star is the same 10x10 soft dot as the old base64 PNG, written as an
# alpha mask so nothing has to be decoded or saved to disk.
STAR_COLOR = (253, 236, 166)
STAR_MASK = [
    "..13##21..",
    ".########.",
    "1########1",
    "2########3",
    "##########",
    "##########",
    "3########2",
    "1########1",
    ".########.",
    "..12##31..",
]
STAR_ALPHA = {".": 0, "1": 0x55, "2": 0xAA, "3": 0xC6, "#": 0xFF}
STAR_OFFSET = 2.5   # old code blitted at (x - 2.5, y - 2.5)


def make_star_sprite() -> pygame.Surface:
    h, w = len(STAR_MASK), len(STAR_MASK[0])
    surf = pygame.Surface((w, h), pygame.SRCALPHA)
    surf.fill((*STAR_COLOR, 0))
    alpha = pygame.surfarray.pixels_alpha(surf)
    for y, row in enumerate(STAR_MASK):
        for x, ch in enumerate(row):
            alpha[x, y] = STAR_ALPHA[ch]
    del alpha   # release the surface lock
    return surf


# ------------------------------------------------------------------ physics

def pull(pos: np.ndarray, target, field: Field, dark: float) -> np.ndarray:
    """Acceleration on every body in `pos` (N x 2) from one attractor at `target`."""
    d = np.asarray(target, dtype=float) - pos
    r2 = np.einsum("ij,ij->i", d, d)
    r = np.sqrt(r2)
    g = field.gravity * dark

    with np.errstate(divide="ignore", invalid="ignore"):
        if field.law == "classic":
            active = (r >= field.min_dist) & (r > 0)
            if field.inner_radius > 0:
                gain = np.where(r < field.inner_radius, field.inner_gain, field.outer_gain)
            else:
                gain = field.outer_gain
            acc = d * (g * gain / r2)[:, None]
        elif field.law == "oop":
            rr = np.rint(r)                     # Python's round(): same half-to-even rule
            active = (rr >= field.min_dist) & (rr < field.max_dist) & (r > 0)
            acc = d * np.abs(d) * (g / (r2 * r))[:, None]
        else:
            raise ValueError(f"unknown law {field.law!r}")

    acc[~active] = 0.0
    return acc


class Sky:
    """The global 'dark' factor: a constant, or a 120 s fade in and out."""

    def __init__(self, dark):
        self.mode = dark
        self.value = 1.0 if dark == "cycle" else float(dark)

    def update(self):
        if self.mode == "cycle":
            t = abs(60 - time.time() % 120) / 10
            self.value = 1 - math.exp(-t * t)


class Paint:
    """Slowly drifting sand colour."""

    def __init__(self, cfg, rng):
        self.cfg, self.rng = cfg, rng
        self.rgb = rng.integers(cfg.init_min, cfg.init_max, size=3, endpoint=True).astype(float)
        self.dir = rng.choice([-1, 1], size=3) if cfg.random_start_dir else np.ones(3)

    def change(self):
        c = self.cfg
        ch = self.rng.integers(0, 3)
        self.rgb[ch] += self.dir[ch] * self.rng.integers(c.step_min, c.step_max, endpoint=True)
        if self.rgb[ch] > c.high:
            self.dir[ch] = -1
        if self.rgb[ch] < c.low:
            self.dir[ch] = 1

    def color(self, dark) -> np.ndarray:
        return np.clip(self.cfg.offset + self.rgb * dark, 0, 255).astype(np.uint8)


class Absolute:
    """The mouse. Read once per frame."""

    def __init__(self, global_mouse=False):
        self.x = self.y = 0.0
        self._pos = pygame.mouse.get_pos
        if global_mouse:
            import pyautogui            # optional: tracks the cursor even when unfocused
            self._pos = pyautogui.position

    def you_must(self):
        self.x, self.y = self._pos()

    @property
    def xy(self):
        return (self.x, self.y)


class Bodies:
    """A swarm of identical bodies stored as arrays (pos, vel: N x 2)."""

    def __init__(self, pos, vel, world):
        self.pos = pos.astype(float)
        self.vel = vel.astype(float)
        self.world = world                     # (width, height), cached once

    def __len__(self):
        return len(self.pos)

    def you_must(self, forces, friction):
        """Feel every force, then friction (v *= 1 - f v^2, never flipping sign)."""
        for acc in forces:
            self.vel += acc
        self.vel *= np.maximum(0.0, 1.0 - friction * self.vel * self.vel)

    def therefore_you_can(self, edge):
        """Move, then handle the screen edge."""
        self.pos += self.vel
        size = np.asarray(self.world, dtype=float)
        if edge == "wrap":
            np.mod(self.pos, size, out=self.pos)
        else:   # "legacy": the old abs(x - width) rule
            out = (self.pos < 0) | (self.pos > size)
            self.pos = np.where(out, np.abs(self.pos - size), self.pos)


class Sand(Bodies):
    def show(self, canvas: pygame.Surface, color: np.ndarray):
        """Write every grain straight into the screen buffer (2 x 1 px, like the old sprite)."""
        w, h = self.world
        x = np.floor(self.pos[:, 0]).astype(np.intp)
        y = np.floor(self.pos[:, 1]).astype(np.intp)
        ok = (x >= 0) & (x < w) & (y >= 0) & (y < h)
        x, y = x[ok], y[ok]
        px = pygame.surfarray.pixels3d(canvas)
        px[x, y] = color
        right = x + 1 < w
        px[x[right] + 1, y[right]] = color
        del px


class Stars(Bodies):
    def __init__(self, pos, vel, world, sprite):
        super().__init__(pos, vel, world)
        self.sprite = sprite
        self.next_teleport = 0

    def teleport_one(self, rng):
        if len(self):
            self.next_teleport = (self.next_teleport + 1) % len(self)
            w, h = self.world
            self.pos[self.next_teleport] = rng.integers(0, (w, h), endpoint=True)

    def show(self, canvas: pygame.Surface):
        canvas.blits([(self.sprite, (x - STAR_OFFSET, y - STAR_OFFSET)) for x, y in self.pos],
                     doreturn=False)


# ------------------------------------------------------------------ the world

class Universe:
    def __init__(self, preset: Preset, screen: pygame.Surface, star_sprite, global_mouse=False, seed=None):
        self.p = preset
        self.screen = screen
        self.world = screen.get_size()          # "cache at the start": read the size once
        self.rng = np.random.default_rng(seed)
        self.sky = Sky(preset.dark)
        self.paint = Paint(preset.palette, self.rng)
        self.absolute = Absolute(global_mouse)
        self.frame = 0
        self.sand = Sand(*self._sand_start(), self.world)
        self.stars = Stars(*self._star_start(), self.world, star_sprite)
        screen.fill((0, 0, 0))

    # -- initial conditions (same distributions as the old scripts)
    def _sand_start(self):
        p, rng, (w, h) = self.p, self.rng, self.world
        n = p.sand_num
        if p.sand_spawn == "center":
            pos = np.tile([w / 2, h / 2], (n, 1))
        else:
            pos = np.column_stack([rng.integers(0, w, n, endpoint=True),
                                   rng.integers(0, h, n, endpoint=True)])
        if p.sand_velocity == "big_bang":
            s = rng.integers(0, p.big_bang_speed_range * 100, n, endpoint=True)
            vx = rng.integers(-s, s, endpoint=True)
            vy = np.round(np.sqrt(s * s - vx * vx))
            vy *= np.where(rng.integers(0, 2, n) == 1, -1, 1)
            vel = np.column_stack([vx, vy]) / 100
        else:   # "jitter"
            vel = rng.integers(-2, 2, (n, 2), endpoint=True)
        return pos, vel

    def _star_start(self):
        p, rng, (w, h) = self.p, self.rng, self.world
        n = p.star_num
        pos = np.column_stack([rng.integers(0, w, n, endpoint=True),
                               rng.integers(0, h, n, endpoint=True)])
        if p.star_velocity == "drift":
            vel = np.column_stack([rng.integers(-2, 1, n, endpoint=True) + 0.5,
                                   rng.integers(-1, 2, n, endpoint=True) - 0.5])
        else:
            vel = np.zeros((n, 2))
        return pos, vel

    # -- one frame
    def step(self):
        p = self.p
        self.sky.update()
        dark = self.sky.value
        friction = p.friction * (dark if p.dark_scales_friction else 1.0)
        self.paint.change()
        self.absolute.you_must()

        # stars move first, so sand feels where they are *this* frame (as before)
        if len(self.stars):
            if p.star_motion == "orbit":
                forces = [pull(self.stars.pos, self.absolute.xy, p.mouse, dark)] if p.mouse else []
                self.stars.you_must(forces, friction)
                self.stars.therefore_you_can(p.edge)
            elif p.star_motion == "random_walk":
                self.stars.vel += self.rng.integers(-1, 1, self.stars.vel.shape, endpoint=True)
                self.stars.you_must([], friction)
                self.stars.therefore_you_can(p.edge)
            elif p.star_motion == "teleport":
                if self.frame % p.teleport_every == 0:
                    self.stars.teleport_one(self.rng)

        forces = []
        if p.mouse:
            forces.append(pull(self.sand.pos, self.absolute.xy, p.mouse, dark))
        if p.star:
            forces += [pull(self.sand.pos, s, p.star, dark) for s in self.stars.pos]
        self.sand.you_must(forces, friction)
        self.sand.therefore_you_can(p.edge)
        self.frame += 1

    def draw(self):
        if not self.p.trails:
            self.screen.fill((0, 0, 0))
        if self.p.draw_stars and len(self.stars):
            self.stars.show(self.screen)        # sand is painted over stars, as before
        self.sand.show(self.screen, self.paint.color(self.sky.value))


# ------------------------------------------------------------------ app shell

class App:
    def __init__(self, preset_key, fps, global_mouse, windowed=None):
        os.environ.setdefault("SDL_VIDEO_CENTERED", "1")
        pygame.init()
        if windowed:
            self.screen = pygame.display.set_mode(windowed)
        else:
            self.screen = pygame.display.set_mode((0, 0), pygame.NOFRAME)
        pygame.display.set_caption("DesktopUniverse")
        self.keys = list(PRESETS)
        self.index = self.keys.index(preset_key)
        self.fps = fps
        self.global_mouse = global_mouse
        self.sprite = make_star_sprite()
        # a font that can draw the Chinese preset names; falls back to pygame's default
        self.font = pygame.font.SysFont(
            "microsoftyaheiui,microsoftyahei,pingfangsc,hiraginosansgb,"
            "notosanscjksc,notosanscjk,wenquanyimicrohei,simhei", 20)
        self.clock = pygame.time.Clock()
        self.paused = False
        self.show_info = False
        self.banner_until = 0.0
        self.load()

    def load(self):
        self.universe = Universe(PRESETS[self.keys[self.index]], self.screen,
                                 self.sprite, self.global_mouse)
        self.banner_until = time.time() + 2.0

    def switch(self, i):
        self.index = i % len(self.keys)
        self.load()

    def handle(self, e):
        if e.type == pygame.QUIT:
            return False
        if e.type != pygame.KEYDOWN:
            return True
        k = e.key
        if k in (pygame.K_ESCAPE, pygame.K_q):
            return False
        if pygame.K_1 <= k <= pygame.K_9 and k - pygame.K_1 < len(self.keys):
            self.switch(k - pygame.K_1)
        elif k == pygame.K_RIGHT:
            self.switch(self.index + 1)
        elif k == pygame.K_LEFT:
            self.switch(self.index - 1)
        elif k == pygame.K_r:
            self.load()
        elif k == pygame.K_c:
            self.screen.fill((0, 0, 0))
        elif k == pygame.K_SPACE:
            self.paused = not self.paused
        elif k == pygame.K_f:
            self.show_info = not self.show_info
        elif k == pygame.K_RIGHTBRACKET:
            self.fps = min(240, self.fps + 10) if self.fps else 0
        elif k == pygame.K_LEFTBRACKET:
            self.fps = max(10, self.fps - 10) if self.fps else 60
        return True

    def overlay_text(self):
        lines = []
        if time.time() < self.banner_until or self.show_info:
            lines.append(f"{self.index + 1}. {self.universe.p.title}")
        if self.show_info:
            cap = self.fps or "off"
            lines.append(f"fps {self.clock.get_fps():.0f}  (cap {cap})   "
                         f"sand {len(self.universe.sand)}  stars {len(self.universe.stars)}")
            if self.paused:
                lines.append("paused")
        return lines

    def present(self):
        """Show the overlay without burning it into trail presets."""
        lines = self.overlay_text()
        if not lines:
            pygame.display.flip()
            return
        surfs = [self.font.render(t, True, (200, 200, 200)) for t in lines]
        rect = pygame.Rect(12, 12, max(s.get_width() for s in surfs) + 8, 22 * len(surfs) + 4)
        rect = rect.clip(self.screen.get_rect())
        backup = self.screen.subsurface(rect).copy()
        for i, s in enumerate(surfs):
            self.screen.blit(s, (16, 14 + 22 * i))
        pygame.display.flip()
        self.screen.blit(backup, rect)

    def run(self):
        running = True
        while running:
            for e in pygame.event.get():
                running = self.handle(e) and running
            if not self.paused:
                self.universe.step()
                self.universe.draw()
            self.present()
            self.clock.tick(self.fps)
        pygame.quit()


def main():
    ap = argparse.ArgumentParser(description="DesktopUniverse particle playground")
    ap.add_argument("preset", nargs="?", default=DEFAULT, help="preset key (see --list)")
    ap.add_argument("--list", action="store_true", help="list presets and exit")
    ap.add_argument("--fps", type=int, default=60, help="frame cap, 0 = uncapped (default 60)")
    ap.add_argument("--global-mouse", action="store_true",
                    help="track the cursor with pyautogui even when the window is not focused")
    ap.add_argument("--window", metavar="WxH", help="run in a normal window, e.g. 1280x720")
    args = ap.parse_args()

    if args.list:
        for i, (k, p) in enumerate(PRESETS.items(), 1):
            print(f"{i}. {k:18s} {p.title}  ({p.sand_num} sand, {p.star_num} stars)")
        return
    if args.preset not in PRESETS:
        sys.exit(f"unknown preset {args.preset!r}; try --list")
    windowed = tuple(map(int, args.window.lower().split("x"))) if args.window else None
    App(args.preset, args.fps, args.global_mouse, windowed).run()


if __name__ == "__main__":
    main()
