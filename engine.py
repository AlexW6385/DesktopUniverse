"""
The simulation: forces, neighbourhoods, swarms, and the universe that ties
them together and paints them. No windows, keys or panels in here.

Everything is vectorised with NumPy: a swarm is two N x 2 arrays (pos, vel)
and every rule is applied to the whole array at once.
"""

from __future__ import annotations

import math

import numpy as np
import pygame

from config import ABOVE, CENTER, MAX_PAIRS, MOUSE, Field, Layer, Preset

TAU = 2 * math.pi
FPS = 60.0           # simulated time advances 1/60 s per step, so pausing never jumps


# ------------------------------------------------------------------ colour

def hsv(h, s, v) -> np.ndarray:
    """Vectorised HSV -> RGB 0..255. h in degrees; any argument may be an array."""
    h, s, v = np.broadcast_arrays(np.asarray(h, float), np.asarray(s, float), np.asarray(v, float))
    h6 = (h % 360.0) / 60.0
    i = np.floor(h6).astype(int) % 6
    f = h6 - np.floor(h6)
    p, q, t = v * (1 - s), v * (1 - s * f), v * (1 - s * (1 - f))
    r = np.choose(i, [v, q, p, p, t, v])
    g = np.choose(i, [t, v, v, q, p, p])
    b = np.choose(i, [p, p, t, v, v, q])
    return np.stack([r, g, b], axis=-1) * 255.0


_LUTS: dict = {}


def hue_colors(h, s, v) -> np.ndarray:
    """Fast HSV for many hues at one saturation / value: a 360-step lookup table."""
    key = (round(float(s), 3), round(float(v), 3))
    lut = _LUTS.get(key)
    if lut is None:
        if len(_LUTS) > 32:
            _LUTS.clear()
        lut = _LUTS[key] = hsv(np.arange(360.0), s, v).astype(np.float32)
    return lut[np.asarray(h).astype(np.int64) % 360]


def make_dot(diameter: int, color, additive: bool) -> tuple[pygame.Surface, float]:
    """A soft round sprite. Additive sprites are premultiplied RGB for BLEND_RGB_ADD."""
    d = max(1, int(diameter))
    c = (np.arange(d) + 0.5) - d / 2
    dist = np.sqrt(c[:, None] ** 2 + c[None, :] ** 2)
    alpha = np.clip(d / 2 + 0.5 - dist, 0, 1)
    col = np.clip(np.asarray(color, float), 0, 255)
    if additive:
        surf = pygame.Surface((d, d))
        px = pygame.surfarray.pixels3d(surf)
        px[:] = (alpha[:, :, None] * col).astype(np.uint8)
        del px
    else:
        surf = pygame.Surface((d, d), pygame.SRCALPHA)
        surf.fill((*col.astype(int), 0))
        a = pygame.surfarray.pixels_alpha(surf)
        a[:] = (alpha * 255).astype(np.uint8)
        del a
    return surf, d / 2


# ------------------------------------------------------------------ forces

def pull(pos, vel, src, src_vel, f: Field, scale: float, ring_radius=None) -> np.ndarray:
    """Acceleration on every body (N x 2) from one source body."""
    if ring_radius is None:
        ring_radius = f.radius
    d = np.asarray(src, float) - pos
    r2 = np.einsum("ij,ij->i", d, d)
    r = np.sqrt(r2)
    active = (r >= f.min_dist) & (r < f.max_dist) & (r > 0)
    g = f.strength * scale
    with np.errstate(divide="ignore", invalid="ignore", over="ignore"):
        if f.law in ("drag", "wake"):
            w = np.clip(1 - r / f.max_dist, 0, 1) if math.isfinite(f.max_dist) else np.ones_like(r)
            sv = np.asarray(src_vel, float)
            acc = ((sv - vel) if f.law == "drag" else np.broadcast_to(sv, vel.shape)) * (g / 100 * w)[:, None]
        elif f.law == "ring":
            acc = d * (g / 1000 * (r - ring_radius) / r)[:, None]
        else:
            gain = (np.where(r < f.inner_radius, f.inner_gain, f.outer_gain)
                    if f.inner_radius > 0 else f.outer_gain)
            k = g * gain / r2 if f.power == 1 else g * gain / r ** (f.power + 1)
            if f.law == "vortex":
                acc = np.column_stack([-d[:, 1], d[:, 0]]) * k[:, None]
            else:
                acc = d * k[:, None]
    acc[~active] = 0.0
    return acc


def pulse_factor(f: Field, t: float) -> float:
    if not f.pulse:
        return 1.0
    return 1.0 + f.pulse * math.sin(TAU * (t / max(f.period, 1e-3) + f.phase))


def flow(pos, cfg, t) -> np.ndarray:
    """Curl of a moving stream function: swirls that never pile up."""
    p32 = pos.astype(np.float32)
    out = np.zeros_like(p32)
    for octave, weight, angle, ph in ((1.0, 1.0, 0.31, 0.0), (1.37, 0.85, 1.29, 1.7),
                                      (2.11, 0.6, 2.47, 4.1), (3.3, 0.35, 0.83, 2.6)):
        c, s = math.cos(angle), math.sin(angle)
        k = TAU * octave / max(cfg.scale, 1.0)
        a = (k * c) * p32[:, 0] + (k * s) * p32[:, 1] + np.float32(t * cfg.speed * octave + ph)
        b = (-k * s) * p32[:, 0] + (k * c) * p32[:, 1] + np.float32(t * cfg.speed * 0.73 * octave - ph)
        sa, ca, sb, cb = np.sin(a), np.cos(a), np.sin(b), np.cos(b)
        fu = sa * cb
        fv = -ca * sb
        out[:, 0] += weight * (c * fu - s * fv)
        out[:, 1] += weight * (s * fu + c * fv)
    return out.astype(np.float64) * (cfg.strength / 2.8)


def attractor_map(pos, cfg, t, world, center) -> np.ndarray:
    """Where each body lands after one step of the (slowly morphing) map."""
    ph = TAU * t * cfg.morph_speed
    m = cfg.morph
    a = cfg.a + m * math.sin(ph)
    b = cfg.b + m * math.sin(1.31 * ph + 1.0)
    c = cfg.c + m * math.sin(0.77 * ph + 2.0)
    d = cfg.d + m * math.sin(1.13 * ph + 3.0)
    R = cfg.scale * min(world) / 2
    cx, cy = center
    if cfg.kind == "dejong":
        ex = ey = 2.0
    else:
        ex, ey = 1 + abs(c), 1 + abs(d)
    u = (pos[:, 0] - cx) / R * ex
    v = (pos[:, 1] - cy) / R * ey
    if cfg.kind == "dejong":
        u2 = np.sin(a * v) - np.cos(b * u)
        v2 = np.sin(c * u) - np.cos(d * v)
    else:
        u2 = np.sin(a * v) + c * np.cos(a * u)
        v2 = np.sin(b * u) + d * np.cos(b * v)
    return np.column_stack([cx + u2 / ex * R, cy + v2 / ey * R])


# ------------------------------------------------------------------ neighbourhoods

def _blur(g):
    p = np.pad(g, 1, mode="edge")
    return (p[:-2, :-2] + p[:-2, 1:-1] + p[:-2, 2:] + p[1:-1, :-2] + p[1:-1, 1:-1]
            + p[1:-1, 2:] + p[2:, :-2] + p[2:, 1:-1] + p[2:, 2:]) / 9.0


def _bilinear(grid, fx, fy):
    gh, gw = grid.shape
    x0 = np.floor(fx).astype(int)
    y0 = np.floor(fy).astype(int)
    tx, ty = fx - x0, fy - y0
    x0c, x1c = np.clip(x0, 0, gw - 1), np.clip(x0 + 1, 0, gw - 1)
    y0c, y1c = np.clip(y0, 0, gh - 1), np.clip(y0 + 1, 0, gh - 1)
    return ((grid[y0c, x0c] * (1 - tx) + grid[y0c, x1c] * tx) * (1 - ty)
            + (grid[y1c, x0c] * (1 - tx) + grid[y1c, x1c] * tx) * ty)


def neighbourhood(pos, vel, world, cell, pressure, align) -> np.ndarray:
    """Pressure and alignment from a density grid: O(N), no pairwise distances.

    pressure: -gradient of the (smoothed, normalised) density, so bodies flow
              from crowded to empty; negative pressure makes them clump.
    align:    steer toward the mean velocity of the bodies in the same cell.
    """
    W, H = world
    cell = max(2, int(cell))
    gw, gh = max(1, math.ceil(W / cell)), max(1, math.ceil(H / cell))
    cx = np.clip((pos[:, 0] // cell).astype(int), 0, gw - 1)
    cy = np.clip((pos[:, 1] // cell).astype(int), 0, gh - 1)
    idx = cy * gw + cx
    cnt = np.bincount(idx, minlength=gw * gh).astype(float)
    acc = np.zeros_like(pos)
    if pressure:
        # log density: a cell holding the whole swarm must not launch it into orbit
        dens = _blur(np.log1p(cnt / max(cnt.mean(), 1e-9)).reshape(gh, gw))
        gy, gx = np.gradient(dens)
        fx, fy = pos[:, 0] / cell - 0.5, pos[:, 1] / cell - 0.5
        acc[:, 0] -= pressure * _bilinear(gx, fx, fy)
        acc[:, 1] -= pressure * _bilinear(gy, fx, fy)
        np.clip(acc, -3.0, 3.0, out=acc)
    if align:
        n = np.maximum(cnt, 1)
        mx = np.bincount(idx, vel[:, 0], minlength=gw * gh) / n
        my = np.bincount(idx, vel[:, 1], minlength=gw * gh) / n
        acc[:, 0] += align * (mx[idx] - vel[:, 0])
        acc[:, 1] += align * (my[idx] - vel[:, 1])
    return acc


# ------------------------------------------------------------------ the cursor

class Mouse:
    """Read once per frame. `read` returns (x, y, left_button_down)."""

    def __init__(self, read):
        self.read = read
        self.pos = np.zeros((1, 2))
        self.vel = np.zeros((1, 2))
        self.pressed = False
        self._first = True

    def update(self):
        x, y, self.pressed = self.read()
        new = np.array([[x, y]], float)
        if self._first:
            self.pos[:], self._first = new, False
        self.vel = 0.5 * self.vel + 0.5 * (new - self.pos)     # smoothed, px / frame
        self.pos = new


# ------------------------------------------------------------------ swarms

class Swarm:
    """All bodies of one layer."""

    def __init__(self, layer: Layer, uni: "Universe"):
        self.layer = layer
        self.uni = uni
        self.rng = uni.rng
        self.pos = np.zeros((0, 2))
        self.vel = np.zeros((0, 2))
        self.home = np.zeros((0, 2))
        self.age = np.zeros(0)
        self.life = np.zeros(0)
        self.hue_seed = np.zeros(0)
        self.seed2 = np.zeros(0)                 # a second per-body random number (variety)
        self._sprites = {}
        self.resize(layer.count, fresh=True)
        if layer.motion == "path":                 # start on the curve, so children are born around it
            self.follow_path(uni.t)
            self.vel[:] = 0

    def __len__(self):
        return len(self.pos)

    # -- birth
    def _parents(self, n):
        """Reference point and velocity each newborn is born relative to."""
        u, L = self.uni, self.layer
        if L.spawn in ("above", "above_ring"):
            src, svel = u.source_arrays(self, ABOVE)
            if len(src):
                k = self.rng.integers(0, len(src), n)
                return src[k], svel[k]
        if L.spawn == "mouse":
            return np.repeat(u.mouse.pos, n, 0), np.repeat(u.mouse.vel, n, 0)
        return np.repeat(u.center, n, 0), np.zeros((n, 2))

    def spawn(self, n, fresh=False):
        L, rng = self.layer, self.rng
        W, H = self.uni.world
        ref, ref_vel = self._parents(n)
        if L.spawn in ("center", "mouse", "above"):
            pos = ref.copy()
        elif L.spawn == "edges":
            t = rng.random(n) * 2 * (W + H)
            z = np.zeros(n)
            pos = np.select([(t < W)[:, None], (t < W + H)[:, None], (t < 2 * W + H)[:, None]],
                            [np.column_stack([t, z]), np.column_stack([z + W, t - W]),
                             np.column_stack([t - W - H, z + H])],
                            np.column_stack([z, t - 2 * W - H]))
        elif L.spawn == "grid":
            total = max(L.count, n)
            cols = max(1, round(math.sqrt(total * W / H)))
            rows = math.ceil(total / cols)
            gx, gy = np.meshgrid((np.arange(cols) + 0.5) * W / cols, (np.arange(rows) + 0.5) * H / rows)
            lattice = np.column_stack([gx.ravel(), gy.ravel()])[:total]
            pos = lattice[:n].copy() if fresh else lattice[rng.integers(0, len(lattice), n)]
        elif L.spawn in ("circle", "above_ring"):
            a = rng.random(n) * TAU
            r = L.spawn_radius + rng.normal(0, 2, n)
            pos = ref + np.column_stack([np.cos(a), np.sin(a)]) * r[:, None]
        else:
            pos = rng.random((n, 2)) * [W, H]

        # initial velocity
        rel = pos - ref
        dist = np.sqrt(np.einsum("ij,ij->i", rel, rel))
        rnd = rng.random(n) * TAU
        unit = np.where((dist > 1e-6)[:, None], rel / np.maximum(dist, 1e-6)[:, None],
                        np.column_stack([np.cos(rnd), np.sin(rnd)]))
        s = L.start_speed
        if L.velocity == "zero":
            vel = np.zeros((n, 2))
        elif L.velocity == "orbit":
            vel = np.column_stack([-unit[:, 1], unit[:, 0]]) * s + ref_vel
        elif L.velocity == "outward":
            vel = unit * (s * (0.3 + 0.7 * rng.random(n)))[:, None] + ref_vel
        else:
            a = rng.random(n) * TAU
            m = s * np.sqrt(rng.random(n))
            vel = np.column_stack([np.cos(a), np.sin(a)]) * m[:, None]
            if L.velocity == "inherit":
                vel += ref_vel
        return pos.astype(float), vel.astype(float)

    def _lives(self, n):
        L = self.layer
        if L.life <= 0:
            return np.full(n, np.inf)
        j = L.life_jitter * (2 * self.rng.random(n) - 1)
        return np.maximum(1.0, L.life * (1 + j))

    def resize(self, n, fresh=False):
        n = max(0, int(n))
        if n > len(self):
            k = n - len(self)
            p, v = self.spawn(k, fresh=fresh and len(self) == 0)
            life = self._lives(k)
            age = np.zeros(k)
            if self.layer.life > 0 and self.layer.life_jitter > 0:
                age = self.rng.random(k) * life     # staggered, unless lives are meant to sync
            self.pos = np.vstack([self.pos, p])
            self.vel = np.vstack([self.vel, v])
            self.home = np.vstack([self.home, p])
            self.age = np.concatenate([self.age, age])
            self.life = np.concatenate([self.life, life])
            self.hue_seed = np.concatenate([self.hue_seed, self.rng.random(k)])
            self.seed2 = np.concatenate([self.seed2, self.rng.random(k)])
        elif n < len(self):
            for name in ("pos", "vel", "home", "age", "life", "hue_seed", "seed2"):
                setattr(self, name, getattr(self, name)[:n].copy())

    def reborn(self, mask):
        k = int(mask.sum())
        if not k:
            return
        p, v = self.spawn(k)
        self.pos[mask], self.vel[mask], self.home[mask] = p, v, p
        self.age[mask] = 0
        self.life[mask] = self._lives(k)

    def relife(self):
        """Lifetime settings changed in the panel."""
        if self.layer.life <= 0:
            self.life[:] = np.inf
        elif not np.isfinite(self.life).all() or abs(np.median(self.life) - self.layer.life) > 0.5:
            self.life = self._lives(len(self))
            self.age = np.minimum(self.age, self.life - 1)

    # -- motion
    def you_must(self, forces, friction, shape):
        """Feel every force, then friction (v *= 1 - f v^2, never flipping sign)."""
        for acc in forces:
            self.vel += acc
        if shape == "axis":
            v2 = self.vel * self.vel
        else:
            v2 = np.einsum("ij,ij->i", self.vel, self.vel)[:, None]
        self.vel *= np.maximum(0.0, 1.0 - friction * v2)
        L = self.layer
        if L.max_speed > 0 or L.min_speed > 0:
            sp = np.sqrt(np.einsum("ij,ij->i", self.vel, self.vel))
            lo, hi = L.min_speed, L.max_speed if L.max_speed > 0 else np.inf
            target = np.clip(sp, lo, hi)
            moving = sp > 1e-9
            self.vel[moving] *= (target[moving] / sp[moving])[:, None]
            if lo > 0 and (~moving).any():               # a body at rest picks a direction
                a = self.rng.random(int((~moving).sum())) * TAU
                self.vel[~moving] = np.column_stack([np.cos(a), np.sin(a)]) * lo

    def therefore_you_can(self, edge, bounce):
        self.pos += self.vel
        size = np.asarray(self.uni.world, float)
        if edge == "bounce":
            low, high = self.pos < 0, self.pos > size
            self.pos = np.where(low, -self.pos, np.where(high, 2 * size - self.pos, self.pos))
            self.vel[low | high] *= -bounce
            np.clip(self.pos, 0, size - 1e-3, out=self.pos)
        elif edge == "respawn":
            out = ((self.pos < 0) | (self.pos > size)).any(axis=1)
            self.reborn(out)
        else:
            np.mod(self.pos, size, out=self.pos)

    def follow_path(self, t):
        L, u = self.layer, self.uni
        n = len(self)
        c = u.mouse.pos[0] if L.path_around == MOUSE else u.center[0]
        ax, ay = L.path_size[0] * u.world[0] / 2, L.path_size[1] * u.world[1] / 2
        ph = TAU * (t * L.path_speed + L.path_spread * np.arange(n) / max(n, 1))
        new = np.column_stack([c[0] + ax * np.sin(L.path_freq[0] * ph + math.pi / 2),
                               c[1] + ay * np.sin(L.path_freq[1] * ph)])
        self.vel = new - self.pos
        self.pos = new

    # -- looks
    def colors(self):
        """Colour per layer (3,) or per body (N x 3), before brightness."""
        L, pal, t = self.layer, self.uni.p.palette, self.uni.t
        hue = pal.hue + pal.hue_speed * t
        m = L.color_mode
        if m == "fixed":
            return np.asarray(L.color, float)
        if m == "speed":
            k = np.sqrt(np.einsum("ij,ij->i", self.vel, self.vel)) / max(L.speed_ref, 1e-6)
            return self._lerp(np.clip(k, 0, 1))
        if m == "age":
            if L.life <= 0:
                return np.asarray(L.color, float)
            return self._lerp(np.clip(self.age / self.life, 0, 1))
        if m == "direction":
            ang = np.degrees(np.arctan2(self.vel[:, 1], self.vel[:, 0]))
            return hue_colors(hue + ang, pal.saturation, pal.value)
        if m == "rainbow":
            return hue_colors(hue + pal.spread * (self.hue_seed - 0.5), pal.saturation, pal.value)
        return hsv(hue, pal.saturation, pal.value)

    def _lerp(self, k):
        a, b = np.asarray(self.layer.color, float), np.asarray(self.layer.color2, float)
        return a + (b - a) * k[:, None]

    def light(self, base):
        """Per body brightness (fade in / out) or None."""
        L = self.layer
        if L.life <= 0 or not L.fade:
            return None
        rise = np.clip(self.age / 12.0, 0, 1)
        fall = np.clip((self.life - self.age) / (0.3 * self.life), 0, 1)
        return base * rise * fall

    def sprite(self, color, additive):
        key = (self.layer.dot, tuple(int(c) for c in color), additive)
        if key not in self._sprites:
            if len(self._sprites) > 96:
                self._sprites.clear()
            self._sprites[key] = make_dot(self.layer.dot, key[1], additive)
        return self._sprites[key]


# ------------------------------------------------------------------ the universe

class Universe:
    def __init__(self, preset: Preset, screen: pygame.Surface, mouse: Mouse, seed=None):
        self.screen = screen
        self.world = screen.get_size()          # read once
        self.center = np.array([[self.world[0] / 2, self.world[1] / 2]], float)
        self.rng = np.random.default_rng(seed)
        self.mouse = mouse
        self.mouse.update()
        self.p = preset
        self.t = 0.0
        self.frame = 0
        self.dark = 1.0
        self.swarms: list[Swarm] = []
        self._veil = self._one = None
        self.reconfigure(preset)
        screen.fill(tuple(preset.background))

    # -- live edits
    def reconfigure(self, preset: Preset):
        """Swap in new settings without a restart; bodies keep moving.
        Layers are matched by name (or by position, if renamed)."""
        self.p = preset
        new_names = {l.name for l in preset.layers}
        old = {s.layer.name: s for s in self.swarms}
        matched = []
        for i, layer in enumerate(preset.layers):
            s = old.pop(layer.name, None)
            if s is None and i < len(self.swarms):
                prev = self.swarms[i]
                if prev.layer.name not in new_names and old.get(prev.layer.name) is prev:
                    s = old.pop(prev.layer.name)
            matched.append((layer, s))
        self.swarms = []
        for layer, s in matched:           # rebuilt in order, so a new emitter sees its parents
            if s is None:
                s = Swarm(layer, self)
            else:
                s.layer = layer
                s.resize(layer.count)
                s.relife()
            self.swarms.append(s)

    def counts(self):
        return {s.layer.name: len(s) for s in self.swarms}

    def swarm(self, name):
        return next(s for s in self.swarms if s.layer.name == name)

    def source_arrays(self, swarm, source):
        """(positions, velocities) of a pull source, as seen from `swarm`."""
        i = self.swarms.index(swarm) if swarm in self.swarms else len(self.swarms)
        if source == ABOVE and i == 0:
            source = MOUSE
        if source == MOUSE:
            return self.mouse.pos, self.mouse.vel
        if source == CENTER:
            return self.center, np.zeros((1, 2))
        above = self.swarms[i - 1]
        return above.pos, above.vel

    # -- one frame
    def _breath(self):
        p = self.p
        if p.breathe_period <= 0:
            return 1.0
        x = abs((self.t % p.breathe_period) - p.breathe_period / 2)      # seconds from the dark moment
        width = min(6.0, p.breathe_period / 6)
        return 1.0 - p.breathe_depth * math.exp(-(x / width) ** 2)

    def step(self):
        p = self.p
        self.dark = self._breath()
        force_scale = self.dark if p.breathe_forces else 1.0
        self.mouse.update()
        mouse_sign = -1.0 if (p.click_invert and self.mouse.pressed) else 1.0
        wind = np.asarray(p.wind, float)
        t = self.t

        for swarm in self.swarms:
            L = swarm.layer
            if not len(swarm):
                continue
            if L.life > 0:
                swarm.age += 1
                swarm.reborn(swarm.age >= swarm.life)
            if L.motion == "fixed":
                continue
            if L.motion == "teleport":
                if self.frame % max(1, L.teleport_every) == 0:
                    swarm.pos = self.rng.random((len(swarm), 2)) * self.world
                    swarm.vel[:] = 0
                continue
            if L.motion == "path":
                swarm.follow_path(t)
                continue

            forces = []
            mass = (1 + L.variety * (2 * swarm.seed2 - 1))[:, None] if L.variety else None
            for pl in L.pulls:
                if not pl.enabled:
                    continue
                src, svel = self.source_arrays(swarm, pl.source)
                if len(src) * len(swarm) > MAX_PAIRS:
                    continue
                is_mouse = pl.source == MOUSE or (pl.source == ABOVE and swarm is self.swarms[0])
                pf = pulse_factor(pl.field, t)
                radius = pl.field.radius
                if pl.field.law == "ring":                    # rings breathe in size, not strength
                    radius, pf = radius * pf, 1.0
                scale = force_scale * pf * (mouse_sign if is_mouse else 1.0)
                if pl.field.law in ("drag", "wake"):
                    scale = pf                                 # light does not dim a sweep
                for s, sv in zip(src, svel):
                    if pl.field.law == "wake" and abs(sv[0]) + abs(sv[1]) < 1e-3:
                        continue                               # a still source leaves no wake
                    acc = pull(swarm.pos, swarm.vel, s, sv, pl.field, scale, radius)
                    forces.append(acc * mass if mass is not None else acc)
            carry = None
            if p.flow.enabled and L.flow:
                fv = flow(swarm.pos, p.flow, t) * L.flow
                if p.flow.mode == "carry":
                    carry = fv * 20                            # streamline speed, px / frame
                else:
                    forces.append(fv)
            if L.wind and wind.any():
                forces.append(wind * L.wind)
            if L.home:
                forces.append((swarm.home - swarm.pos) * L.home)
            if L.pressure or L.align:
                forces.append(neighbourhood(swarm.pos, swarm.vel, self.world, L.cell, L.pressure, L.align))
            if L.jitter:
                swarm.vel += self.rng.normal(0.0, L.jitter, swarm.vel.shape)
            if L.motion == "wander":
                swarm.vel += self.rng.normal(0.0, 0.5, swarm.vel.shape)

            friction = L.friction if L.friction is not None else p.friction
            swarm.you_must(forces, friction, p.friction_shape)
            if L.motion == "attractor":
                c = self.mouse.pos[0] if p.attractor.around == MOUSE else self.center[0]
                target = attractor_map(swarm.pos, p.attractor, t, self.world, c)
                swarm.pos += L.map_blend * (target - swarm.pos) + swarm.vel
            else:
                if carry is not None:
                    swarm.pos += carry
                swarm.therefore_you_can(p.edge, p.bounce)

        self.t += 1.0 / FPS
        self.frame += 1

    # -- painting
    def fade(self):
        p = self.p
        bg = tuple(int(c) for c in p.background)
        if p.trail <= 0:
            self.screen.fill(bg)
            return
        if p.trail >= 1:
            return
        if self._veil is None:
            self._veil = pygame.Surface(self.world)
            self._one = pygame.Surface(self.world)
            self._one.fill((1, 1, 1))
            try:
                self._veil, self._one = self._veil.convert(), self._one.convert()
            except pygame.error:            # no display (tests)
                pass
        self._veil.fill(bg)
        self._veil.set_alpha(int(round(255 * (1 - p.trail))))
        self.screen.blit(self._veil, (0, 0))
        if not any(bg):
            self.screen.blit(self._one, (0, 0), special_flags=pygame.BLEND_SUB)   # reach true black

    def copies(self, pos):
        """The kaleidoscope: every position, rotated (and mirrored) about the centre."""
        p = self.p
        k = max(1, int(p.symmetry))
        if k == 1 and not p.mirror:
            return [pos]
        c = self.center[0]
        rel = pos - c
        out = []
        for j in range(k):
            a = TAU * j / k
            ca, sa = math.cos(a), math.sin(a)
            rot = np.column_stack([rel[:, 0] * ca - rel[:, 1] * sa, rel[:, 0] * sa + rel[:, 1] * ca])
            out.append(rot + c)
            if p.mirror:
                out.append(np.column_stack([-rot[:, 0], rot[:, 1]]) + c)
        return out

    def draw(self):
        self.fade()
        for swarm in self.swarms:
            self._paint(swarm)

    def _paint(self, swarm: Swarm):
        L, p = swarm.layer, self.p
        if L.look == "none" or not len(swarm):
            return
        base = self.dark * p.brightness * L.brightness
        col = swarm.colors()
        light = swarm.light(base)
        if light is not None:
            col = (col if col.ndim == 2 else np.broadcast_to(col, (len(swarm), 3))) * light[:, None]
        else:
            col = col * base
        col = np.clip(col, 0, 255)
        additive = p.blend == "add"

        if L.look == "dot":
            jobs, flags = [], pygame.BLEND_RGB_ADD if additive else 0
            tint = col if col.ndim == 1 else None
            for xy in self.copies(swarm.pos):
                if tint is not None:
                    spr, o = swarm.sprite(tint, additive)
                    jobs += [(spr, (x - o, y - o)) for x, y in xy]
                else:                                    # a few tints: one sprite per tint
                    q = (col // 16 * 16).astype(int)
                    tints, inv = np.unique(q, axis=0, return_inverse=True)
                    for i, c in enumerate(tints):
                        spr, o = swarm.sprite(c, additive)
                        pts = xy[inv.ravel() == i] - o
                        jobs += [(spr, (x, y)) for x, y in pts]
            if flags:
                for spr, at in jobs:
                    self.screen.blit(spr, at, special_flags=flags)
            else:
                self.screen.blits(jobs, doreturn=False)
            return

        W, H = self.world
        px = pygame.surfarray.pixels3d(self.screen)
        s = max(1, min(4, int(L.size)))
        add = col * p.glow if additive else col.astype(np.uint8)
        for xy in self.copies(swarm.pos):
            x = np.floor(xy[:, 0]).astype(np.intp)
            y = np.floor(xy[:, 1]).astype(np.intp)
            for dx in range(s):
                for dy in range(s):
                    xx, yy = x + dx, y + dy
                    ok = (xx >= 0) & (xx < W) & (yy >= 0) & (yy < H)
                    c = add if add.ndim == 1 else add[ok]
                    if additive:
                        cur = px[xx[ok], yy[ok]].astype(np.float32)
                        px[xx[ok], yy[ok]] = np.minimum(cur + c, 255).astype(np.uint8)
                    else:
                        px[xx[ok], yy[ok]] = c
        del px
