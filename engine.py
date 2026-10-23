"""
The simulation: forces, swarms and the universe that ties them together.
No windows, keys or panels here (see universe.py for those).
"""

from __future__ import annotations

import math
import time

import numpy as np
import pygame

from config import ABOVE, CENTER, MAX_PAIRS, MOUSE, Field, Layer, Preset

# ------------------------------------------------------------------ sprites
# The original star: a 10x10 soft dot (the old base64 PNG), as an alpha mask.
STAR_COLOR = (253, 236, 166)
SAND_COLOR = (220, 220, 220)
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


def make_dot(diameter: int, color) -> tuple[pygame.Surface, float]:
    """A soft round sprite and the offset to blit it at (x - offset, y - offset)."""
    color = tuple(int(c) for c in color)
    d = max(1, int(diameter))
    if d == 10:
        alpha = np.array([[STAR_ALPHA[c] for c in row] for row in STAR_MASK], dtype=np.uint8).T
        offset = 2.5            # exactly where the old code blitted the star
    else:
        c = (np.arange(d) + 0.5) - d / 2
        dist = np.sqrt(c[:, None] ** 2 + c[None, :] ** 2)
        alpha = (np.clip(d / 2 + 0.5 - dist, 0, 1) * 255).astype(np.uint8)
        offset = d / 2
    surf = pygame.Surface(alpha.shape, pygame.SRCALPHA)
    surf.fill((*color, 0))
    a = pygame.surfarray.pixels_alpha(surf)
    a[:] = alpha
    del a
    return surf, offset


# ------------------------------------------------------------------ forces

def pull(pos: np.ndarray, target, field: Field, scale: float) -> np.ndarray:
    """Acceleration on every body in pos (N x 2) from one source at target."""
    d = np.asarray(target, dtype=float) - pos
    r2 = np.einsum("ij,ij->i", d, d)
    r = np.sqrt(r2)
    g = field.gravity * scale
    law = field.law

    with np.errstate(divide="ignore", invalid="ignore", over="ignore"):
        if law == "oop":
            rr = np.rint(r)                      # = Python round(): half to even
            active = (rr >= field.min_dist) & (rr < field.max_dist) & (r > 0)
            acc = d * np.abs(d) * (g / (r2 * r))[:, None]
        else:
            active = (r >= field.min_dist) & (r < field.max_dist) & (r > 0)
            if law == "ring":
                acc = d * (g / 1000 * (r - field.radius) / r)[:, None]
            else:
                if field.inner_radius > 0:
                    gain = np.where(r < field.inner_radius, field.inner_gain, field.outer_gain)
                else:
                    gain = field.outer_gain
                # g / r^power along d/r; power 1 keeps the exact original g*d/r^2
                k = g * gain / r2 if field.power == 1 else g * gain / r ** (field.power + 1)
                if law == "vortex":
                    acc = np.column_stack([-d[:, 1], d[:, 0]]) * k[:, None]
                else:                            # classic
                    acc = d * k[:, None]

    acc[~active] = 0.0
    return acc


def flow(pos: np.ndarray, cfg, t: float) -> np.ndarray:
    """Curl of a moving stream function: swirls that never pile up."""
    out = np.zeros_like(pos)
    # three cell patterns, each rotated and scaled differently so no grid shows
    for octave, weight, angle, ph in ((1.0, 1.0, 0.0, 0.0), (1.63, 0.6, 1.07, 1.7),
                                      (2.71, 0.35, 2.29, 4.1)):
        c, s = math.cos(angle), math.sin(angle)
        u = c * pos[:, 0] + s * pos[:, 1]
        v = -s * pos[:, 0] + c * pos[:, 1]
        k = 2 * math.pi * octave / max(cfg.scale, 1.0)
        t1 = t * cfg.speed * octave + ph
        t2 = t * cfg.speed * 0.73 * octave - ph
        fu = np.sin(k * u + t1) * np.cos(k * v + t2)      # d(psi)/dv
        fv = -np.cos(k * u + t1) * np.sin(k * v + t2)     # -d(psi)/du
        out[:, 0] += weight * (c * fu - s * fv)
        out[:, 1] += weight * (s * fu + c * fv)
    return out * (cfg.strength / 1.95)


# ------------------------------------------------------------------ pieces

class Sky:
    """The global dark factor: fixed, or fading to black and back every 120 s."""

    def __init__(self, dark):
        self.set(dark)

    def set(self, dark):
        self.mode = dark
        self.value = 1.0 if dark == "cycle" else float(dark)

    def update(self):
        if self.mode == "cycle":
            t = abs(60 - time.time() % 120) / 10
            self.value = 1 - math.exp(-t * t)


class Paint:
    """The slowly drifting colour."""

    def __init__(self, cfg, rng):
        self.rng = rng
        self.cfg = cfg
        self.rgb = rng.integers(cfg.init_min, cfg.init_max, size=3, endpoint=True).astype(float)
        self.dir = rng.choice([-1.0, 1.0], size=3) if cfg.random_start_dir else np.ones(3)

    def change(self):
        c = self.cfg
        ch = self.rng.integers(0, 3)
        self.rgb[ch] += self.dir[ch] * self.rng.integers(c.step_min, max(c.step_min, c.step_max),
                                                         endpoint=True)
        if self.rgb[ch] > c.high:
            self.dir[ch] = -1
        if self.rgb[ch] < c.low:
            self.dir[ch] = 1

    def color(self, dark) -> np.ndarray:
        return np.clip(self.cfg.offset + self.rgb * dark, 0, 255)


class Mouse:
    """The cursor, read once per frame. `read` returns (x, y, left_button_down)."""

    def __init__(self, read):
        self.read = read
        self.pos = np.zeros((1, 2))
        self.pressed = False

    def you_must(self):
        x, y, self.pressed = self.read()
        self.pos[0] = (x, y)


class Swarm:
    """All bodies of one layer, stored as arrays (pos, vel: N x 2)."""

    def __init__(self, layer: Layer, world, rng, mouse: Mouse):
        self.layer = layer
        self.world = world
        self.rng = rng
        self.mouse = mouse
        self.pos = np.zeros((0, 2))
        self.vel = np.zeros((0, 2))
        self.next_teleport = 0
        self._sprites = {}
        self.resize(layer.count)

    def __len__(self):
        return len(self.pos)

    # -- birth (random / center use the original scripts' distributions)
    def spawn(self, n):
        L, rng, (w, h) = self.layer, self.rng, self.world
        if L.spawn == "center":
            pos = np.tile([w / 2, h / 2], (n, 1)).astype(float)
        elif L.spawn == "mouse":
            pos = np.tile(self.mouse.pos[0], (n, 1)).astype(float)
        elif L.spawn == "edges":
            t = rng.random(n) * 2 * (w + h)          # a point along the screen's border
            z = np.zeros(n)
            pos = np.select(
                [(t < w)[:, None], (t < w + h)[:, None], (t < 2 * w + h)[:, None]],
                [np.column_stack([t, z]), np.column_stack([z + w, t - w]),
                 np.column_stack([t - w - h, z + h])],
                np.column_stack([z, t - 2 * w - h]))
        else:
            pos = np.column_stack([rng.integers(0, w, n, endpoint=True),
                                   rng.integers(0, h, n, endpoint=True)]).astype(float)
        if L.velocity == "big_bang":
            s = rng.integers(0, L.big_bang_speed_range * 100, n, endpoint=True)
            vx = rng.integers(-s, s, endpoint=True)
            vy = np.round(np.sqrt(s * s - vx * vx)) * np.where(rng.integers(0, 2, n) == 1, -1, 1)
            vel = np.column_stack([vx, vy]) / 100
        elif L.velocity == "jitter":
            vel = rng.integers(-2, 2, (n, 2), endpoint=True).astype(float)
        elif L.velocity == "drift":
            vel = np.column_stack([rng.integers(-2, 1, n, endpoint=True) + 0.5,
                                   rng.integers(-1, 2, n, endpoint=True) - 0.5])
        else:
            vel = np.zeros((n, 2))
        return pos, vel

    def resize(self, n):
        n = max(0, int(n))
        if n > len(self):
            p, v = self.spawn(n - len(self))
            self.pos = np.vstack([self.pos, p])
            self.vel = np.vstack([self.vel, v])
        elif n < len(self):
            self.pos, self.vel = self.pos[:n].copy(), self.vel[:n].copy()

    # -- the two verbs
    def you_must(self, forces, friction, shape="axis"):
        """Feel every force, then friction (v *= 1 - f v^2, never flipping sign)."""
        for acc in forces:
            self.vel += acc
        if shape == "round":
            v2 = np.einsum("ij,ij->i", self.vel, self.vel)[:, None]
        else:
            v2 = self.vel * self.vel
        self.vel *= np.maximum(0.0, 1.0 - friction * v2)
        if self.layer.max_speed > 0:
            sp = np.sqrt(np.einsum("ij,ij->i", self.vel, self.vel))
            fast = sp > self.layer.max_speed
            self.vel[fast] *= (self.layer.max_speed / sp[fast])[:, None]

    def therefore_you_can(self, edge, bounce=0.8):
        self.pos += self.vel
        size = np.asarray(self.world, dtype=float)
        if edge == "wrap":
            np.mod(self.pos, size, out=self.pos)
        elif edge == "bounce":
            low, high = self.pos < 0, self.pos > size
            self.pos = np.where(low, -self.pos, np.where(high, 2 * size - self.pos, self.pos))
            self.vel[low | high] *= -bounce
            np.clip(self.pos, 0, size - 1e-3, out=self.pos)   # stay on a drawable pixel
        elif edge == "respawn":
            out = ((self.pos < 0) | (self.pos > size)).any(axis=1)
            if out.any():
                p, v = self.spawn(int(out.sum()))
                self.pos[out], self.vel[out] = p, v
        else:   # "legacy": the old abs(x - width) rule
            out = (self.pos < 0) | (self.pos > size)
            self.pos = np.where(out, np.abs(self.pos - size), self.pos)

    def teleport_one(self):
        if len(self):
            self.next_teleport = (self.next_teleport + 1) % len(self)
            w, h = self.world
            self.pos[self.next_teleport] = self.rng.integers(0, (w, h), endpoint=True)

    # -- drawing
    def colors(self, paint: Paint, dark: float):
        """One colour for the whole layer (3,), or one per body (N x 3)."""
        L = self.layer
        if L.color_mode == "palette":
            return paint.color(dark)
        default = STAR_COLOR if L.look == "dot" else SAND_COLOR
        slow = np.asarray(L.color if L.color else default, dtype=float)
        if L.color_mode == "speed":
            t = np.sqrt(np.einsum("ij,ij->i", self.vel, self.vel)) / max(L.speed_ref, 1e-6)
            t = np.clip(t, 0, 1)[:, None]
            return (slow + (np.asarray(L.color2, dtype=float) - slow) * t) * dark
        if L.look == "dot":
            return slow                           # the original star was never dimmed
        return slow * dark

    def _sprite(self, color):
        key = (self.layer.dot, tuple(int(c) for c in color))
        if key not in self._sprites:
            if len(self._sprites) > 64:
                self._sprites.clear()
            self._sprites[key] = make_dot(self.layer.dot, key[1])
        return self._sprites[key]

    def show(self, canvas, paint: Paint, dark: float):
        L = self.layer
        if L.look == "none" or not len(self):
            return
        col = np.clip(self.colors(paint, dark), 0, 255)
        if L.look == "dot":
            if col.ndim == 1:
                sprite, o = self._sprite(col)
                canvas.blits([(sprite, (x - o, y - o)) for x, y in self.pos], doreturn=False)
            else:
                tints = (col // 16 * 16).astype(int)     # a handful of tints, cached
                jobs = []
                for (x, y), c in zip(self.pos, tints):
                    sprite, o = self._sprite(c)
                    jobs.append((sprite, (x - o, y - o)))
                canvas.blits(jobs, doreturn=False)
            return
        # pixel: write straight into the screen buffer
        w, h = self.world
        col = col.astype(np.uint8)
        x = np.floor(self.pos[:, 0]).astype(np.intp)
        y = np.floor(self.pos[:, 1]).astype(np.intp)
        px = pygame.surfarray.pixels3d(canvas)
        sw, sh = (max(1, min(4, int(v))) for v in L.size)
        for dx in range(sw):
            for dy in range(sh):
                xx, yy = x + dx, y + dy
                ok = (xx >= 0) & (xx < w) & (yy >= 0) & (yy < h)
                px[xx[ok], yy[ok]] = col if col.ndim == 1 else col[ok]
        del px


# ------------------------------------------------------------------ the universe

class Universe:
    def __init__(self, preset: Preset, screen: pygame.Surface, mouse: Mouse, seed=None):
        self.screen = screen
        self.world = screen.get_size()      # read once, not per particle per frame
        self.center = np.array([[self.world[0] / 2, self.world[1] / 2]], dtype=float)
        self.rng = np.random.default_rng(seed)
        self.mouse = mouse
        self.p = preset
        self.sky = Sky(preset.dark)
        self.paint = Paint(preset.palette, self.rng)
        self.swarms: list[Swarm] = []
        self.frame = 0
        self.t0 = time.time()
        self.mouse.you_must()               # so "spawn at mouse" works from the start
        self.reconfigure(preset)
        screen.fill((0, 0, 0))

    def reconfigure(self, preset: Preset):
        """Swap in new settings without a restart: bodies keep moving where they are.
        Layers are matched by name, so reordering or renaming in the panel is safe."""
        self.p = preset
        new_names = {l.name for l in preset.layers}
        old = {s.layer.name: s for s in self.swarms}
        swarms = []
        for i, layer in enumerate(preset.layers):
            s = old.pop(layer.name, None)
            if s is None and i < len(self.swarms):
                prev = self.swarms[i]
                if prev.layer.name not in new_names and old.get(prev.layer.name) is prev:
                    s = old.pop(prev.layer.name)     # renamed in place: keep its bodies
            if s is None:
                s = Swarm(layer, self.world, self.rng, self.mouse)
            else:
                s.layer = layer
                s.resize(layer.count)
            swarms.append(s)
        self.swarms = swarms
        if preset.dark != self.sky.mode:
            self.sky.set(preset.dark)
        self.paint.cfg = preset.palette

    def swarm(self, name):
        return next(s for s in self.swarms if s.layer.name == name)

    def counts(self):
        return {s.layer.name: len(s) for s in self.swarms}

    def step(self):
        p = self.p
        self.sky.update()
        dark = self.sky.value
        self.paint.change()
        self.mouse.you_must()
        mouse_sign = -1.0 if (p.click_invert and self.mouse.pressed) else 1.0
        t = time.time() - self.t0
        wind = np.asarray(p.wind, dtype=float)

        for i, swarm in enumerate(self.swarms):
            layer = swarm.layer
            if not len(swarm) or layer.motion == "fixed":
                continue
            if layer.motion == "teleport":
                if self.frame % max(1, layer.teleport_every) == 0:
                    swarm.teleport_one()
                continue

            forces = []
            for pl in layer.pulls:
                if not pl.enabled:
                    continue
                source = pl.source
                if source == ABOVE and i == 0:
                    source = MOUSE                   # the top layer's "above" is the mouse
                if source == MOUSE:
                    srcs, scale = self.mouse.pos, dark * mouse_sign
                elif source == CENTER:
                    srcs, scale = self.center, dark
                else:
                    srcs, scale = self.swarms[i - 1].pos, dark
                    if len(srcs) * len(swarm) > MAX_PAIRS:
                        continue                     # would freeze the frame (see problems())
                forces += [pull(swarm.pos, s, pl.field, scale) for s in srcs]
            if p.flow.enabled and layer.flow:
                forces.append(flow(swarm.pos, p.flow, t) * layer.flow)
            if layer.wind and wind.any():
                forces.append(wind * layer.wind)
            if layer.jitter:
                swarm.vel += self.rng.normal(0.0, layer.jitter, swarm.vel.shape)
            if layer.motion == "random_walk":
                swarm.vel += self.rng.integers(-1, 1, swarm.vel.shape, endpoint=True)

            friction = layer.friction if layer.friction is not None else p.friction
            if p.dark_scales_friction:
                friction *= dark
            swarm.you_must(forces, friction, p.friction_shape)
            swarm.therefore_you_can(p.edge, p.bounce)
        self.frame += 1

    def fade(self):
        t = self.p.trail
        if t <= 0:
            self.screen.fill((0, 0, 0))
        elif t < 1:
            # a translucent black sheet over the last frame (SDL's fast alpha blit),
            # then minus one so the faintest pixels really reach black
            if getattr(self, "_veil", None) is None:
                self._veil = pygame.Surface(self.world)
                self._one = pygame.Surface(self.world)
                self._one.fill((1, 1, 1))
                try:
                    self._veil, self._one = self._veil.convert(), self._one.convert()
                except pygame.error:            # no display (tests): unconverted is fine
                    pass
            self._veil.set_alpha(int(round(255 * (1 - t))))
            self.screen.blit(self._veil, (0, 0))
            self.screen.blit(self._one, (0, 0), special_flags=pygame.BLEND_SUB)

    def draw(self):
        self.fade()
        for swarm in self.swarms:                    # lower layers paint over upper ones
            swarm.show(self.screen, self.paint, self.sky.value)
