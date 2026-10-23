"""
The simulation: forces, neighbourhoods, swarms, and the universe that ties
them together and paints them. No windows, keys or panels in here.

Everything is vectorised with NumPy: a swarm is two N x 2 arrays (pos, vel)
and every rule is applied to the whole array at once.
"""

from __future__ import annotations

import math
from datetime import datetime

import numpy as np
import pygame

from config import ABOVE, CENTER, MAX_PAIRS, MOUSE, Field, Layer, Preset

TAU = 2 * math.pi
FPS = 60.0           # simulated time advances 1/60 s per step, so pausing never jumps
MAX_LINK_BODIES = 700
MAX_LINKS = 4000


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


def make_dot(diameter: int, color, additive: bool, soft: float = 0.0) -> tuple[pygame.Surface, float]:
    """A round sprite, crisp (soft 0) to a gaussian glow (soft 1).
    Additive sprites are premultiplied RGB for BLEND_RGB_ADD."""
    d = max(1, int(diameter))
    c = (np.arange(d) + 0.5) - d / 2
    dist = np.sqrt(c[:, None] ** 2 + c[None, :] ** 2)
    alpha = np.clip(d / 2 + 0.5 - dist, 0, 1)
    if soft > 0:
        glow = np.exp(-2.5 * (dist / max(d / 2, 0.5)) ** 2)
        alpha = alpha * (1 - soft) + glow * soft
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
        if f.law in ("drag", "wake", "startle"):
            w = np.clip(1 - r / f.max_dist, 0, 1) if math.isfinite(f.max_dist) else np.ones_like(r)
            sv = np.asarray(src_vel, float)
            if f.law == "drag":
                acc = (sv - vel) * (g / 100 * w)[:, None]
            elif f.law == "wake":
                acc = np.broadcast_to(sv, vel.shape) * (g / 100 * w)[:, None]
            else:                                   # startle: away, as hard as the source moves
                speed = math.hypot(sv[0], sv[1])
                acc = -d / r[:, None] * (g * speed * w)[:, None]
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
    acc = np.array(acc)
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


# ------------------------------------------------------------------ 3D flows

def _lorenz(p):
    x, y, z = p[:, 0], p[:, 1], p[:, 2]
    return np.column_stack([10 * (y - x), x * (28 - z) - y, x * y - 8 / 3 * z])


def _aizawa(p):
    x, y, z = p[:, 0], p[:, 1], p[:, 2]
    zb = z - 0.7
    return np.column_stack([zb * x - 3.5 * y, 3.5 * x + zb * y,
                            0.6 + 0.95 * z - z * z * z / 3 - (x * x + y * y) * (1 + 0.25 * z) + 0.1 * z * x * x * x])


def _thomas(p):
    x, y, z = p[:, 0], p[:, 1], p[:, 2]
    b = 0.208186
    return np.column_stack([np.sin(y) - b * x, np.sin(z) - b * y, np.sin(x) - b * z])


def _halvorsen(p):
    x, y, z = p[:, 0], p[:, 1], p[:, 2]
    a = 1.89
    return np.column_stack([-a * x - 4 * y - 4 * z - y * y, -a * y - 4 * z - 4 * x - z * z,
                            -a * z - 4 * x - 4 * y - x * x])


def _rossler(p):
    x, y, z = p[:, 0], p[:, 1], p[:, 2]
    return np.column_stack([-y - z, x + 0.2 * y, 0.2 + z * (x - 5.7)])


# derivative, time step per sub-step, centre, radius, a point on the attractor, best side (yaw, degrees)
FLOWS_3D = {
    "lorenz": (_lorenz, 0.004, (0.0, 0.0, 24.5), 31.0, (4.6374, 4.5937, 22.5697), -45.0),
    "aizawa": (_aizawa, 0.01, (0.0, 0.0, 0.746), 1.52, (-0.0815, 1.2248, 0.1169), 0.0),
    "thomas": (_thomas, 0.045, (1.357, 1.357, 1.357), 3.52, (3.1171, 2.8729, 1.2847), 0.0),
    "halvorsen": (_halvorsen, 0.004, (-2.909, -2.909, -2.909), 12.7, (-1.1658, -5.114, -9.0167), 0.0),
    "rossler": (_rossler, 0.02, (1.127, -1.462, 10.472), 15.0, (-2.3354, 7.6668, 0.042), 0.0),
}


def rk4(f, p, dt):
    k1 = f(p)
    k2 = f(p + dt / 2 * k1)
    k3 = f(p + dt / 2 * k2)
    k4 = f(p + dt * k3)
    return p + dt / 6 * (k1 + 2 * k2 + 2 * k3 + k4)


def pendulum_rate(s, m2, l2, g):
    """d/dt of double pendulums [theta1, omega1, theta2, omega2] (m1 = l1 = 1, angles from straight down)."""
    th1, w1, th2, w2 = s[:, 0], s[:, 1], s[:, 2], s[:, 3]
    d = th1 - th2
    sd, cd = np.sin(d), np.cos(d)
    den = 2 + m2 - m2 * np.cos(2 * d)
    a1 = (-g * (2 + m2) * np.sin(th1) - m2 * g * np.sin(th1 - 2 * th2)
          - 2 * sd * m2 * (w2 * w2 * l2 + w1 * w1 * cd)) / den
    a2 = 2 * sd * (w1 * w1 * (1 + m2) + g * (1 + m2) * np.cos(th1) + w2 * w2 * l2 * m2 * cd) / (l2 * den)
    return np.column_stack([w1, a1, w2, a2])


# ------------------------------------------------------------------ text

DEFAULT_FONTS = ("pingfang,pingfangsc,hiraginosansgb,stheitimedium,heitisc,notosanscjksc,notosanscjk,"
                 "sourcehansanssc,wenquanyimicrohei,microsoftyahei,arialunicode,arialunicodems,dejavusans")
WEEKDAYS = "一二三四五六日"
_FONTS: dict = {}


def expand_text(template: str, t: float, period: float, now: datetime | None = None) -> str:
    """Pick the line that is due (lines are separated by |) and fill in the clock."""
    items = template.split("|") if template else [""]
    line = items[int(t // max(period, 0.5)) % len(items)]
    if "{" in line:
        now = now or datetime.now()
        line = (line.replace("{seconds}", now.strftime("%H:%M:%S"))
                    .replace("{time}", now.strftime("%H:%M"))
                    .replace("{date}", f"{now.month}月{now.day}日")
                    .replace("{weekday}", "星期" + WEEKDAYS[now.weekday()]))
    return line.replace("\\n", "\n")


def _font(names, px):
    key = (names, px)
    if key not in _FONTS:
        if len(_FONTS) > 24:
            _FONTS.clear()
        if not pygame.font.get_init():
            pygame.font.init()
        _FONTS[key] = pygame.font.SysFont(names, px)
    return _FONTS[key]


def text_points(text: str, n: int, world, size: float, pos, fonts: str, rng) -> np.ndarray:
    """n points spread over the pixels of `text`, centred at `pos` (screen fractions)."""
    W, H = world
    names = (fonts.strip() + "," + DEFAULT_FONTS) if fonts.strip() else DEFAULT_FONTS
    lines = text.split("\n") or [" "]
    px = max(8, int(size * H))
    for _ in range(4):                                   # shrink until it fits the screen
        font = _font(names, px)
        surfs = [font.render(line or " ", False, (255, 255, 255)) for line in lines]
        w = max(s.get_width() for s in surfs)
        h = sum(s.get_height() for s in surfs)
        fit = min(0.92 * W / max(w, 1), 0.9 * H / max(h, 1))
        if fit >= 1:
            break
        px = max(8, int(px * fit * 0.98))
    canvas = pygame.Surface((w, h))
    y = 0
    for s in surfs:
        canvas.blit(s, ((w - s.get_width()) // 2, y))
        y += s.get_height()
    on = pygame.surfarray.array3d(canvas)[:, :, 0] > 127
    xs, ys = np.nonzero(on)
    if len(xs) == 0:
        xs, ys = np.array([w // 2]), np.array([h // 2])
    pick = rng.choice(len(xs), n, replace=n > len(xs))
    pts = np.column_stack([xs[pick], ys[pick]]).astype(float) + rng.random((n, 2))
    pts += [pos[0] * W - w / 2, pos[1] * H - h / 2]
    return pts


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
        self.clicked = False                     # pressed this frame, not the last
        self._first = True

    def update(self):
        x, y, pressed = self.read()
        self.clicked = bool(pressed) and not self.pressed
        self.pressed = bool(pressed)
        new = np.array([[x, y]], float)
        if self._first:
            self.pos[:], self._first = new, False
        self.vel = 0.5 * self.vel + 0.5 * (new - self.pos)     # smoothed, px / frame
        self.pos = new


# ------------------------------------------------------------------ swarms

class Swarm:
    """All bodies of one layer."""

    PER_BODY = ("pos", "vel", "home", "age", "life", "hue_seed", "seed2", "birth_hue")

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
        self.birth_hue = np.zeros(0)
        self.text_key = None
        self.crystal = None                      # grow: the crystal
        self.scent = None                        # slime: the scent map
        self.p3 = None                           # flow3d: positions in 3D
        self.p3_kind = None
        self.depth = None
        self.view = None
        self.pend = None                         # pendulum: [theta1, omega1, theta2, omega2] per body
        self.pend_release = None
        self.joint = None
        self.path_u = None                       # sunflower: how far out each seed is
        self._sprites = {}
        self.resize(layer.count, fresh=True)
        if layer.motion == "path":                 # start on the curve, so children are born around it
            self.follow_path(uni.t)
            self.vel[:] = 0

    def __len__(self):
        return len(self.pos)

    # -- birth
    def _parents(self, n):
        """Reference point, its velocity, and a parent index (for birth colours)."""
        u, L = self.uni, self.layer
        if L.spawn in ("above", "above_ring"):
            src, svel = u.source_arrays(self, ABOVE)
            if len(src):
                k = self.rng.integers(0, len(src), n)
                return src[k], svel[k], k
        if L.spawn in ("mouse", "mouse_ring"):
            return np.repeat(u.mouse.pos, n, 0), np.repeat(u.mouse.vel, n, 0), np.zeros(n, int)
        return np.repeat(u.center, n, 0), np.zeros((n, 2)), np.zeros(n, int)

    def _hue_now(self):
        pal = self.uni.p.palette
        return pal.hue + pal.hue_speed * self.uni.t

    def spawn(self, n, fresh=False, at=None):
        """Positions, velocities and birth hues for n newborns (at a point, if given)."""
        L, rng = self.layer, self.rng
        W, H = self.uni.world
        ref, ref_vel, parent = self._parents(n)
        if at is not None:
            ref = np.repeat(np.asarray(at, float)[None, :], n, 0)
            ref_vel = np.zeros((n, 2))
            pos = ref.copy()
        elif L.spawn in ("center", "mouse", "above"):
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
        elif L.spawn in ("circle", "above_ring", "mouse_ring"):
            a = rng.random(n) * TAU
            r = L.spawn_radius + rng.normal(0, L.spawn_spread, n)
            pos = ref + np.column_stack([np.cos(a), np.sin(a)]) * r[:, None]
        else:                                            # random, text (flies in to its glyph)
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
        elif L.velocity == "sphere":                 # a 3D shell bursting, seen head-on: bright rim
            a = rng.random(n) * TAU
            m = s * np.sqrt(1 - rng.uniform(-1, 1, n) ** 2) * (0.93 + 0.07 * rng.random(n))
            vel = np.column_stack([np.cos(a), np.sin(a)]) * m[:, None] + ref_vel
        else:
            a = rng.random(n) * TAU
            m = s * np.sqrt(rng.random(n))
            vel = np.column_stack([np.cos(a), np.sin(a)]) * m[:, None]
            if L.velocity == "inherit":
                vel += ref_vel
        # each parent gets its own colour (golden-angle apart), drifting with the palette
        hue = self._hue_now() + 137.508 * parent + rng.normal(0, 6, n)
        return pos.astype(float), vel.astype(float), hue

    def _lives(self, n):
        L = self.layer
        if L.life <= 0:
            return np.full(n, np.inf)
        j = L.life_jitter * (2 * self.rng.random(n) - 1)
        return np.maximum(1.0, L.life * (1 + j))

    def resize(self, n, fresh=False):
        n = max(0, int(n))
        changed = n != len(self)
        if n > len(self):
            k = n - len(self)
            p, v, hue = self.spawn(k, fresh=fresh and len(self) == 0)
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
            self.birth_hue = np.concatenate([self.birth_hue, hue])
        elif n < len(self):
            for name in self.PER_BODY:
                setattr(self, name, getattr(self, name)[:n].copy())
        if changed:
            self.text_key = None                 # re-spread over the glyphs next frame
            self.crystal = None
            self.p3 = self.pend = None

    def reborn(self, mask):
        k = int(mask.sum())
        if not k:
            return
        if self.p3 is not None:
            self._reborn3d(mask)
        if self.pend is not None:
            self.pend[mask] = self._pend_start(np.flatnonzero(mask))
        p, v, hue = self.spawn(k)
        self.pos[mask], self.vel[mask] = p, v
        if self.layer.spawn != "text":            # text bodies keep flying to their glyph
            self.home[mask] = p
        self.birth_hue[mask] = hue
        self.age[mask] = 0
        self.life[mask] = self._lives(k)

    def burst_at(self, point, n):
        """A click: the n oldest bodies are reborn at `point`."""
        n = min(int(n), len(self))
        if n <= 0:
            return
        ratio = self.age / np.where(np.isfinite(self.life), self.life, 1e9)
        idx = np.argsort(ratio + self.rng.random(len(self)) * 1e-6)[-n:]
        p, v, hue = self.spawn(n, at=point)
        hue[:] = self._hue_now() + self.rng.normal(0, 6, n)    # one colour per click
        self.pos[idx], self.vel[idx], self.home[idx] = p, v, p
        self.birth_hue[idx] = hue
        self.age[idx] = 0
        self.life[idx] = self._lives(n)

    def relife(self):
        """Lifetime settings changed in the panel."""
        if self.layer.life <= 0:
            self.life[:] = np.inf
        elif not np.isfinite(self.life).all() or abs(np.median(self.life) - self.layer.life) > 0.5:
            self.life = self._lives(len(self))
            self.age = np.minimum(self.age, self.life - 1)

    # -- text
    def retarget(self, text):
        """Spread the bodies over the glyphs of `text`; each flies to its new pixel."""
        L = self.layer
        n = len(self)
        pts = text_points(text, n, self.uni.world, L.text_size, L.text_pos, L.text_font, self.rng)
        # pair bodies and pixels left-to-right (with a little noise), so the swarm sweeps
        # sideways into the new shape instead of criss-crossing the screen
        order_b = np.argsort(self.pos[:, 0] + self.rng.normal(0, 25, n))
        order_t = np.argsort(pts[:, 0])
        home = np.empty_like(pts)
        home[order_b] = pts[order_t]
        self.home = home
        self.text_key = text

    # -- crystal growth (diffusion-limited aggregation)
    def _crystal_reset(self):
        L, (W, H) = self.layer, self.uni.world
        g = 2
        occ = np.zeros((H // g + 3, W // g + 3), bool)
        n = len(self)
        cx, cy = W / 2, H / 2
        if L.grow_seed == "bottom":
            occ[(H - g - 1) // g:, :] = True
        else:
            occ[int(cy) // g, int(cx) // g] = True
        self.crystal = {"g": g, "occ": occ, "hits": np.zeros(occ.shape, np.int16),
                        "stuck": np.zeros(n, bool), "walking": np.zeros(n, bool),
                        "reach": 2.0, "done_at": None, "center": (cx, cy)}
        self.pos[:] = (cx, cy) if L.grow_seed != "bottom" else (cx, H - 1)
        self.vel[:] = 0

    def _fold(self, P):
        """Reflect positions into the wedge 0..pi/fold around the centre."""
        fold = self.layer.grow_fold
        if fold <= 0 or self.layer.grow_seed == "bottom":
            return P
        cx, cy = self.crystal["center"]
        d = P - (cx, cy)
        r = np.hypot(d[:, 0], d[:, 1])
        a = np.mod(np.arctan2(d[:, 1], d[:, 0]), TAU / fold)
        a = np.where(a > math.pi / fold, TAU / fold - a, a)
        return np.column_stack([cx + r * np.cos(a), cy + r * np.sin(a)])

    def _launch(self, k):
        L, (W, H), c = self.layer, self.uni.world, self.crystal
        if L.grow_seed == "bottom":
            y = H - c["reach"] - 15
            return np.column_stack([self.rng.random(k) * W, np.full(k, y)])
        cx, cy = c["center"]
        wedge = math.pi / L.grow_fold if L.grow_fold > 0 else TAU
        a = self.rng.random(k) * wedge
        r = c["reach"] + 15
        return np.column_stack([cx + r * np.cos(a), cy + r * np.sin(a)])

    def grow(self, t, mouse):
        L = self.layer
        if self.crystal is None or len(self.crystal["stuck"]) != len(self):
            self._crystal_reset()
        c = self.crystal
        W, H = self.uni.world
        g, occ, stuck, walking = c["g"], c["occ"], c["stuck"], c["walking"]
        if c["done_at"] is not None:
            if t - c["done_at"] > L.grow_hold:
                self._crystal_reset()
            return
        limit = (H - 40) if L.grow_seed == "bottom" else 0.47 * min(W, H)
        free = np.flatnonzero(~stuck)
        if len(free) == 0 or c["reach"] > limit:
            c["done_at"] = t
            return

        # a moving cursor melts the crystal from the outside in, down to where it touches (folded into
        # the wedge, so every copy melts at once); regrowth then starts from a connected edge
        if L.grow_melt > 0 and abs(mouse.vel[0, 0]) + abs(mouse.vel[0, 1]) > 1.5:
            idx = np.flatnonzero(stuck)
            P0 = self.pos[idx]
            if L.grow_seed == "bottom":
                hit = np.hypot(*(P0 - mouse.pos[0]).T) < L.grow_melt
                cut = (H - P0[:, 1]) >= (H - mouse.pos[0, 1]) - L.grow_melt if hit.any() else hit
            else:
                m = self._fold(mouse.pos.copy())[0]
                hit = np.hypot(*(P0 - m).T) < L.grow_melt
                rm = math.hypot(m[0] - c["center"][0], m[1] - c["center"][1])
                r0 = np.hypot(P0[:, 0] - c["center"][0], P0[:, 1] - c["center"][1])
                cut = r0 >= rm - L.grow_melt if hit.any() else hit
            gone = idx[cut]
            if len(gone):
                cells = (self.pos[gone] // g).astype(int)
                occ[cells[:, 1], cells[:, 0]] = False
                c["hits"][:] = 0
                stuck[gone] = False
                walking[gone] = False
                free = np.flatnonzero(~stuck)
                left = self.pos[stuck]
                if L.grow_seed == "bottom":
                    c["reach"] = max(2.0, float(H - left[:, 1].min())) if len(left) else 2.0
                else:
                    c["reach"] = max(2.0, float(np.hypot(left[:, 0] - c["center"][0],
                                                         left[:, 1] - c["center"][1]).max())) if len(left) else 2.0
                walking[:] = False                          # everyone in flight starts again from the new edge

        active = free[:max(1, L.grow_walkers)]
        new = active[~walking[active]]
        if len(new):
            self.pos[new] = self._launch(len(new))
            walking[new] = True
        P = self.pos[active]
        cx, cy = c["center"]
        hue = self._hue_now()
        for _ in range(max(1, L.grow_speed)):
            a = self.rng.random(len(P)) * TAU
            P = P + np.column_stack([np.cos(a), np.sin(a)]) * g
            if L.grow_seed == "bottom":
                P[:, 0] = np.mod(P[:, 0], W)
                far = P[:, 1] < H - c["reach"] - 60
            else:
                P = self._fold(P)
                far = np.hypot(P[:, 0] - cx, P[:, 1] - cy) > c["reach"] + 50
            if far.any():
                P[far] = self._launch(int(far.sum()))
            P[:, 0] = np.clip(P[:, 0], g, W - g - 1)
            P[:, 1] = np.clip(P[:, 1], g, H - g - 1)
            gx = (P[:, 0] // g).astype(int)
            gy = (P[:, 1] // g).astype(int)
            hit = np.zeros(len(P), bool)
            for dy in (-1, 0, 1):
                for dx in (-1, 0, 1):
                    hit |= occ[gy + dy, gx + dx]
            if hit.any() and L.grow_noise > 1:
                # noise reduction: a site freezes only after several touches; the others start over
                hy, hx = gy[hit], gx[hit]
                np.add.at(c["hits"], (hy, hx), 1)
                ready = c["hits"][hy, hx] >= L.grow_noise
                retry = np.flatnonzero(hit)[~ready]
                if len(retry):
                    P[retry] = self._launch(len(retry))
                    hit[retry] = False
            if hit.any():
                hits = active[hit]
                occ[gy[hit], gx[hit]] = True
                stuck[hits] = True
                walking[hits] = False
                self.pos[hits] = P[hit]
                self.birth_hue[hits] = hue + self.rng.normal(0, 4, len(hits))
                if L.grow_seed == "bottom":
                    c["reach"] = max(c["reach"], float(H - P[hit, 1].min()))
                else:
                    c["reach"] = max(c["reach"], float(np.hypot(P[hit, 0] - cx, P[hit, 1] - cy).max()))
                active, P = active[~hit], P[~hit]
                if not len(active):
                    break
        self.pos[active] = P

    # -- slime mould (Physarum): smell ahead, turn toward the strongest scent, lay more
    def slime(self, mouse, sign):
        L, (W, H) = self.layer, self.uni.world
        g = max(1, int(L.slime_cell))
        gw, gh = max(1, math.ceil(W / g)), max(1, math.ceil(H / g))
        T = self.scent
        if T is None or T.shape != (gh, gw):
            T = np.zeros((gh, gw), np.float32)
        n = len(self)
        # headings as unit vectors: turning is a rotation, no trigonometry per agent
        sp = np.sqrt(np.einsum("ij,ij->i", self.vel, self.vel))
        still = sp < 1e-9
        if still.any():
            a = self.rng.random(int(still.sum())) * TAU
            self.vel[still] = np.column_stack([np.cos(a), np.sin(a)])
            sp[still] = 1.0
        fx = (self.vel[:, 0] / sp).astype(np.float32)
        fy = (self.vel[:, 1] / sp).astype(np.float32)
        x = self.pos[:, 0].astype(np.float32)
        y = self.pos[:, 1].astype(np.float32)
        flat, inv, sd = T.ravel(), np.float32(1.0 / g), np.float32(L.slime_dist)

        def smell(dx, dy):
            ix = ((x + dx * sd) * inv).astype(np.int32) % gw
            iy = ((y + dy * sd) * inv).astype(np.int32) % gh
            return flat[iy * gw + ix]

        cs, ss = np.float32(math.cos(math.radians(L.slime_angle))), np.float32(math.sin(math.radians(L.slime_angle)))
        f = smell(fx, fy)
        fl = smell(fx * cs + fy * ss, fy * cs - fx * ss)
        fr = smell(fx * cs - fy * ss, fy * cs + fx * ss)
        ahead = (f >= fl) & (f >= fr)
        lost = (f < fl) & (f < fr)                     # both sides smell better: pick one at random
        side = np.where(lost, np.where(self.rng.random(n) < 0.5, 1, -1), np.where(fr > fl, 1, -1))
        side[ahead] = 0
        ct, st = math.cos(math.radians(L.slime_turn)), math.sin(math.radians(L.slime_turn))
        s_ = side * st
        nx = fx * np.where(side == 0, 1.0, ct) - fy * s_
        ny = fy * np.where(side == 0, 1.0, ct) + fx * s_
        if L.jitter:                                   # wobble: a small random sideways nudge
            k = self.rng.normal(0.0, L.jitter, n)
            nx, ny = nx - ny * k, ny + nx * k
            norm = np.sqrt(nx * nx + ny * ny)
            nx, ny = nx / norm, ny / norm
        self.vel = np.column_stack([nx, ny]).astype(float) * L.slime_speed
        self.therefore_you_can(self.uni.p.edge, self.uni.p.bounce)

        ix = (self.pos[:, 0] * inv).astype(np.int32) % gw
        iy = (self.pos[:, 1] * inv).astype(np.int32) % gh
        T += (np.bincount(iy * gw + ix, minlength=gw * gh).reshape(gh, gw)
              * np.float32(L.slime_deposit)).astype(np.float32)
        if L.slime_mouse:                               # food at the cursor (or poison, inverted)
            R = max(1, int(round(L.slime_mouse_radius / g)))
            yy, xx = np.mgrid[-R:R + 1, -R:R + 1]
            disk = xx * xx + yy * yy <= R * R
            mx, my = int(mouse.pos[0, 0] // g), int(mouse.pos[0, 1] // g)
            T[(yy[disk] + my) % gh, (xx[disk] + mx) % gw] += np.float32(sign * L.slime_mouse)
        if L.slime_blur > 0:                            # diffuse (3 x 3 box blur, wrapping)
            B = (T + np.roll(T, 1, 0) + np.roll(T, -1, 0)) * np.float32(1 / 3)
            B = (B + np.roll(B, 1, 1) + np.roll(B, -1, 1)) * np.float32(1 / 3)
            T = B if L.slime_blur >= 1 else T + (B - T) * np.float32(L.slime_blur)
        T *= np.float32(1 - L.slime_decay)
        self.scent = T

    # -- a 3D strange attractor (a flow), turned around in front of you
    def _flow3d_start(self, n):
        cfg = self.uni.p.flow3d
        f, dt, center, radius, point, _ = FLOWS_3D[self.p3_kind]
        if cfg.start == "blob":
            return self._blob(np.asarray(point, float), n, cfg.blob * radius)
        # a few dozen independent trajectories, settled onto the attractor, sampled over a long time
        seeds = max(8, min(64, n // 300))
        p = np.asarray(point, float) + self.rng.normal(0, 0.05 * radius, (seeds, 3))
        for _ in range(600):
            p = rk4(f, p, dt * 2)
        every = 6
        out = []
        for _ in range(math.ceil(n / seeds)):
            for _ in range(every):
                p = rk4(f, p, dt * 2)
            out.append(p.copy())
        P = np.concatenate(out)[:n]
        ok = np.isfinite(P).all(axis=1) & (np.abs(P - np.asarray(center)) < 4 * radius).all(axis=1)
        P = P[ok] if ok.any() else np.asarray(point, float)[None, :]
        P = P[self.rng.integers(0, len(P), n)] if len(P) < n else P
        return P[self.rng.permutation(n)]

    def _blob(self, at, n, size):
        """n points on a tiny segment, in body order: neighbours in colour stay neighbours in space,
        so the stretching and folding shows as a ribbon."""
        d = self.rng.normal(0, 1, 3)
        d /= np.linalg.norm(d)
        return at + np.outer(np.linspace(-0.5, 0.5, n), d) * size + self.rng.normal(0, size * 0.02, (n, 3))

    def _reborn3d(self, mask):
        cfg = self.uni.p.flow3d
        radius = FLOWS_3D[self.p3_kind][3]
        rest = np.flatnonzero(~mask)
        k = int(mask.sum())
        if len(rest) == 0:                              # everyone at once: a new speck somewhere on it
            self.p3[mask] = self._blob(self.p3[self.rng.integers(0, len(self.p3))], k, max(cfg.blob, 1e-7) * radius)
        else:
            src = self.p3[rest[self.rng.integers(0, len(rest), k)]]
            self.p3[mask] = src + self.rng.normal(0, max(cfg.blob, 1e-6) * radius, (k, 3))

    def flow3d(self, t, mouse):
        cfg = self.uni.p.flow3d
        kind = cfg.kind if cfg.kind in FLOWS_3D else "lorenz"
        n = len(self)
        if self.p3 is None or len(self.p3) != n or self.p3_kind != kind:
            self.p3_kind = kind
            self.p3 = self._flow3d_start(n)
        f, dt, center, radius, point, yaw0 = FLOWS_3D[kind]
        steps = max(1, math.ceil(2 * abs(cfg.speed)))
        h = dt * 2 * cfg.speed / steps
        for _ in range(steps):                          # midpoint rule: plenty for drawing, half of RK4
            self.p3 = self.p3 + h * f(self.p3 + h / 2 * f(self.p3))
        c = np.asarray(center)
        bad = ~np.isfinite(self.p3).all(axis=1) | (np.abs(self.p3 - c) > 4 * radius).any(axis=1)
        if bad.any():                                   # escaped (too big a step): back onto the attractor
            good = np.flatnonzero(~bad)
            src = self.p3[good[self.rng.integers(0, len(good), int(bad.sum()))]] if len(good) else c + 0 * self.p3[bad]
            self.p3[bad] = src + self.rng.normal(0, 1e-3 * radius, (int(bad.sum()), 3))

        W, H = self.uni.world
        mx, my = mouse.pos[0]
        yaw = math.radians(yaw0) + TAU * cfg.spin * t + cfg.mouse_turn * TAU * (mx / max(W, 1) - 0.5)
        pitch = math.radians(cfg.tilt) + cfg.mouse_turn * 0.5 * math.pi * (my / max(H, 1) - 0.5)
        if self.view is None:
            self.view = [yaw, pitch]
        else:                                            # turn smoothly toward where the cursor says
            self.view[0] += (yaw - self.view[0]) * 0.06
            self.view[1] += (pitch - self.view[1]) * 0.06
        yaw, pitch = self.view
        q = (self.p3 - c) / radius
        x, y, z = q[:, 0], q[:, 1], q[:, 2]
        X = x * math.cos(yaw) - y * math.sin(yaw)
        Y = x * math.sin(yaw) + y * math.cos(yaw)
        up = z * math.cos(pitch) - Y * math.sin(pitch)
        depth = z * math.sin(pitch) + Y * math.cos(pitch)
        k = 1.0 / np.maximum(0.2, 1.0 + cfg.perspective * 0.6 * depth)
        R = cfg.scale * min(W, H) / 2
        new = np.column_stack([W / 2 + R * X * k, H / 2 - R * up * k])
        self.vel = new - self.pos
        self.pos = new
        self.depth = depth

    # -- double pendulums: each body is the tip of its own
    def _pend_start(self, idx):
        L, n = self.layer, max(len(self), 2)
        a0 = self.pend_release if self.pend_release is not None else math.radians(L.pend_angle)
        a = a0 + math.radians(L.pend_spread) * (idx / (n - 1) - 0.5)
        z = np.zeros(len(idx))
        return np.column_stack([a, z, a, z])

    def pendulum(self, mouse):
        L, (W, H) = self.layer, self.uni.world
        n = len(self)
        piv = np.array([L.pend_pivot[0] * W, L.pend_pivot[1] * H])
        if L.pend_click and mouse.clicked:              # let go of all of them where you clicked
            d = mouse.pos[0] - piv
            self.pend_release = math.atan2(d[0], d[1])
            self.pend = None
        if self.pend is None or len(self.pend) != n:
            self.pend = self._pend_start(np.arange(n))
        steps = 8
        h = L.pend_speed / FPS / steps
        s, m2, l2, g = self.pend, L.pend_mass, max(L.pend_ratio, 0.05), L.pend_gravity
        for _ in range(steps):
            k1 = pendulum_rate(s, m2, l2, g)
            k2 = pendulum_rate(s + h / 2 * k1, m2, l2, g)
            k3 = pendulum_rate(s + h / 2 * k2, m2, l2, g)
            k4 = pendulum_rate(s + h * k3, m2, l2, g)
            s = s + h / 6 * (k1 + 2 * k2 + 2 * k3 + k4)
        self.pend = s
        unit = L.pend_size * min(W, H) / (1 + l2)
        th1, th2 = s[:, 0], s[:, 2]
        joint = piv + unit * np.column_stack([np.sin(th1), np.cos(th1)])
        tip = joint + unit * l2 * np.column_stack([np.sin(th2), np.cos(th2)])
        self.vel = tip - self.pos
        self.pos = tip
        self.joint = joint

    # -- motion
    def you_must(self, forces, friction, shape):
        """Feel every force, then friction (v *= 1 - f v^2, never flipping sign)."""
        L = self.layer
        if L.damping:
            self.vel *= max(0.0, 1.0 - L.damping)
        for acc in forces:
            self.vel += acc
        if shape == "axis":
            v2 = self.vel * self.vel
        else:
            v2 = np.einsum("ij,ij->i", self.vel, self.vel)[:, None]
        self.vel *= np.maximum(0.0, 1.0 - friction * v2)
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

    def path_points(self, t):
        """Where every body of a path layer should be at time t."""
        L, u = self.layer, self.uni
        n = len(self)
        W, H = u.world
        if L.path_around == MOUSE:
            c = u.mouse.pos[0]
        else:
            c = np.array([L.path_center[0] * W, L.path_center[1] * H])
        ph = TAU * (t * L.path_speed + L.path_spread * L.path_loops * np.arange(n) / max(n, 1))
        if L.path_shape == "sunflower":
            # Vogel's model: seed j at angle j * divergence, radius sqrt(j). The newest seed is in the
            # middle; with path_speed > 0 the seeds stream outward (path_speed = share of the flower
            # per second), and the divergence can swing around the golden angle.
            ax = ay = L.path_size[0] * min(W, H) / 2
            b = np.arange(n, dtype=float)
            if L.path_speed:
                born = t * L.path_speed * n
                u_ = np.mod(born - b, n)
                j = born - u_
            else:
                u_ = j = b
            self.path_u = u_
            div = L.path_angle + L.path_sweep * math.sin(TAU * t / max(L.path_sweep_period, 1e-3))
            th = np.radians(div) * j
            r = np.sqrt((u_ + 0.5) / n)
            x, y = r * np.cos(th), r * np.sin(th)
        elif L.path_shape in ("rose", "spiro"):
            ax = ay = L.path_size[0] * min(W, H) / 2
            if L.path_shape == "rose":
                r = np.cos(L.path_k * ph)
                x, y = r * np.cos(ph), r * np.sin(ph)
            else:
                q = min(max(L.path_k, 0.01), 0.99)
                k = (1 - q) / q
                x = (1 - q) * np.cos(ph) + L.path_d * q * np.cos(k * ph)
                y = (1 - q) * np.sin(ph) - L.path_d * q * np.sin(k * ph)
                norm = (1 - q) + L.path_d * q
                x, y = x / norm, y / norm
        else:
            ax, ay = L.path_size[0] * W / 2, L.path_size[1] * H / 2
            x = np.sin(L.path_freq[0] * ph + math.pi / 2)
            y = np.sin(L.path_freq[1] * ph)
        if L.path_spin:
            a = TAU * L.path_spin * t
            x, y = x * math.cos(a) - y * math.sin(a), x * math.sin(a) + y * math.cos(a)
        return np.column_stack([c[0] + ax * x, c[1] + ay * y])

    def follow_path(self, t):
        new = self.path_points(t)
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
        if m == "birth":
            return hue_colors(self.birth_hue, pal.saturation, pal.value)
        if m == "index":
            return hue_colors(hue + pal.spread * np.arange(len(self)) / max(len(self), 1),
                              pal.saturation, pal.value)
        return hsv(hue, pal.saturation, pal.value)

    def _lerp(self, k):
        a, b = np.asarray(self.layer.color, float), np.asarray(self.layer.color2, float)
        return a + (b - a) * k[:, None]

    def light(self, base):
        """Per body brightness (fade in / out, crystal walkers) or None."""
        L = self.layer
        if L.motion == "grow" and self.crystal is not None:
            c = self.crystal
            out = np.where(c["stuck"], base, np.where(c["walking"], base * L.grow_walker_light, 0.0))
            if c["done_at"] is not None:                 # the finished crystal fades before regrowing
                left = L.grow_hold - (self.uni.t - c["done_at"])
                out = out * min(1.0, max(0.0, left / 3.0))
            return out
        out = None
        if L.motion == "flow3d" and self.depth is not None and self.uni.p.flow3d.depth_light:
            k = self.uni.p.flow3d.depth_light               # the far side is dimmer: depth you can see
            out = base * np.clip(1 - k * (self.depth + 1) / 2, 0.05, 1.5)
        if L.motion == "path" and L.path_shape == "sunflower" and L.path_speed and self.path_u is not None:
            n = max(len(self), 1)                         # seeds fade in at the heart, out at the rim
            u_ = self.path_u
            out = (base if out is None else out) * np.clip((n - u_) / (0.1 * n), 0, 1) * np.clip(u_ / (0.004 * n), 0, 1)
        if L.twinkle > 0:                                  # each body flickers on its own clock
            ph = self.uni.t / (max(L.twinkle_period, 0.05) * (0.7 + 0.6 * self.seed2)) + self.hue_seed
            wave = (0.5 + 0.5 * np.sin(TAU * ph)) ** (2 + 10 * L.twinkle)   # strong twinkle = brief flashes
            out = (base if out is None else out) * (1 - L.twinkle + L.twinkle * wave)
        if L.life > 0 and L.fade:
            rise = np.clip(self.age / 12.0, 0, 1)
            fall = np.clip((self.life - self.age) / (0.3 * self.life), 0, 1)
            out = (base if out is None else out) * rise * fall
        return out

    def sprite(self, color, additive):
        key = (self.layer.dot, tuple(int(c) for c in color), additive, self.layer.dot_soft)
        if key not in self._sprites:
            if len(self._sprites) > 96:
                self._sprites.clear()
            self._sprites[key] = make_dot(self.layer.dot, key[1], additive, self.layer.dot_soft)
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
                text_changed = (s.layer.text, s.layer.text_size, s.layer.text_pos, s.layer.text_font) != \
                               (layer.text, layer.text_size, layer.text_pos, layer.text_font)
                regrow = s.layer.motion != layer.motion or s.layer.grow_seed != layer.grow_seed or \
                    s.layer.grow_fold != layer.grow_fold
                if (s.layer.pend_angle, s.layer.pend_spread, s.layer.motion) != \
                        (layer.pend_angle, layer.pend_spread, layer.motion):
                    s.pend, s.pend_release = None, None
                s.layer = layer
                s.resize(layer.count)
                s.relife()
                if text_changed:
                    s.text_key = None
                if regrow:
                    s.crystal = None
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

    def _wind(self):
        p = self.p
        w = np.asarray(p.wind, float)
        if p.wind_mode == "tilt":
            d = self.mouse.pos[0] - self.center[0]
            n = math.hypot(d[0], d[1])
            strength = math.hypot(w[0], w[1])
            # a dead zone in the middle, so a centred cursor means a level tray
            k = min(1.0, max(0.0, (n - 40) / (0.35 * min(self.world))))
            w = d / n * strength * k if n > 1e-6 else np.zeros(2)
        return w

    def step(self):
        p = self.p
        self.dark = self._breath()
        force_scale = self.dark if p.breathe_forces else 1.0
        self.mouse.update()
        mouse_sign = -1.0 if (p.click_invert and self.mouse.pressed) else 1.0
        wind = self._wind()
        t = self.t

        for swarm in self.swarms:
            L = swarm.layer
            if not len(swarm):
                continue
            if L.spawn == "text":
                text = expand_text(L.text, t, L.text_period)
                if text != swarm.text_key:
                    swarm.retarget(text)
            if L.click_burst and self.mouse.clicked:
                swarm.burst_at(self.mouse.pos[0], L.click_burst)
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
                if L.home <= 0:                              # rigid: exactly on the curve
                    swarm.follow_path(t)
                    continue
                swarm.home = swarm.path_points(t)            # elastic: springs toward the moving curve
            elif L.motion == "grow":
                swarm.grow(t, self.mouse)
                continue
            elif L.motion == "slime":
                swarm.slime(self.mouse, mouse_sign)
                continue
            elif L.motion == "flow3d":
                swarm.flow3d(t, self.mouse)
                continue
            elif L.motion == "pendulum":
                swarm.pendulum(self.mouse)
                continue

            forces = []
            eaten = None
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
                if pl.field.law in ("drag", "wake", "startle"):
                    scale = pf                                 # light does not dim a sweep
                for s, sv in zip(src, svel):
                    if pl.field.absorb > 0:
                        d = swarm.pos - s
                        hit = np.einsum("ij,ij->i", d, d) < pl.field.absorb ** 2
                        eaten = hit if eaten is None else (eaten | hit)
                    if pl.field.law in ("wake", "startle") and abs(sv[0]) + abs(sv[1]) < 1e-3:
                        continue                               # a still source stirs nothing
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
            if eaten is not None and eaten.any():
                swarm.reborn(eaten)

        self.t += 1.0 / FPS
        self.frame += 1

    # -- painting
    def fade(self):
        """Trails: blend a veil of the background over the last frame. Very long trails fade
        one step every few frames; a last nudge of 1 makes every pixel really reach the
        background (from above on dark backgrounds, from below on light 'paper')."""
        p = self.p
        bg = tuple(int(c) for c in p.background)
        if p.trail <= 0:
            self.screen.fill(bg)
            return
        if p.trail >= 1:
            return
        alpha = 255 * (1 - p.trail)
        every = 1 if alpha >= 1 else max(1, int(round(1 / alpha)))
        if self.frame % every:
            return
        if self._veil is None:
            self._veil = pygame.Surface(self.world)
            self._one = pygame.Surface(self.world)
            self._one.fill((1, 1, 1))
            self._bgs = pygame.Surface(self.world)
            try:
                self._veil, self._one, self._bgs = self._veil.convert(), self._one.convert(), self._bgs.convert()
            except pygame.error:            # no display (tests)
                pass
        self._veil.fill(bg)
        self._veil.set_alpha(max(1, int(round(alpha))))
        self.screen.blit(self._veil, (0, 0))
        if sum(bg) >= 384:                  # paper: ink fades up toward it
            self._bgs.fill(bg)
            self.screen.blit(self._one, (0, 0), special_flags=pygame.BLEND_RGB_ADD)
            self.screen.blit(self._bgs, (0, 0), special_flags=pygame.BLEND_RGB_MIN)
        else:                               # night: light fades down toward it
            self.screen.blit(self._one, (0, 0), special_flags=pygame.BLEND_RGB_SUB)
            if any(bg):
                self._bgs.fill(bg)
                self.screen.blit(self._bgs, (0, 0), special_flags=pygame.BLEND_RGB_MAX)

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

    def _links(self, swarm: Swarm, col):
        """Constellation lines between nearby bodies (and the cursor)."""
        L = swarm.layer
        P, C = swarm.pos, col
        m = self.mouse.pos[0]
        if L.link_reveal > 0:                       # only the sky around the cursor shows its lines
            near = np.flatnonzero(np.hypot(*(P - m).T) < L.link_reveal + L.links)
            P = P[near]
            C = col[near] if col.ndim == 2 else col
        n = len(P)
        if n < 2 or n > MAX_LINK_BODIES:
            return
        d = P[:, None, :] - P[None, :, :]
        dist = np.sqrt(np.einsum("ijk,ijk->ij", d, d))
        if L.link_max > 0:                          # each body links only to its nearest few
            D = np.where(dist < L.links, dist, np.inf)
            np.fill_diagonal(D, np.inf)
            k = min(int(L.link_max), n - 1)
            nn = np.argpartition(D, k - 1, axis=1)[:, :k]
            rows = np.repeat(np.arange(n), k)
            cols = nn.ravel()
            ok = np.isfinite(D[rows, cols])
            key = np.unique(np.minimum(rows, cols)[ok] * n + np.maximum(rows, cols)[ok])
            i, j = key // n, key % n
        else:
            i, j = np.nonzero(np.triu(dist < L.links, 1))
        strength = (1 - dist[i, j] / L.links) * L.link_brightness
        if L.link_reveal > 0:
            mid = (P[i] + P[j]) / 2
            strength = strength * np.clip(1.5 * (1 - np.hypot(*(mid - m).T) / L.link_reveal), 0, 1)
            keep = strength > 0.01
            i, j, strength = i[keep], j[keep], strength[keep]
        budget = max(50, MAX_LINKS // len(self.copies(P[:1])))
        if len(i) > budget:
            keep = np.argsort(-strength)[:budget]
            i, j, strength = i[keep], j[keep], strength[keep]
        a_pts, b_pts = P[i], P[j]
        cols = (C[i] if C.ndim == 2 else np.broadcast_to(C, (len(i), 3))) * strength[:, None]
        if L.link_mouse:
            dm = np.hypot(*(P - m).T)
            near = np.flatnonzero(dm < L.links * 1.4)
            s2 = (1 - dm[near] / (L.links * 1.4)) * L.link_brightness * 1.2
            a_pts = np.vstack([a_pts, np.repeat(m[None, :], len(near), 0)])
            b_pts = np.vstack([b_pts, P[near]])
            cm = (C[near] if C.ndim == 2 else np.broadcast_to(C, (len(near), 3))) * s2[:, None]
            cols = np.vstack([cols, cm])
        if not len(a_pts):
            return
        cols = np.clip(cols, 0, 255).astype(int)
        line = pygame.draw.aaline
        for A, B in zip(self.copies(a_pts), self.copies(b_pts)):
            for (x1, y1), (x2, y2), c in zip(A, B, cols):
                line(self.screen, c, (x1, y1), (x2, y2))

    def _scent(self, swarm: Swarm, col):
        """The slime's scent map itself, as a soft glow (tone mapped, scaled up smoothly)."""
        L = swarm.layer
        T = swarm.scent
        g = max(1, int(L.slime_cell))
        k = np.float32(L.slime_show * 0.1 / max(L.slime_deposit, 1e-6))
        v = 1.0 - np.exp(-np.maximum(T, 0) * k)
        tint = (col if col.ndim == 1 else col.mean(axis=0)).astype(np.float32)
        vt = v.T[:, :, None]                      # the busiest veins burn toward white
        img = np.minimum(vt * tint + (vt ** 4) * (255 - tint) * 0.4, 255).astype(np.uint8)
        surf = pygame.surfarray.make_surface(img)
        gh, gw = T.shape
        surf = pygame.transform.smoothscale(surf, (gw * g, gh * g))
        self.screen.blit(surf, (0, 0), special_flags=pygame.BLEND_RGB_ADD)

    def _arms(self, swarm: Swarm, col):
        """The rods of a few of the double pendulums."""
        L = swarm.layer
        W, H = self.world
        n = len(swarm)
        idx = np.unique(np.linspace(0, n - 1, min(L.pend_arms, n)).astype(int))
        piv = np.repeat(np.array([[L.pend_pivot[0] * W, L.pend_pivot[1] * H]]), len(idx), 0)
        joint, tip = swarm.joint[idx], swarm.pos[idx]
        c = col[idx] if col.ndim == 2 else np.broadcast_to(col, (len(idx), 3))
        c = np.clip(c * 0.8 + 30, 0, 255).astype(int)
        for P, J, T in zip(self.copies(piv), self.copies(joint), self.copies(tip)):
            for p, j, tt, cc in zip(P, J, T, c):
                pygame.draw.aaline(self.screen, cc, p, j)
                pygame.draw.aaline(self.screen, cc, j, tt)
                pygame.draw.circle(self.screen, cc, j, 3)
            pygame.draw.circle(self.screen, (200, 200, 210), P[0], 3)

    def _paint(self, swarm: Swarm):
        L, p = swarm.layer, self.p
        extras = L.links > 0 or (L.motion == "slime" and L.slime_show > 0) or \
            (L.motion == "pendulum" and L.pend_arms > 0)
        if not len(swarm) or (L.look == "none" and not extras):
            return
        base = self.dark * p.brightness * L.brightness
        col = swarm.colors()
        light = swarm.light(base)
        additive = p.blend == "add"
        paper = np.asarray(p.background, float)
        if additive or paper.sum() < 384:
            paper = np.zeros(3)             # on a dark screen, faint = dark
        if light is not None:               # on paper, faint = closer to the paper colour
            col = paper + ((col if col.ndim == 2 else np.broadcast_to(col, (len(swarm), 3))) - paper) * light[:, None]
        else:
            col = paper + (col - paper) * base
        col = np.clip(col, 0, 255)
        if L.links > 0:
            self._links(swarm, col)
        if L.motion == "pendulum" and L.pend_arms > 0 and swarm.joint is not None:
            self._arms(swarm, col)
        if L.motion == "slime" and L.slime_show > 0 and swarm.scent is not None:
            self._scent(swarm, col)

        if L.look == "none":
            return
        if light is not None and L.motion == "grow":    # skip the invisible waiting walkers
            show = light > 0
            pos, col = swarm.pos[show], col[show]
        else:
            pos = swarm.pos
        if not len(pos):
            return

        if L.look == "dot":
            flags = pygame.BLEND_RGB_ADD if additive else 0
            if col.ndim == 1:
                groups = [(swarm.sprite(col, additive), None)]
            else:                                        # one sprite per tint (16 levels a channel)
                q = col.astype(np.int64) >> 4
                key = (q[:, 0] << 8) | (q[:, 1] << 4) | q[:, 2]
                keys, inv = np.unique(key, return_inverse=True)
                inv = inv.ravel()
                order = np.argsort(inv, kind="stable")
                parts = np.split(order, np.cumsum(np.bincount(inv, minlength=len(keys)))[:-1])
                groups = [(swarm.sprite(np.array([(k >> 8) & 15, (k >> 4) & 15, k & 15]) * 16, additive), idx)
                          for k, idx in zip(keys.tolist(), parts)]
            jobs = []
            for xy in self.copies(pos):
                for (spr, o), idx in groups:
                    pts = ((xy if idx is None else xy[idx]) - o).tolist()
                    if flags:
                        jobs += [(spr, p, None, flags) for p in pts]
                    else:
                        jobs += [(spr, p) for p in pts]
            self.screen.blits(jobs, doreturn=False)
            return

        W, H = self.world
        px = pygame.surfarray.pixels3d(self.screen)
        s = max(1, min(4, int(L.size)))
        add = col * p.glow if additive else col.astype(np.uint8)
        for xy in self.copies(pos):
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
