// The simulation, ported from engine.py: forces, swarms, text, crystals, slime mould,
// 3D attractors, pendulums. No drawing in here (see render.js).
(function () {
"use strict";
const DU = (window.DU = window.DU || {});
const TAU = Math.PI * 2;
const FPS = 60;
const MAX_LINK_BODIES = 700;
const MAX_LINKS = 4000;
const DATA = window.DU_DATA;
const MAX_PAIRS = (DATA && DATA.max_pairs) || 600000;

// ------------------------------------------------------------------ random numbers

function makeRng(seed) {
  let s = seed >>> 0 || 0x2545f491;
  function random() {                                  // mulberry32
    s = (s + 0x6d2b79f5) | 0;
    let t = Math.imul(s ^ (s >>> 15), 1 | s);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  }
  let spare = null;
  function normal(mu, sigma) {
    let z;
    if (spare !== null) { z = spare; spare = null; }
    else {
      let u = 0;
      while (u === 0) u = random();
      const v = random(), m = Math.sqrt(-2 * Math.log(u));
      z = m * Math.cos(TAU * v);
      spare = m * Math.sin(TAU * v);
    }
    return (mu || 0) + (sigma === undefined ? 1 : sigma) * z;
  }
  return { random, normal, int: (n) => Math.floor(random() * n) };
}

// ------------------------------------------------------------------ fast trigonometry (flow fields, maps)

const SN = 4096, SIN = new Float64Array(SN + 1);
for (let i = 0; i <= SN; i++) SIN[i] = Math.sin(i * TAU / SN);
const S_SCALE = SN / TAU, QUARTER = SN / 4;
/** sin(x) from a 4096-step table with linear interpolation (error ~3e-7) */
function fsin(x) {
  const t = x * S_SCALE, f = Math.floor(t), i = f & (SN - 1), r = t - f;
  return SIN[i] + (SIN[i + 1] - SIN[i]) * r;
}
function fcos(x) {
  const t = x * S_SCALE + QUARTER, f = Math.floor(t), i = f & (SN - 1), r = t - f;
  return SIN[i] + (SIN[i + 1] - SIN[i]) * r;
}

// ------------------------------------------------------------------ presets as data

function clone(o) {
  return JSON.parse(JSON.stringify(o, (k, v) => (v === Infinity ? null : v)));
}

/** Fill in every missing field with its default (presets saved by older versions, hand-written JSON). */
function normalise(p) {
  const D = DATA.defaults;
  p = clone(p || {});
  const out = Object.assign(clone(D.preset), p);
  for (const sub of ["palette", "flow", "attractor", "flow3d"]) out[sub] = Object.assign(clone(D.preset[sub]), p[sub] || {});
  out.layers = (p.layers || []).map((L) => {
    const l = Object.assign(clone(D.layer), L);
    l.count = Math.max(0, Math.floor(+l.count || 0));
    l.pulls = (L.pulls || []).map((pl) => {
      const f = Object.assign(clone(D.field), pl.field || {});
      if (f.max_dist === null || f.max_dist === undefined) f.max_dist = Infinity;
      return { source: ["above", "mouse", "center"].includes(pl.source) ? pl.source : "above",
               enabled: pl.enabled !== false, field: f };
    });
    return l;
  });
  return out;
}

/** JSON-safe copy (Infinity -> null), the same format the desktop app saves. */
function toPlain(p) { return clone(p); }

// ------------------------------------------------------------------ colour

function hsvInto(h, s, v, out, o) {
  let h6 = ((h % 360) + 360) % 360 / 60;
  const i = Math.floor(h6) % 6, f = h6 - Math.floor(h6);
  const p = v * (1 - s), q = v * (1 - s * f), t = v * (1 - s * (1 - f));
  let r, g, b;
  switch (i) {
    case 0: r = v; g = t; b = p; break;
    case 1: r = q; g = v; b = p; break;
    case 2: r = p; g = v; b = t; break;
    case 3: r = p; g = q; b = v; break;
    case 4: r = t; g = p; b = v; break;
    default: r = v; g = p; b = q;
  }
  out[o] = r * 255; out[o + 1] = g * 255; out[o + 2] = b * 255;
}

const LUTS = new Map();
/** 360-step hue table at one saturation / value (like hue_colors in engine.py). */
function hueLut(s, v) {
  const key = Math.round(s * 1000) + ":" + Math.round(v * 1000);
  let lut = LUTS.get(key);
  if (!lut) {
    if (LUTS.size > 32) LUTS.clear();
    lut = new Float32Array(360 * 3);
    for (let h = 0; h < 360; h++) hsvInto(h, s, v, lut, h * 3);
    LUTS.set(key, lut);
  }
  return lut;
}
function lutIndex(h) { const k = Math.trunc(h) % 360; return (k < 0 ? k + 360 : k) * 3; }

// ------------------------------------------------------------------ forces

function pulseFactor(f, t) {
  if (!f.pulse) return 1;
  return 1 + f.pulse * Math.sin(TAU * (t / Math.max(f.period, 1e-3) + f.phase));
}

/** Add the pull of one source body onto every body of a swarm (ax, ay). */
function pullInto(sw, sx, sy, svx, svy, f, scale, ringR, ax, ay) {
  const n = sw.n, px = sw.px, py = sw.py, vx = sw.vx, vy = sw.vy;
  const g = f.strength * scale, minD = f.min_dist, maxD = f.max_dist, law = f.law;
  if (law === "drag" || law === "wake" || law === "startle") {
    const finite = isFinite(maxD), speed = Math.hypot(svx, svy);
    for (let i = 0; i < n; i++) {
      const dx = sx - px[i], dy = sy - py[i];
      const r = Math.sqrt(dx * dx + dy * dy);
      if (!(r >= minD && r < maxD && r > 0)) continue;
      const w = finite ? Math.min(1, Math.max(0, 1 - r / maxD)) : 1;
      if (law === "drag") { const k = g / 100 * w; ax[i] += (svx - vx[i]) * k; ay[i] += (svy - vy[i]) * k; }
      else if (law === "wake") { const k = g / 100 * w; ax[i] += svx * k; ay[i] += svy * k; }
      else { const k = g * speed * w / r; ax[i] -= dx * k; ay[i] -= dy * k; }   // startle: away
    }
  } else if (law === "ring") {
    for (let i = 0; i < n; i++) {
      const dx = sx - px[i], dy = sy - py[i];
      const r = Math.sqrt(dx * dx + dy * dy);
      if (!(r >= minD && r < maxD && r > 0)) continue;
      const k = g / 1000 * (r - ringR) / r;
      ax[i] += dx * k; ay[i] += dy * k;
    }
  } else {
    const p1 = f.power + 1, inner = f.inner_radius, gi = f.inner_gain, go = f.outer_gain;
    const vortex = law === "vortex", newton1 = f.power === 1;
    for (let i = 0; i < n; i++) {
      const dx = sx - px[i], dy = sy - py[i];
      const r2 = dx * dx + dy * dy, r = Math.sqrt(r2);
      if (!(r >= minD && r < maxD && r > 0)) continue;
      const gain = inner > 0 ? (r < inner ? gi : go) : go;
      const k = newton1 ? g * gain / r2 : g * gain / Math.pow(r, p1);
      if (vortex) { ax[i] -= dy * k; ay[i] += dx * k; }
      else { ax[i] += dx * k; ay[i] += dy * k; }
    }
  }
}

const OCTAVES = [[1.0, 1.0, 0.31, 0.0], [1.37, 0.85, 1.29, 1.7], [2.11, 0.6, 2.47, 4.1], [3.3, 0.35, 0.83, 2.6]];
/** Curl of a moving stream function: swirls that never pile up. Adds gain * flow onto ax, ay. */
function flowInto(sw, cfg, t, gain, ax, ay) {
  const n = sw.n, px = sw.px, py = sw.py;
  const s0 = cfg.strength / 2.8 * gain;
  for (const [octave, weight, angle, ph] of OCTAVES) {
    const c = Math.cos(angle), s = Math.sin(angle);
    const k = TAU * octave / Math.max(cfg.scale, 1);
    const kc = k * c, ks = k * s;
    const pa = t * cfg.speed * octave + ph, pb = t * cfg.speed * 0.73 * octave - ph;
    const w = weight * s0;
    for (let i = 0; i < n; i++) {
      const x = px[i], y = py[i];
      const a = kc * x + ks * y + pa, b = -ks * x + kc * y + pb;
      const fu = fsin(a) * fcos(b), fv = -fcos(a) * fsin(b);
      ax[i] += w * (c * fu - s * fv);
      ay[i] += w * (s * fu + c * fv);
    }
  }
}

/** One step of the slowly morphing Clifford / de Jong map, blended toward. */
function attractorStep(sw, cfg, t, W, H, cx, cy, blend) {
  const ph = TAU * t * cfg.morph_speed, m = cfg.morph;
  const a = cfg.a + m * Math.sin(ph), b = cfg.b + m * Math.sin(1.31 * ph + 1.0);
  const c = cfg.c + m * Math.sin(0.77 * ph + 2.0), d = cfg.d + m * Math.sin(1.13 * ph + 3.0);
  const R = cfg.scale * Math.min(W, H) / 2;
  const dejong = cfg.kind === "dejong";
  const ex = dejong ? 2 : 1 + Math.abs(c), ey = dejong ? 2 : 1 + Math.abs(d);
  const n = sw.n, px = sw.px, py = sw.py, vx = sw.vx, vy = sw.vy;
  for (let i = 0; i < n; i++) {
    const u = (px[i] - cx) / R * ex, v = (py[i] - cy) / R * ey;
    let u2, v2;
    if (dejong) { u2 = fsin(a * v) - fcos(b * u); v2 = fsin(c * u) - fcos(d * v); }
    else { u2 = fsin(a * v) + c * fcos(a * u); v2 = fsin(b * u) + d * fcos(b * v); }
    const tx = cx + u2 / ex * R, ty = cy + v2 / ey * R;
    px[i] += blend * (tx - px[i]) + vx[i];
    py[i] += blend * (ty - py[i]) + vy[i];
  }
}

// ------------------------------------------------------------------ 3D flows

const B_THOMAS = 0.208186, A_HALV = 1.89;
const FLOWS_3D = {
  // derivative into o[k..k+2], time step per sub-step, centre, radius, a point on it, best side (yaw)
  lorenz: { f: (x, y, z, o, k) => { o[k] = 10 * (y - x); o[k + 1] = x * (28 - z) - y; o[k + 2] = x * y - 8 / 3 * z; },
            dt: 0.004, c: [0, 0, 24.5], r: 31.0, p: [4.6374, 4.5937, 22.5697], yaw: -45 },
  aizawa: { f: (x, y, z, o, k) => { const zb = z - 0.7; o[k] = zb * x - 3.5 * y; o[k + 1] = 3.5 * x + zb * y;
                                    o[k + 2] = 0.6 + 0.95 * z - z * z * z / 3 - (x * x + y * y) * (1 + 0.25 * z) + 0.1 * z * x * x * x; },
            dt: 0.01, c: [0, 0, 0.746], r: 1.52, p: [-0.0815, 1.2248, 0.1169], yaw: 0 },
  thomas: { f: (x, y, z, o, k) => { o[k] = Math.sin(y) - B_THOMAS * x; o[k + 1] = Math.sin(z) - B_THOMAS * y; o[k + 2] = Math.sin(x) - B_THOMAS * z; },
            dt: 0.045, c: [1.357, 1.357, 1.357], r: 3.52, p: [3.1171, 2.8729, 1.2847], yaw: 0 },
  halvorsen: { f: (x, y, z, o, k) => { o[k] = -A_HALV * x - 4 * y - 4 * z - y * y; o[k + 1] = -A_HALV * y - 4 * z - 4 * x - z * z;
                                       o[k + 2] = -A_HALV * z - 4 * x - 4 * y - x * x; },
               dt: 0.004, c: [-2.909, -2.909, -2.909], r: 12.7, p: [-1.1658, -5.114, -9.0167], yaw: 0 },
  rossler: { f: (x, y, z, o, k) => { o[k] = -y - z; o[k + 1] = x + 0.2 * y; o[k + 2] = 0.2 + z * (x - 5.7); },
             dt: 0.02, c: [1.127, -1.462, 10.472], r: 15.0, p: [-2.3354, 7.6668, 0.042], yaw: 0 },
};

const K = new Float64Array(12);
function rk4Point(f, P, i, dt) {
  const x = P[i], y = P[i + 1], z = P[i + 2];
  f(x, y, z, K, 0);
  f(x + dt / 2 * K[0], y + dt / 2 * K[1], z + dt / 2 * K[2], K, 3);
  f(x + dt / 2 * K[3], y + dt / 2 * K[4], z + dt / 2 * K[5], K, 6);
  f(x + dt * K[6], y + dt * K[7], z + dt * K[8], K, 9);
  P[i] = x + dt / 6 * (K[0] + 2 * K[3] + 2 * K[6] + K[9]);
  P[i + 1] = y + dt / 6 * (K[1] + 2 * K[4] + 2 * K[7] + K[10]);
  P[i + 2] = z + dt / 6 * (K[2] + 2 * K[5] + 2 * K[8] + K[11]);
}

/** d/dt of a double pendulum [th1, w1, th2, w2] (m1 = l1 = 1, angles from straight down). */
function pendRate(th1, w1, th2, w2, m2, l2, g, o, k) {
  const d = th1 - th2, sd = Math.sin(d), cd = Math.cos(d);
  const den = 2 + m2 - m2 * Math.cos(2 * d);
  o[k] = w1;
  o[k + 1] = (-g * (2 + m2) * Math.sin(th1) - m2 * g * Math.sin(th1 - 2 * th2)
              - 2 * sd * m2 * (w2 * w2 * l2 + w1 * w1 * cd)) / den;
  o[k + 2] = w2;
  o[k + 3] = 2 * sd * (w1 * w1 * (1 + m2) + g * (1 + m2) * Math.cos(th1) + w2 * w2 * l2 * m2 * cd) / (l2 * den);
}

// ------------------------------------------------------------------ text

// the browser falls back glyph by glyph, so one stack serves Latin and CJK text alike
const SANS = '"Helvetica Neue",Helvetica,Arial,"PingFang SC","Hiragino Sans GB","Microsoft YaHei","Noto Sans CJK SC",sans-serif';
const SERIF = 'Baskerville,"Baskerville Old Face","Palatino Linotype",Palatino,"Book Antiqua",Georgia,"Times New Roman",' +
              '"Songti SC","STSong","Noto Serif CJK SC",serif';
const MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October",
                "November", "December"];
const WEEKDAYS = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"];

/** The text of one page (pages are separated by |), with the clock filled in. */
function expandText(template, page = 0, now) {
  const pages = template ? template.split("|") : [""];
  let line = pages[page % pages.length];
  if (line.includes("{")) {
    now = now || new Date();
    const p2 = (v) => String(v).padStart(2, "0");
    const hh = p2(now.getHours()), mm = p2(now.getMinutes()), ss = p2(now.getSeconds());
    line = line.split("{seconds}").join(`${hh}:${mm}:${ss}`).split("{time}").join(`${hh}:${mm}`)
      .split("{date}").join(`${MONTHS[now.getMonth()]} ${now.getDate()}`)
      .split("{weekday}").join(WEEKDAYS[now.getDay()]);
  }
  return line.split("\\n").join("\n");
}

/** The layer's own fonts (the desktop's system names, quoted) ahead of a sans or serif stack. */
function fontStack(fonts) {
  const own = (fonts || "").split(",").map((s) => s.trim()).filter(Boolean);
  const serif = own.some((f) => /song|serif|kai|ming|baskerville|palatino|georgia|times|garamond|hoefler/i.test(f));
  return [...own.map((f) => JSON.stringify(f)), serif ? SERIF : SANS].join(",");
}

let textCanvas = null;
/** n points spread over the pixels of `text`, centred at `pos` (screen fractions). */
function textPoints(text, n, W, H, size, pos, fonts, rng) {
  const lines = text.split("\n");
  const stack = fontStack(fonts);
  textCanvas = textCanvas || document.createElement("canvas");
  const ctx = textCanvas.getContext("2d", { willReadFrequently: true });
  let px = Math.max(8, Math.floor(size * H)), w = 1, lh = 1, h = 1;
  for (let tries = 0; tries < 4; tries++) {                // shrink until it fits the screen
    ctx.font = `${px}px ${stack}`;
    w = Math.max(1, ...lines.map((l) => Math.ceil(ctx.measureText(l || " ").width)));
    lh = Math.ceil(px * 1.3);
    h = lh * lines.length;
    const fit = Math.min(0.92 * W / w, 0.9 * H / h);
    if (fit >= 1) break;
    px = Math.max(8, Math.floor(px * fit * 0.98));
  }
  textCanvas.width = w; textCanvas.height = h;
  ctx.font = `${px}px ${stack}`;
  ctx.fillStyle = "#fff"; ctx.textAlign = "center"; ctx.textBaseline = "middle";
  lines.forEach((l, i) => ctx.fillText(l, w / 2, lh * (i + 0.5)));
  const img = ctx.getImageData(0, 0, w, h).data;
  const on = [];
  for (let y = 0; y < h; y++) for (let x = 0; x < w; x++) if (img[(y * w + x) * 4 + 3] > 127) on.push(x, y);
  if (!on.length) on.push(w >> 1, h >> 1);
  const m = on.length / 2, out = new Float64Array(n * 2);
  const ox = pos[0] * W - w / 2, oy = pos[1] * H - h / 2;
  let pick;
  if (n <= m) {                                            // without replacement: partial shuffle
    const idx = new Int32Array(m);
    for (let i = 0; i < m; i++) idx[i] = i;
    for (let i = 0; i < n; i++) { const j = i + rng.int(m - i); const t = idx[i]; idx[i] = idx[j]; idx[j] = t; }
    pick = (i) => idx[i];
  } else pick = () => rng.int(m);
  for (let i = 0; i < n; i++) {
    const k = pick(i);
    out[2 * i] = on[2 * k] + rng.random() + ox;
    out[2 * i + 1] = on[2 * k + 1] + rng.random() + oy;
  }
  return out;
}

// ------------------------------------------------------------------ neighbourhoods

/** Pressure and alignment from a density grid, added onto ax, ay. */
function neighbourhoodInto(sw, W, H, cell, pressure, align, ax, ay) {
  cell = Math.max(2, Math.floor(cell));
  const gw = Math.max(1, Math.ceil(W / cell)), gh = Math.max(1, Math.ceil(H / cell)), G = gw * gh;
  const n = sw.n, px = sw.px, py = sw.py, vx = sw.vx, vy = sw.vy;
  const idx = new Int32Array(n), cnt = new Float64Array(G);
  for (let i = 0; i < n; i++) {
    const cx = Math.min(gw - 1, Math.max(0, Math.floor(px[i] / cell)));
    const cy = Math.min(gh - 1, Math.max(0, Math.floor(py[i] / cell)));
    idx[i] = cy * gw + cx; cnt[idx[i]]++;
  }
  if (pressure) {
    // log density: a cell holding the whole swarm must not launch it into orbit
    const mean = Math.max(n / G, 1e-9), d0 = new Float64Array(G), dens = new Float64Array(G);
    for (let j = 0; j < G; j++) d0[j] = Math.log1p(cnt[j] / mean);
    for (let y = 0; y < gh; y++) for (let x = 0; x < gw; x++) {         // 3 x 3 blur, edge padded
      let s = 0;
      for (let dy = -1; dy <= 1; dy++) {
        const yy = Math.min(gh - 1, Math.max(0, y + dy));
        for (let dx = -1; dx <= 1; dx++) s += d0[yy * gw + Math.min(gw - 1, Math.max(0, x + dx))];
      }
      dens[y * gw + x] = s / 9;
    }
    const gx = new Float64Array(G), gy = new Float64Array(G);           // like np.gradient
    for (let y = 0; y < gh; y++) for (let x = 0; x < gw; x++) {
      const j = y * gw + x;
      if (gw > 1) gx[j] = x === 0 ? dens[j + 1] - dens[j] : x === gw - 1 ? dens[j] - dens[j - 1] : (dens[j + 1] - dens[j - 1]) / 2;
      if (gh > 1) gy[j] = y === 0 ? dens[j + gw] - dens[j] : y === gh - 1 ? dens[j] - dens[j - gw] : (dens[j + gw] - dens[j - gw]) / 2;
    }
    for (let i = 0; i < n; i++) {
      const fx = px[i] / cell - 0.5, fy = py[i] / cell - 0.5;
      const x0 = Math.floor(fx), y0 = Math.floor(fy), tx = fx - x0, ty = fy - y0;
      const xa = Math.min(gw - 1, Math.max(0, x0)), xb = Math.min(gw - 1, Math.max(0, x0 + 1));
      const ya = Math.min(gh - 1, Math.max(0, y0)), yb = Math.min(gh - 1, Math.max(0, y0 + 1));
      const bx = (gx[ya * gw + xa] * (1 - tx) + gx[ya * gw + xb] * tx) * (1 - ty) + (gx[yb * gw + xa] * (1 - tx) + gx[yb * gw + xb] * tx) * ty;
      const by = (gy[ya * gw + xa] * (1 - tx) + gy[ya * gw + xb] * tx) * (1 - ty) + (gy[yb * gw + xa] * (1 - tx) + gy[yb * gw + xb] * tx) * ty;
      ax[i] += Math.min(3, Math.max(-3, -pressure * bx));
      ay[i] += Math.min(3, Math.max(-3, -pressure * by));
    }
  }
  if (align) {
    const mx = new Float64Array(G), my = new Float64Array(G);
    for (let i = 0; i < n; i++) { mx[idx[i]] += vx[i]; my[idx[i]] += vy[i]; }
    for (let i = 0; i < n; i++) {
      const c = Math.max(cnt[idx[i]], 1);
      ax[i] += align * (mx[idx[i]] / c - vx[i]);
      ay[i] += align * (my[idx[i]] / c - vy[i]);
    }
  }
}

// ------------------------------------------------------------------ the cursor

class Mouse {
  /** read() -> [x, y, pressed] in world coordinates */
  constructor(read) {
    this.read = read; this.x = 0; this.y = 0; this.vx = 0; this.vy = 0;
    this.pressed = false; this.clicked = false; this.first = true;
  }
  update() {
    const [x, y, pressed] = this.read();
    this.clicked = !!pressed && !this.pressed;
    this.pressed = !!pressed;
    if (this.first) { this.x = x; this.y = y; this.first = false; }
    this.vx = 0.5 * this.vx + 0.5 * (x - this.x);            // smoothed, px / frame
    this.vy = 0.5 * this.vy + 0.5 * (y - this.y);
    this.x = x; this.y = y;
  }
}

// ------------------------------------------------------------------ swarms

const PER_BODY = ["px", "py", "vx", "vy", "hx", "hy", "age", "life", "hueSeed", "seed2", "birthHue"];

class Swarm {
  constructor(layer, uni) {
    this.layer = layer; this.uni = uni; this.rng = uni.rng; this.n = 0;
    for (const k of PER_BODY) this[k] = new Float64Array(0);
    this.textKey = null; this.crystal = null; this.scent = null; this.scentW = 0; this.scentH = 0;
    this.p3 = null; this.p3Kind = null; this.depth = null; this.view = null;
    this.pend = null; this.pendRelease = null; this.jx = null; this.jy = null; this.pathU = null;
    this.ax = new Float64Array(0); this.ay = new Float64Array(0);
    this.resize(layer.count, true);
    if (layer.motion === "path") { this.followPath(uni.t); this.vx.fill(0); this.vy.fill(0); }
  }

  hueNow() { const pal = this.uni.p.palette; return pal.hue + pal.hue_speed * this.uni.t; }

  // -- birth
  parents(n) {
    const u = this.uni, L = this.layer, rng = this.rng;
    const o = { x: new Float64Array(n), y: new Float64Array(n), vx: new Float64Array(n), vy: new Float64Array(n), k: new Int32Array(n) };
    if (L.spawn === "above" || L.spawn === "above_ring") {
      const s = u.sourceArrays(this, "above");
      if (s.n) {
        for (let i = 0; i < n; i++) { const k = rng.int(s.n); o.x[i] = s.x[k]; o.y[i] = s.y[k]; o.vx[i] = s.vx[k]; o.vy[i] = s.vy[k]; o.k[i] = k; }
        return o;
      }
    }
    if (L.spawn === "mouse" || L.spawn === "mouse_ring") {
      o.x.fill(u.mouse.x); o.y.fill(u.mouse.y); o.vx.fill(u.mouse.vx); o.vy.fill(u.mouse.vy);
    } else { o.x.fill(u.cx); o.y.fill(u.cy); }
    return o;
  }

  /** Positions, velocities and birth hues for n newborns (at a point, if given). */
  spawn(n, fresh, at) {
    const L = this.layer, rng = this.rng, [W, H] = this.uni.world;
    const P = this.parents(n);
    const x = new Float64Array(n), y = new Float64Array(n), vx = new Float64Array(n), vy = new Float64Array(n), hue = new Float64Array(n);
    if (at) { P.x.fill(at[0]); P.y.fill(at[1]); P.vx.fill(0); P.vy.fill(0); }
    const sp = at ? "at" : L.spawn;
    if (sp === "at" || sp === "center" || sp === "mouse" || sp === "above") { x.set(P.x); y.set(P.y); }
    else if (sp === "edges") {
      for (let i = 0; i < n; i++) {
        const t = rng.random() * 2 * (W + H);
        if (t < W) { x[i] = t; y[i] = 0; } else if (t < W + H) { x[i] = W; y[i] = t - W; }
        else if (t < 2 * W + H) { x[i] = t - W - H; y[i] = H; } else { x[i] = 0; y[i] = t - 2 * W - H; }
      }
    } else if (sp === "grid") {
      const total = Math.max(L.count, n), cols = Math.max(1, Math.round(Math.sqrt(total * W / H)));
      const rows = Math.ceil(total / cols);
      for (let i = 0; i < n; i++) {
        const j = fresh ? i : rng.int(total);
        x[i] = (j % cols + 0.5) * W / cols; y[i] = (Math.floor(j / cols) + 0.5) * H / rows;
      }
    } else if (sp === "circle" || sp === "above_ring" || sp === "mouse_ring") {
      for (let i = 0; i < n; i++) {
        const a = rng.random() * TAU, r = L.spawn_radius + rng.normal(0, L.spawn_spread);
        x[i] = P.x[i] + Math.cos(a) * r; y[i] = P.y[i] + Math.sin(a) * r;
      }
    } else {                                                // random, text (flies in to its glyph)
      for (let i = 0; i < n; i++) { x[i] = rng.random() * W; y[i] = rng.random() * H; }
    }
    const s = L.start_speed, mode = L.velocity, h0 = this.hueNow();
    for (let i = 0; i < n; i++) {
      const rx = x[i] - P.x[i], ry = y[i] - P.y[i], dist = Math.sqrt(rx * rx + ry * ry);
      let ux, uy;
      if (dist > 1e-6) { ux = rx / dist; uy = ry / dist; } else { const a = rng.random() * TAU; ux = Math.cos(a); uy = Math.sin(a); }
      if (mode === "zero") { vx[i] = 0; vy[i] = 0; }
      else if (mode === "orbit") { vx[i] = -uy * s + P.vx[i]; vy[i] = ux * s + P.vy[i]; }
      else if (mode === "outward") { const m = s * (0.3 + 0.7 * rng.random()); vx[i] = ux * m + P.vx[i]; vy[i] = uy * m + P.vy[i]; }
      else if (mode === "sphere") {                         // a 3D shell bursting, seen head-on: bright rim
        const a = rng.random() * TAU, c = rng.random() * 2 - 1;
        const m = s * Math.sqrt(1 - c * c) * (0.93 + 0.07 * rng.random());
        vx[i] = Math.cos(a) * m + P.vx[i]; vy[i] = Math.sin(a) * m + P.vy[i];
      } else {
        const a = rng.random() * TAU, m = s * Math.sqrt(rng.random());
        vx[i] = Math.cos(a) * m; vy[i] = Math.sin(a) * m;
        if (mode === "inherit") { vx[i] += P.vx[i]; vy[i] += P.vy[i]; }
      }
      hue[i] = h0 + 137.508 * P.k[i] + rng.normal(0, 6);   // each parent its own colour, golden-angle apart
    }
    return { x, y, vx, vy, hue };
  }

  lives(k) {
    const L = this.layer, out = new Float64Array(k);
    if (L.life <= 0) { out.fill(Infinity); return out; }
    for (let i = 0; i < k; i++) out[i] = Math.max(1, L.life * (1 + L.life_jitter * (2 * this.rng.random() - 1)));
    return out;
  }

  resize(n, fresh) {
    n = Math.max(0, Math.floor(n));
    const old = this.n;
    if (n === old) return;
    const keep = Math.min(n, old);
    for (const k of PER_BODY) { const a = new Float64Array(n); a.set(this[k].subarray(0, keep)); this[k] = a; }
    this.ax = new Float64Array(n); this.ay = new Float64Array(n);
    this.n = n;
    if (n > old) {
      const k = n - old, L = this.layer;
      const s = this.spawn(k, fresh && old === 0), lives = this.lives(k);
      for (let i = 0; i < k; i++) {
        const j = old + i;
        this.px[j] = this.hx[j] = s.x[i]; this.py[j] = this.hy[j] = s.y[i];
        this.vx[j] = s.vx[i]; this.vy[j] = s.vy[i];
        this.life[j] = lives[i];
        this.age[j] = L.life > 0 && L.life_jitter > 0 ? this.rng.random() * lives[i] : 0;   // staggered
        this.hueSeed[j] = this.rng.random(); this.seed2[j] = this.rng.random(); this.birthHue[j] = s.hue[i];
      }
    }
    this.textKey = null; this.crystal = null; this.p3 = null; this.pend = null;
  }

  /** idx: indices of the bodies to be born again */
  reborn(idx) {
    const k = idx.length;
    if (!k) return;
    if (this.p3) this.reborn3d(idx);
    if (this.pend) {
      const st = this.pendStart(idx);
      for (let i = 0; i < k; i++) for (let c = 0; c < 4; c++) this.pend[idx[i] * 4 + c] = st[i * 4 + c];
    }
    const s = this.spawn(k), lives = this.lives(k), text = this.layer.spawn === "text";
    for (let i = 0; i < k; i++) {
      const j = idx[i];
      this.px[j] = s.x[i]; this.py[j] = s.y[i]; this.vx[j] = s.vx[i]; this.vy[j] = s.vy[i];
      if (!text) { this.hx[j] = s.x[i]; this.hy[j] = s.y[i]; }   // text bodies keep flying to their glyph
      this.birthHue[j] = s.hue[i]; this.age[j] = 0; this.life[j] = lives[i];
    }
  }

  /** A click: the n oldest bodies are reborn at `pt`, in one colour. */
  burstAt(pt, n) {
    n = Math.min(Math.floor(n), this.n);
    if (n <= 0) return;
    const ratio = new Float64Array(this.n);
    for (let i = 0; i < this.n; i++) ratio[i] = this.age[i] / (isFinite(this.life[i]) ? this.life[i] : 1e9) + this.rng.random() * 1e-6;
    const order = Array.from({ length: this.n }, (_, i) => i).sort((a, b) => ratio[a] - ratio[b]);
    const idx = order.slice(this.n - n), s = this.spawn(n, false, pt), lives = this.lives(n), h0 = this.hueNow();
    for (let i = 0; i < n; i++) {
      const j = idx[i];
      this.px[j] = this.hx[j] = s.x[i]; this.py[j] = this.hy[j] = s.y[i];
      this.vx[j] = s.vx[i]; this.vy[j] = s.vy[i];
      this.birthHue[j] = h0 + this.rng.normal(0, 6); this.age[j] = 0; this.life[j] = lives[i];
    }
  }

  /** Lifetime settings changed in the panel. */
  relife() {
    const L = this.layer;
    if (L.life <= 0) { this.life.fill(Infinity); return; }
    let finite = true;
    for (let i = 0; i < this.n; i++) if (!isFinite(this.life[i])) { finite = false; break; }
    const sorted = Float64Array.from(this.life).sort();
    const median = this.n ? sorted[this.n >> 1] : L.life;
    if (!finite || Math.abs(median - L.life) > 0.5) {
      this.life = this.lives(this.n);
      for (let i = 0; i < this.n; i++) this.age[i] = Math.min(this.age[i], this.life[i] - 1);
    }
  }

  // -- text
  retarget(text) {
    const L = this.layer, n = this.n, [W, H] = this.uni.world;
    const pts = textPoints(text, n, W, H, L.text_size, L.text_pos, L.text_font, this.rng);
    // pair bodies and pixels left-to-right (with a little noise): the swarm sweeps sideways
    const keyB = new Float64Array(n);
    for (let i = 0; i < n; i++) keyB[i] = this.px[i] + this.rng.normal(0, 25);
    const ob = Array.from({ length: n }, (_, i) => i).sort((a, b) => keyB[a] - keyB[b]);
    const ot = Array.from({ length: n }, (_, i) => i).sort((a, b) => pts[2 * a] - pts[2 * b]);
    for (let i = 0; i < n; i++) { this.hx[ob[i]] = pts[2 * ot[i]]; this.hy[ob[i]] = pts[2 * ot[i] + 1]; }
    this.textKey = text;
  }

  // -- crystal growth (diffusion-limited aggregation)
  crystalReset() {
    const L = this.layer, [W, H] = this.uni.world, g = 2;
    const gw = Math.floor(W / g) + 3, gh = Math.floor(H / g) + 3;
    const occ = new Uint8Array(gw * gh), cx = W / 2, cy = H / 2;
    if (L.grow_seed === "bottom") occ.fill(1, Math.floor((H - g - 1) / g) * gw);
    else occ[Math.floor(Math.floor(cy) / g) * gw + Math.floor(Math.floor(cx) / g)] = 1;
    this.crystal = { g, gw, gh, occ, hits: new Int16Array(gw * gh), stuck: new Uint8Array(this.n),
                     walking: new Uint8Array(this.n), reach: 2.0, doneAt: null, cx, cy };
    for (let i = 0; i < this.n; i++) { this.px[i] = cx; this.py[i] = L.grow_seed === "bottom" ? H - 1 : cy; }
    this.vx.fill(0); this.vy.fill(0);
  }

  fold(x, y, out) {                                         // reflect into the wedge 0..pi/fold
    const fold = this.layer.grow_fold, c = this.crystal;
    if (fold <= 0 || this.layer.grow_seed === "bottom") { out[0] = x; out[1] = y; return; }
    const dx = x - c.cx, dy = y - c.cy, r = Math.hypot(dx, dy), w = TAU / fold;
    let a = Math.atan2(dy, dx) % w;
    if (a < 0) a += w;
    if (a > Math.PI / fold) a = w - a;
    out[0] = c.cx + r * Math.cos(a); out[1] = c.cy + r * Math.sin(a);
  }

  launch(out) {
    const L = this.layer, [W, H] = this.uni.world, c = this.crystal;
    if (L.grow_seed === "bottom") { out[0] = this.rng.random() * W; out[1] = H - c.reach - 15; return; }
    const wedge = L.grow_fold > 0 ? Math.PI / L.grow_fold : TAU;
    const a = this.rng.random() * wedge, r = c.reach + 15;
    out[0] = c.cx + r * Math.cos(a); out[1] = c.cy + r * Math.sin(a);
  }

  grow(t, mouse) {
    const L = this.layer;
    if (!this.crystal || this.crystal.stuck.length !== this.n) this.crystalReset();
    const c = this.crystal, [W, H] = this.uni.world, { g, gw, occ, stuck, walking } = c;
    const bottom = L.grow_seed === "bottom";
    if (c.doneAt !== null) { if (t - c.doneAt > L.grow_hold) this.crystalReset(); return; }
    const limit = bottom ? H - 40 : 0.47 * Math.min(W, H);
    let free = 0;
    for (let i = 0; i < this.n; i++) if (!stuck[i]) free++;
    if (free === 0 || c.reach > limit) { c.doneAt = t; return; }
    const tmp = [0, 0];

    // a moving cursor melts the crystal from the outside in, down to where it touches
    if (L.grow_melt > 0 && Math.abs(mouse.vx) + Math.abs(mouse.vy) > 1.5) {
      let mx = mouse.x, my = mouse.y, hit = false;
      if (!bottom) { this.fold(mouse.x, mouse.y, tmp); mx = tmp[0]; my = tmp[1]; }
      for (let i = 0; i < this.n; i++) if (stuck[i] && Math.hypot(this.px[i] - mx, this.py[i] - my) < L.grow_melt) { hit = true; break; }
      if (hit) {
        const rm = bottom ? H - my : Math.hypot(mx - c.cx, my - c.cy);
        let gone = 0;
        for (let i = 0; i < this.n; i++) {
          if (!stuck[i]) continue;
          const r0 = bottom ? H - this.py[i] : Math.hypot(this.px[i] - c.cx, this.py[i] - c.cy);
          if (r0 >= rm - L.grow_melt) {
            occ[Math.floor(this.py[i] / g) * gw + Math.floor(this.px[i] / g)] = 0;
            stuck[i] = 0; gone++;
          }
        }
        if (gone) {
          c.hits.fill(0); walking.fill(0);                    // everyone starts again from the new edge
          let reach = 2;
          for (let i = 0; i < this.n; i++) if (stuck[i])
            reach = Math.max(reach, bottom ? H - this.py[i] : Math.hypot(this.px[i] - c.cx, this.py[i] - c.cy));
          c.reach = reach;
        }
      }
    }

    const hue = this.hueNow(), maxW = Math.max(1, L.grow_walkers), steps = Math.max(1, L.grow_speed);
    let count = 0;
    for (let i = 0; i < this.n && count < maxW; i++) {
      if (stuck[i]) continue;
      count++;
      if (!walking[i]) { this.launch(tmp); this.px[i] = tmp[0]; this.py[i] = tmp[1]; walking[i] = 1; }
      let x = this.px[i], y = this.py[i];
      for (let s = 0; s < steps; s++) {
        const a = this.rng.random() * TAU;
        x += Math.cos(a) * g; y += Math.sin(a) * g;
        let far;
        if (bottom) { x = ((x % W) + W) % W; far = y < H - c.reach - 60; }
        else { this.fold(x, y, tmp); x = tmp[0]; y = tmp[1]; far = Math.hypot(x - c.cx, y - c.cy) > c.reach + 50; }
        if (far) { this.launch(tmp); x = tmp[0]; y = tmp[1]; }
        x = Math.min(W - g - 1, Math.max(g, x)); y = Math.min(H - g - 1, Math.max(g, y));
        const gx = Math.floor(x / g), gy = Math.floor(y / g);
        let touch = false;
        for (let dy = -1; dy <= 1 && !touch; dy++) for (let dx = -1; dx <= 1; dx++) if (occ[(gy + dy) * gw + gx + dx]) { touch = true; break; }
        if (!touch) continue;
        if (L.grow_noise > 1) {                             // noise reduction: freeze only after several touches
          const j = gy * gw + gx;
          c.hits[j]++;
          if (c.hits[j] < L.grow_noise) { this.launch(tmp); x = tmp[0]; y = tmp[1]; continue; }
        }
        occ[gy * gw + gx] = 1; stuck[i] = 1; walking[i] = 0;
        this.birthHue[i] = hue + this.rng.normal(0, 4);
        c.reach = Math.max(c.reach, bottom ? H - y : Math.hypot(x - c.cx, y - c.cy));
        break;
      }
      this.px[i] = x; this.py[i] = y;
    }
  }

  // -- slime mould (Physarum): smell ahead, turn toward the strongest scent, lay more
  slime(mouse, sign) {
    const L = this.layer, [W, H] = this.uni.world, g = Math.max(1, Math.floor(L.slime_cell));
    const gw = Math.max(1, Math.ceil(W / g)), gh = Math.max(1, Math.ceil(H / g));
    if (!this.scent || this.scentW !== gw || this.scentH !== gh) {
      this.scent = new Float32Array(gw * gh); this.scentTmp = new Float32Array(gw * gh);
      this.scentW = gw; this.scentH = gh;
    }
    const T = this.scent, n = this.n, inv = 1 / g, sd = L.slime_dist, rng = this.rng;
    const px = this.px, py = this.py, vx = this.vx, vy = this.vy;
    const ca = Math.cos(L.slime_angle * Math.PI / 180), sa = Math.sin(L.slime_angle * Math.PI / 180);
    const ct = Math.cos(L.slime_turn * Math.PI / 180), st = Math.sin(L.slime_turn * Math.PI / 180);
    const wrapX = (v) => { v = Math.floor(v); return v < 0 ? (v % gw + gw) % gw : v >= gw ? v % gw : v; };
    const wrapY = (v) => { v = Math.floor(v); return v < 0 ? (v % gh + gh) % gh : v >= gh ? v % gh : v; };
    for (let i = 0; i < n; i++) {
      let fx = vx[i], fy = vy[i], sp = Math.sqrt(fx * fx + fy * fy);
      if (sp < 1e-9) { const a = rng.random() * TAU; fx = Math.cos(a); fy = Math.sin(a); sp = 1; }
      fx /= sp; fy /= sp;
      const x = px[i], y = py[i];
      const f = T[wrapY((y + fy * sd) * inv) * gw + wrapX((x + fx * sd) * inv)];
      const lx = fx * ca + fy * sa, ly = fy * ca - fx * sa, rx = fx * ca - fy * sa, ry = fy * ca + fx * sa;
      const fl = T[wrapY((y + ly * sd) * inv) * gw + wrapX((x + lx * sd) * inv)];
      const fr = T[wrapY((y + ry * sd) * inv) * gw + wrapX((x + rx * sd) * inv)];
      let side = 0;
      if (!(f >= fl && f >= fr)) side = f < fl && f < fr ? (rng.random() < 0.5 ? 1 : -1) : (fr > fl ? 1 : -1);
      let nx = fx, ny = fy;
      if (side) { nx = fx * ct - fy * side * st; ny = fy * ct + fx * side * st; }
      if (L.jitter) {                                      // wobble: a small random sideways nudge
        const k = rng.normal(0, L.jitter), ox = nx;
        nx = nx - ny * k; ny = ny + ox * k;
        const norm = Math.sqrt(nx * nx + ny * ny); nx /= norm; ny /= norm;
      }
      vx[i] = nx * L.slime_speed; vy[i] = ny * L.slime_speed;
    }
    this.move(this.uni.p.edge, this.uni.p.bounce);
    for (let i = 0; i < n; i++) T[wrapY(py[i] * inv) * gw + wrapX(px[i] * inv)] += L.slime_deposit;
    if (L.slime_mouse) {                                   // food at the cursor (or poison, inverted)
      const R = Math.max(1, Math.round(L.slime_mouse_radius / g));
      const mx = Math.floor(mouse.x / g), my = Math.floor(mouse.y / g), v = sign * L.slime_mouse;
      for (let dy = -R; dy <= R; dy++) for (let dx = -R; dx <= R; dx++)
        if (dx * dx + dy * dy <= R * R) T[(((my + dy) % gh) + gh) % gh * gw + (((mx + dx) % gw) + gw) % gw] += v;
    }
    if (L.slime_blur > 0) {                                // diffuse: 3 x 3 box blur, wrapping
      const B = this.scentTmp;
      for (let y = 0; y < gh; y++) {
        const up = ((y + gh - 1) % gh) * gw, dn = ((y + 1) % gh) * gw, row = y * gw;
        for (let x = 0; x < gw; x++) B[row + x] = (T[row + x] + T[up + x] + T[dn + x]) / 3;
      }
      const blur = Math.min(1, L.slime_blur);
      for (let y = 0; y < gh; y++) {
        const row = y * gw;
        let prev = B[row + gw - 1], cur = B[row];
        for (let x = 0; x < gw; x++) {
          const next = B[row + (x + 1) % gw];
          const v = (prev + cur + next) / 3;
          T[row + x] = blur >= 1 ? v : T[row + x] + (v - T[row + x]) * blur;
          prev = cur; cur = next;
        }
      }
    }
    const keep = 1 - L.slime_decay;
    for (let j = 0; j < T.length; j++) T[j] *= keep;
  }

  // -- a 3D strange attractor (a flow), turned around in front of you
  flow3dStart(n) {
    const cfg = this.uni.p.flow3d, F = FLOWS_3D[this.p3Kind], rng = this.rng;
    if (cfg.start === "blob") return this.blob(F.p, n, cfg.blob * F.r);
    const seeds = Math.max(8, Math.min(64, Math.floor(n / 300)));
    const S = new Float64Array(seeds * 3);
    for (let s = 0; s < seeds; s++) for (let c = 0; c < 3; c++) S[s * 3 + c] = F.p[c] + rng.normal(0, 0.05 * F.r);
    for (let it = 0; it < 600; it++) for (let s = 0; s < seeds; s++) rk4Point(F.f, S, s * 3, F.dt * 2);
    const out = new Float64Array(n * 3), rounds = Math.ceil(n / seeds);
    let m = 0;
    for (let r = 0; r < rounds && m < n; r++) {
      for (let e = 0; e < 6; e++) for (let s = 0; s < seeds; s++) rk4Point(F.f, S, s * 3, F.dt * 2);
      for (let s = 0; s < seeds && m < n; s++) {
        const ok = [0, 1, 2].every((c) => isFinite(S[s * 3 + c]) && Math.abs(S[s * 3 + c] - F.c[c]) < 4 * F.r);
        const src = ok ? s * 3 : -1;
        for (let c = 0; c < 3; c++) out[m * 3 + c] = src >= 0 ? S[src + c] : F.p[c];
        m++;
      }
    }
    for (let i = n - 1; i > 0; i--) {                       // shuffle
      const j = rng.int(i + 1);
      for (let c = 0; c < 3; c++) { const t = out[i * 3 + c]; out[i * 3 + c] = out[j * 3 + c]; out[j * 3 + c] = t; }
    }
    return out;
  }

  /** n points on a tiny segment, in body order: neighbours in colour stay neighbours in space. */
  blob(at, n, size) {
    const rng = this.rng, d = [rng.normal(), rng.normal(), rng.normal()];
    const norm = Math.hypot(d[0], d[1], d[2]) || 1, out = new Float64Array(n * 3);
    for (let i = 0; i < n; i++) {
      const s = (n > 1 ? i / (n - 1) : 0.5) - 0.5;
      for (let c = 0; c < 3; c++) out[i * 3 + c] = at[c] + s * d[c] / norm * size + rng.normal(0, size * 0.02);
    }
    return out;
  }

  reborn3d(idx) {
    const cfg = this.uni.p.flow3d, F = FLOWS_3D[this.p3Kind], k = idx.length, rng = this.rng;
    if (k === this.n) {                                    // everyone at once: a new speck somewhere on it
      const j = rng.int(this.n), at = [this.p3[j * 3], this.p3[j * 3 + 1], this.p3[j * 3 + 2]];
      this.p3.set(this.blob(at, k, Math.max(cfg.blob, 1e-7) * F.r));
      return;
    }
    const mark = new Uint8Array(this.n);
    for (const j of idx) mark[j] = 1;
    const rest = [];
    for (let i = 0; i < this.n; i++) if (!mark[i]) rest.push(i);
    const sd = Math.max(cfg.blob, 1e-6) * F.r;
    for (const j of idx) {
      const s = rest[rng.int(rest.length)];
      for (let c = 0; c < 3; c++) this.p3[j * 3 + c] = this.p3[s * 3 + c] + rng.normal(0, sd);
    }
  }

  flow3d(t, mouse) {
    const cfg = this.uni.p.flow3d, kind = FLOWS_3D[cfg.kind] ? cfg.kind : "lorenz", n = this.n;
    if (!this.p3 || this.p3.length !== n * 3 || this.p3Kind !== kind) { this.p3Kind = kind; this.p3 = this.flow3dStart(n); }
    const F = FLOWS_3D[kind], P = this.p3, f = F.f;
    const steps = Math.max(1, Math.ceil(2 * Math.abs(cfg.speed))), h = F.dt * 2 * cfg.speed / steps;
    const k1 = new Float64Array(3), k2 = new Float64Array(3);
    for (let s = 0; s < steps; s++) {                      // midpoint rule: plenty for drawing
      for (let i = 0; i < n * 3; i += 3) {
        const x = P[i], y = P[i + 1], z = P[i + 2];
        f(x, y, z, k1, 0);
        f(x + h / 2 * k1[0], y + h / 2 * k1[1], z + h / 2 * k1[2], k2, 0);
        P[i] = x + h * k2[0]; P[i + 1] = y + h * k2[1]; P[i + 2] = z + h * k2[2];
      }
    }
    let good = -1;
    for (let i = 0; i < n * 3; i += 3) {                   // escaped (too big a step): back onto the attractor
      const bad = ![0, 1, 2].every((c) => isFinite(P[i + c]) && Math.abs(P[i + c] - F.c[c]) <= 4 * F.r);
      if (!bad) { good = i; continue; }
      for (let c = 0; c < 3; c++) P[i + c] = (good >= 0 ? P[good + c] : F.c[c]) + this.rng.normal(0, 1e-3 * F.r);
    }
    const [W, H] = this.uni.world;
    let yaw = F.yaw * Math.PI / 180 + TAU * cfg.spin * t + cfg.mouse_turn * TAU * (mouse.x / Math.max(W, 1) - 0.5);
    let pitch = cfg.tilt * Math.PI / 180 + cfg.mouse_turn * 0.5 * Math.PI * (mouse.y / Math.max(H, 1) - 0.5);
    if (!this.view) this.view = [yaw, pitch];
    else { this.view[0] += (yaw - this.view[0]) * 0.06; this.view[1] += (pitch - this.view[1]) * 0.06; }
    [yaw, pitch] = this.view;
    const cy = Math.cos(yaw), sy = Math.sin(yaw), cp = Math.cos(pitch), sp = Math.sin(pitch);
    const R = cfg.scale * Math.min(W, H) / 2, persp = cfg.perspective * 0.6;
    if (!this.depth || this.depth.length !== n) this.depth = new Float64Array(n);
    for (let i = 0; i < n; i++) {
      const x = (P[i * 3] - F.c[0]) / F.r, y = (P[i * 3 + 1] - F.c[1]) / F.r, z = (P[i * 3 + 2] - F.c[2]) / F.r;
      const X = x * cy - y * sy, Y = x * sy + y * cy;
      const up = z * cp - Y * sp, depth = z * sp + Y * cp;
      const k = 1 / Math.max(0.2, 1 + persp * depth);
      const nx = W / 2 + R * X * k, ny = H / 2 - R * up * k;
      this.vx[i] = nx - this.px[i]; this.vy[i] = ny - this.py[i];
      this.px[i] = nx; this.py[i] = ny; this.depth[i] = depth;
    }
  }

  // -- double pendulums: each body is the tip of its own
  pendStart(idx) {
    const L = this.layer, n = Math.max(this.n, 2);
    const a0 = this.pendRelease !== null ? this.pendRelease : L.pend_angle * Math.PI / 180;
    const out = new Float64Array(idx.length * 4);
    for (let i = 0; i < idx.length; i++) {
      const a = a0 + L.pend_spread * Math.PI / 180 * (idx[i] / (n - 1) - 0.5);
      out[i * 4] = a; out[i * 4 + 2] = a;
    }
    return out;
  }

  pendulum(mouse) {
    const L = this.layer, [W, H] = this.uni.world, n = this.n;
    const pvx = L.pend_pivot[0] * W, pvy = L.pend_pivot[1] * H;
    if (L.pend_click && mouse.clicked) {                    // let go of all of them where you clicked
      this.pendRelease = Math.atan2(mouse.x - pvx, mouse.y - pvy);
      this.pend = null;
    }
    if (!this.pend || this.pend.length !== n * 4) this.pend = this.pendStart(Array.from({ length: n }, (_, i) => i));
    const S = this.pend, steps = 8, h = L.pend_speed / FPS / steps;
    const m2 = L.pend_mass, l2 = Math.max(L.pend_ratio, 0.05), g = L.pend_gravity;
    const k = new Float64Array(16);
    for (let i = 0; i < n * 4; i += 4) {
      let a = S[i], b = S[i + 1], c = S[i + 2], d = S[i + 3];
      for (let s = 0; s < steps; s++) {
        pendRate(a, b, c, d, m2, l2, g, k, 0);
        pendRate(a + h / 2 * k[0], b + h / 2 * k[1], c + h / 2 * k[2], d + h / 2 * k[3], m2, l2, g, k, 4);
        pendRate(a + h / 2 * k[4], b + h / 2 * k[5], c + h / 2 * k[6], d + h / 2 * k[7], m2, l2, g, k, 8);
        pendRate(a + h * k[8], b + h * k[9], c + h * k[10], d + h * k[11], m2, l2, g, k, 12);
        a += h / 6 * (k[0] + 2 * k[4] + 2 * k[8] + k[12]);
        b += h / 6 * (k[1] + 2 * k[5] + 2 * k[9] + k[13]);
        c += h / 6 * (k[2] + 2 * k[6] + 2 * k[10] + k[14]);
        d += h / 6 * (k[3] + 2 * k[7] + 2 * k[11] + k[15]);
      }
      S[i] = a; S[i + 1] = b; S[i + 2] = c; S[i + 3] = d;
    }
    const unit = L.pend_size * Math.min(W, H) / (1 + l2);
    if (!this.jx || this.jx.length !== n) { this.jx = new Float64Array(n); this.jy = new Float64Array(n); }
    for (let i = 0; i < n; i++) {
      const th1 = S[i * 4], th2 = S[i * 4 + 2];
      const jx = pvx + unit * Math.sin(th1), jy = pvy + unit * Math.cos(th1);
      const tx = jx + unit * l2 * Math.sin(th2), ty = jy + unit * l2 * Math.cos(th2);
      this.vx[i] = tx - this.px[i]; this.vy[i] = ty - this.py[i];
      this.px[i] = tx; this.py[i] = ty; this.jx[i] = jx; this.jy[i] = jy;
    }
  }

  // -- motion
  /** Move by the velocity and deal with the walls. */
  move(edge, bounce) {
    const [W, H] = this.uni.world, n = this.n, px = this.px, py = this.py, vx = this.vx, vy = this.vy;
    for (let i = 0; i < n; i++) { px[i] += vx[i]; py[i] += vy[i]; }
    if (edge === "bounce") {
      for (let i = 0; i < n; i++) {
        if (px[i] < 0) { px[i] = -px[i]; vx[i] *= -bounce; } else if (px[i] > W) { px[i] = 2 * W - px[i]; vx[i] *= -bounce; }
        if (py[i] < 0) { py[i] = -py[i]; vy[i] *= -bounce; } else if (py[i] > H) { py[i] = 2 * H - py[i]; vy[i] *= -bounce; }
        px[i] = Math.min(W - 1e-3, Math.max(0, px[i])); py[i] = Math.min(H - 1e-3, Math.max(0, py[i]));
      }
    } else if (edge === "respawn") {
      const out = [];
      for (let i = 0; i < n; i++) if (px[i] < 0 || px[i] > W || py[i] < 0 || py[i] > H) out.push(i);
      this.reborn(out);
    } else {
      for (let i = 0; i < n; i++) {
        px[i] %= W; if (px[i] < 0) px[i] += W;
        py[i] %= H; if (py[i] < 0) py[i] += H;
      }
    }
  }

  /** Where every body of a path layer should be at time t (into ox, oy). */
  pathPoints(t, ox, oy) {
    const L = this.layer, u = this.uni, n = this.n, [W, H] = u.world;
    const cx = L.path_around === "mouse" ? u.mouse.x : L.path_center[0] * W;
    const cy = L.path_around === "mouse" ? u.mouse.y : L.path_center[1] * H;
    const spin = L.path_spin ? TAU * L.path_spin * t : 0, cs = Math.cos(spin), ss = Math.sin(spin);
    const shape = L.path_shape;
    let ax, ay;
    if (shape === "sunflower") {
      // Vogel's model: seed j at angle j * divergence, radius sqrt(j); with path_speed > 0 the seeds
      // stream outward, and the divergence can swing around the golden angle
      ax = ay = L.path_size[0] * Math.min(W, H) / 2;
      if (!this.pathU || this.pathU.length !== n) this.pathU = new Float64Array(n);
      const born = t * L.path_speed * n;
      const div = (L.path_angle + L.path_sweep * Math.sin(TAU * t / Math.max(L.path_sweep_period, 1e-3))) * Math.PI / 180;
      for (let b = 0; b < n; b++) {
        let uu, j;
        if (L.path_speed) { uu = ((born - b) % n + n) % n; j = born - uu; } else { uu = j = b; }
        this.pathU[b] = uu;
        const r = Math.sqrt((uu + 0.5) / n), th = div * j;
        let x = r * Math.cos(th), y = r * Math.sin(th);
        if (spin) { const x2 = x * cs - y * ss; y = x * ss + y * cs; x = x2; }
        ox[b] = cx + ax * x; oy[b] = cy + ay * y;
      }
      return;
    }
    const rose = shape === "rose", spiro = shape === "spiro";
    if (rose || spiro) { ax = ay = L.path_size[0] * Math.min(W, H) / 2; }
    else { ax = L.path_size[0] * W / 2; ay = L.path_size[1] * H / 2; }
    const q = Math.min(Math.max(L.path_k, 0.01), 0.99), kk = (1 - q) / q, norm = (1 - q) + L.path_d * q;
    for (let i = 0; i < n; i++) {
      const ph = TAU * (t * L.path_speed + L.path_spread * L.path_loops * i / Math.max(n, 1));
      let x, y;
      if (rose) { const r = Math.cos(L.path_k * ph); x = r * Math.cos(ph); y = r * Math.sin(ph); }
      else if (spiro) {
        x = ((1 - q) * Math.cos(ph) + L.path_d * q * Math.cos(kk * ph)) / norm;
        y = ((1 - q) * Math.sin(ph) - L.path_d * q * Math.sin(kk * ph)) / norm;
      } else { x = Math.sin(L.path_freq[0] * ph + Math.PI / 2); y = Math.sin(L.path_freq[1] * ph); }
      if (spin) { const x2 = x * cs - y * ss; y = x * ss + y * cs; x = x2; }
      ox[i] = cx + ax * x; oy[i] = cy + ay * y;
    }
  }

  followPath(t) {
    const n = this.n, nx = new Float64Array(n), ny = new Float64Array(n);
    this.pathPoints(t, nx, ny);
    for (let i = 0; i < n; i++) { this.vx[i] = nx[i] - this.px[i]; this.vy[i] = ny[i] - this.py[i]; }
    this.px = nx; this.py = ny;
  }

  // -- looks
  /** Colour per body into out (n x 3, 0..255), before brightness. */
  colorsInto(out) {
    const L = this.layer, pal = this.uni.p.palette, t = this.uni.t, n = this.n;
    const hue = pal.hue + pal.hue_speed * t, m = L.color_mode;
    const lerp = (i, k) => {
      const a = L.color, b = L.color2;
      out[i * 3] = a[0] + (b[0] - a[0]) * k; out[i * 3 + 1] = a[1] + (b[1] - a[1]) * k; out[i * 3 + 2] = a[2] + (b[2] - a[2]) * k;
    };
    if (m === "fixed" || (m === "age" && L.life <= 0)) {
      for (let i = 0; i < n; i++) { out[i * 3] = L.color[0]; out[i * 3 + 1] = L.color[1]; out[i * 3 + 2] = L.color[2]; }
    } else if (m === "speed") {
      const ref = Math.max(L.speed_ref, 1e-6);
      for (let i = 0; i < n; i++) lerp(i, Math.min(1, Math.sqrt(this.vx[i] * this.vx[i] + this.vy[i] * this.vy[i]) / ref));
    } else if (m === "age") {
      for (let i = 0; i < n; i++) lerp(i, Math.min(1, Math.max(0, this.age[i] / this.life[i])));
    } else if (m === "palette") {
      const c = [0, 0, 0];
      hsvInto(hue, pal.saturation, pal.value, c, 0);
      for (let i = 0; i < n; i++) { out[i * 3] = c[0]; out[i * 3 + 1] = c[1]; out[i * 3 + 2] = c[2]; }
    } else {
      const lut = hueLut(pal.saturation, pal.value);
      for (let i = 0; i < n; i++) {
        let h;
        if (m === "direction") h = hue + Math.atan2(this.vy[i], this.vx[i]) * 180 / Math.PI;
        else if (m === "rainbow") h = hue + pal.spread * (this.hueSeed[i] - 0.5);
        else if (m === "birth") h = this.birthHue[i];
        else h = hue + pal.spread * i / Math.max(n, 1);   // index
        const k = lutIndex(h);
        out[i * 3] = lut[k]; out[i * 3 + 1] = lut[k + 1]; out[i * 3 + 2] = lut[k + 2];
      }
    }
  }

  /** Per body brightness (fade in / out, crystal walkers, depth, twinkle) or null. */
  light(base) {
    const L = this.layer, n = this.n, t = this.uni.t;
    if (L.motion === "grow" && this.crystal) {
      const c = this.crystal, out = new Float64Array(n);
      let k = 1;
      if (c.doneAt !== null) k = Math.min(1, Math.max(0, (L.grow_hold - (t - c.doneAt)) / 3));
      for (let i = 0; i < n; i++) out[i] = (c.stuck[i] ? base : c.walking[i] ? base * L.grow_walker_light : 0) * k;
      return out;
    }
    let out = null;
    const start = () => { if (!out) { out = new Float64Array(n); out.fill(base); } return out; };
    if (L.motion === "flow3d" && this.depth && this.uni.p.flow3d.depth_light) {
      const k = this.uni.p.flow3d.depth_light, o = start();
      for (let i = 0; i < n; i++) o[i] *= Math.min(1.5, Math.max(0.05, 1 - k * (this.depth[i] + 1) / 2));
    }
    if (L.motion === "path" && L.path_shape === "sunflower" && L.path_speed && this.pathU) {
      const o = start();
      for (let i = 0; i < n; i++) {
        const uu = this.pathU[i];
        o[i] *= Math.min(1, Math.max(0, (n - uu) / (0.1 * n))) * Math.min(1, Math.max(0, uu / (0.004 * n)));
      }
    }
    if (L.twinkle > 0) {                                   // each body flickers on its own clock
      const o = start(), p = 2 + 10 * L.twinkle, per = Math.max(L.twinkle_period, 0.05);
      for (let i = 0; i < n; i++) {
        const ph = t / (per * (0.7 + 0.6 * this.seed2[i])) + this.hueSeed[i];
        o[i] *= 1 - L.twinkle + L.twinkle * Math.pow(0.5 + 0.5 * Math.sin(TAU * ph), p);
      }
    }
    if (L.life > 0 && L.fade) {
      const o = start();
      for (let i = 0; i < n; i++) {
        const rise = Math.min(1, Math.max(0, this.age[i] / 12));
        const fall = Math.min(1, Math.max(0, (this.life[i] - this.age[i]) / (0.3 * this.life[i])));
        o[i] *= rise * fall;
      }
    }
    return out;
  }
}

// ------------------------------------------------------------------ the universe

class Universe {
  constructor(preset, world, mouse, seed) {
    this.world = world;                                    // [W, H], read once
    this.cx = world[0] / 2; this.cy = world[1] / 2;
    this.rng = makeRng(seed === undefined ? (Math.random() * 4294967296) >>> 0 : seed);
    this.mouse = mouse; this.mouse.update();
    this.p = preset; this.t = 0; this.frame = 0; this.dark = 1; this.swarms = [];
    this.pages = new Map();                                // text: "period|click" -> {page, at}
    this.reconfigure(preset);
  }

  static pageKey(L) { return `${Math.max(+L.text_period, 0.5)}|${!!L.text_click}`; }

  /** Text layers with the same seconds per page share one page counter, so a poem and its title
      turn together; the counter turns when its time is up, or on a click if it may. */
  turnPages(t) {
    const live = new Map();
    for (const s of this.swarms) {
      const L = s.layer;
      if (L.spawn === "text") live.set(Universe.pageKey(L), [Math.max(+L.text_period, 0.5), !!L.text_click]);
    }
    for (const k of [...this.pages.keys()]) if (!live.has(k)) this.pages.delete(k);
    for (const [k, [period, click]] of live) {
      let pg = this.pages.get(k);
      if (!pg) { pg = { page: 0, at: t }; this.pages.set(k, pg); }
      if ((click && this.mouse.clicked) || t - pg.at >= period - 1e-9) { pg.page++; pg.at = t; }
    }
  }

  /** Swap in new settings without a restart; bodies keep moving. Layers match by name (or position). */
  reconfigure(preset) {
    this.p = preset;
    const newNames = new Set(preset.layers.map((l) => l.name));
    const old = new Map(this.swarms.map((s) => [s.layer.name, s]));
    const matched = preset.layers.map((layer, i) => {
      let s = old.get(layer.name);
      if (s) old.delete(layer.name);
      else if (i < this.swarms.length) {
        const prev = this.swarms[i];
        if (!newNames.has(prev.layer.name) && old.get(prev.layer.name) === prev) { s = prev; old.delete(prev.layer.name); }
      }
      return [layer, s];
    });
    this.swarms = [];
    for (const [layer, s0] of matched) {                   // rebuilt in order: a new emitter sees its parents
      let s = s0;
      if (!s) s = new Swarm(layer, this);
      else {
        const a = s.layer;
        const textChanged = a.text !== layer.text || a.text_size !== layer.text_size || a.text_font !== layer.text_font ||
          a.text_pos[0] !== layer.text_pos[0] || a.text_pos[1] !== layer.text_pos[1];
        const regrow = a.motion !== layer.motion || a.grow_seed !== layer.grow_seed || a.grow_fold !== layer.grow_fold;
        if (a.pend_angle !== layer.pend_angle || a.pend_spread !== layer.pend_spread || a.motion !== layer.motion) {
          s.pend = null; s.pendRelease = null;
        }
        s.layer = layer;
        s.resize(layer.count);
        s.relife();
        if (textChanged) s.textKey = null;
        if (regrow) s.crystal = null;
      }
      this.swarms.push(s);
    }
  }

  counts() { const o = {}; for (const s of this.swarms) o[s.layer.name] = s.n; return o; }

  /** Positions and velocities of a pull source, as seen from `swarm`. */
  sourceArrays(swarm, source) {
    let i = this.swarms.indexOf(swarm);
    if (i < 0) i = this.swarms.length;
    if (source === "above" && i === 0) source = "mouse";
    const m = this.mouse;
    if (source === "mouse") return { n: 1, x: [m.x], y: [m.y], vx: [m.vx], vy: [m.vy] };
    if (source === "center") return { n: 1, x: [this.cx], y: [this.cy], vx: [0], vy: [0] };
    const a = this.swarms[i - 1];
    return { n: a.n, x: a.px, y: a.py, vx: a.vx, vy: a.vy };
  }

  breath() {
    const p = this.p;
    if (p.breathe_period <= 0) return 1;
    const x = Math.abs((this.t % p.breathe_period) - p.breathe_period / 2);   // seconds from the dark moment
    const width = Math.min(6, p.breathe_period / 6);
    return 1 - p.breathe_depth * Math.exp(-((x / width) ** 2));
  }

  wind() {
    const p = this.p;
    let wx = p.wind[0], wy = p.wind[1];
    if (p.wind_mode === "tilt") {                           // gravity toward the cursor, a dead zone in the middle
      const dx = this.mouse.x - this.cx, dy = this.mouse.y - this.cy, d = Math.hypot(dx, dy);
      const strength = Math.hypot(wx, wy);
      const k = Math.min(1, Math.max(0, (d - 40) / (0.35 * Math.min(...this.world))));
      if (d > 1e-6) { wx = dx / d * strength * k; wy = dy / d * strength * k; } else { wx = wy = 0; }
    }
    return [wx, wy];
  }

  step() {
    const p = this.p, m = this.mouse, [W, H] = this.world;
    this.dark = this.breath();
    const forceScale = p.breathe_forces ? this.dark : 1;
    m.update();
    const mouseSign = p.click_invert && m.pressed ? -1 : 1;
    const [wx, wy] = this.wind();
    const t = this.t;
    this.turnPages(t);

    for (const sw of this.swarms) {
      const L = sw.layer, n = sw.n;
      if (!n) continue;
      if (L.spawn === "text") {
        const text = expandText(L.text, this.pages.get(Universe.pageKey(L)).page);
        if (text !== sw.textKey) sw.retarget(text);
      }
      if (L.click_burst && m.clicked) sw.burstAt([m.x, m.y], L.click_burst);
      if (L.life > 0) {
        const due = [];
        for (let i = 0; i < n; i++) if (++sw.age[i] >= sw.life[i]) due.push(i);
        sw.reborn(due);
      }
      if (L.motion === "fixed") continue;
      if (L.motion === "teleport") {
        if (this.frame % Math.max(1, L.teleport_every) === 0) {
          for (let i = 0; i < n; i++) { sw.px[i] = this.rng.random() * W; sw.py[i] = this.rng.random() * H; }
          sw.vx.fill(0); sw.vy.fill(0);
        }
        continue;
      }
      if (L.motion === "path") {
        if (L.home <= 0) { sw.followPath(t); continue; }     // rigid: exactly on the curve
        sw.pathPoints(t, sw.hx, sw.hy);                      // elastic: springs toward the moving curve
      } else if (L.motion === "grow") { sw.grow(t, m); continue; }
      else if (L.motion === "slime") { sw.slime(m, mouseSign); continue; }
      else if (L.motion === "flow3d") { sw.flow3d(t, m); continue; }
      else if (L.motion === "pendulum") { sw.pendulum(m); continue; }

      // pulls (scaled by each body's own mass when variety > 0), then the other forces
      const ax = sw.ax, ay = sw.ay;
      ax.fill(0); ay.fill(0);
      let eaten = null;
      for (const pl of L.pulls) {
        if (!pl.enabled) continue;
        const src = this.sourceArrays(sw, pl.source);
        if (src.n * n > MAX_PAIRS) continue;
        const f = pl.field;
        const isMouse = pl.source === "mouse" || (pl.source === "above" && sw === this.swarms[0]);
        let pf = pulseFactor(f, t), radius = f.radius;
        if (f.law === "ring") { radius *= pf; pf = 1; }      // rings breathe in size, not strength
        let scale = forceScale * pf * (isMouse ? mouseSign : 1);
        if (f.law === "drag" || f.law === "wake" || f.law === "startle") scale = pf;   // light does not dim a sweep
        const sweep = f.law === "wake" || f.law === "startle";
        for (let s = 0; s < src.n; s++) {
          const sx = src.x[s], sy = src.y[s], svx = src.vx[s], svy = src.vy[s];
          if (f.absorb > 0) {
            const a2 = f.absorb * f.absorb;
            for (let i = 0; i < n; i++) {
              const dx = sw.px[i] - sx, dy = sw.py[i] - sy;
              if (dx * dx + dy * dy < a2) (eaten || (eaten = new Uint8Array(n)))[i] = 1;
            }
          }
          if (sweep && Math.abs(svx) + Math.abs(svy) < 1e-3) continue;   // a still source stirs nothing
          pullInto(sw, sx, sy, svx, svy, f, scale, radius, ax, ay);
        }
      }
      if (L.variety) for (let i = 0; i < n; i++) { const k = 1 + L.variety * (2 * sw.seed2[i] - 1); ax[i] *= k; ay[i] *= k; }
      let carry = null;
      if (p.flow.enabled && L.flow) {
        if (p.flow.mode === "carry") {
          carry = [new Float64Array(n), new Float64Array(n)];
          flowInto(sw, p.flow, t, L.flow * 20, carry[0], carry[1]);   // streamline speed, px / frame
        } else flowInto(sw, p.flow, t, L.flow, ax, ay);
      }
      if (L.wind && (wx || wy)) for (let i = 0; i < n; i++) { ax[i] += wx * L.wind; ay[i] += wy * L.wind; }
      if (L.home) {
        const wrap = p.edge === "wrap";                       // the short way round: wrapping must not pump the spring
        for (let i = 0; i < n; i++) {
          let dx = sw.hx[i] - sw.px[i], dy = sw.hy[i] - sw.py[i];
          if (wrap) { dx -= W * Math.round(dx / W); dy -= H * Math.round(dy / H); }
          ax[i] += dx * L.home; ay[i] += dy * L.home;
        }
      }
      if (L.pressure || L.align) neighbourhoodInto(sw, W, H, L.cell, L.pressure, L.align, ax, ay);

      const vx = sw.vx, vy = sw.vy, rng = this.rng;
      if (L.jitter) for (let i = 0; i < n; i++) { vx[i] += rng.normal(0, L.jitter); vy[i] += rng.normal(0, L.jitter); }
      if (L.motion === "wander") for (let i = 0; i < n; i++) { vx[i] += rng.normal(0, 0.5); vy[i] += rng.normal(0, 0.5); }
      // feel every force, then friction (v *= 1 - f v^2, never flipping sign) and the speed limits
      const damp = L.damping ? Math.max(0, 1 - L.damping) : 1;
      const fr = L.friction !== null && L.friction !== undefined ? L.friction : p.friction;
      const axis = p.friction_shape === "axis", lo = L.min_speed, hi = L.max_speed > 0 ? L.max_speed : Infinity;
      const limit = L.max_speed > 0 || L.min_speed > 0;
      for (let i = 0; i < n; i++) {
        let a = vx[i] * damp + ax[i], b = vy[i] * damp + ay[i];
        if (axis) { a *= Math.max(0, 1 - fr * a * a); b *= Math.max(0, 1 - fr * b * b); }
        else { const k = Math.max(0, 1 - fr * (a * a + b * b)); a *= k; b *= k; }
        if (limit) {
          const sp = Math.sqrt(a * a + b * b);
          if (sp > 1e-9) { const k = Math.min(hi, Math.max(lo, sp)) / sp; a *= k; b *= k; }
          else if (lo > 0) { const r = rng.random() * TAU; a = Math.cos(r) * lo; b = Math.sin(r) * lo; }
        }
        vx[i] = a; vy[i] = b;
      }
      if (L.motion === "attractor") {
        const ac = p.attractor.around === "mouse" ? [m.x, m.y] : [this.cx, this.cy];
        attractorStep(sw, p.attractor, t, W, H, ac[0], ac[1], L.map_blend);
      } else {
        if (carry) for (let i = 0; i < n; i++) { sw.px[i] += carry[0][i]; sw.py[i] += carry[1][i]; }
        sw.move(p.edge, p.bounce);
      }
      if (eaten) { const idx = []; for (let i = 0; i < n; i++) if (eaten[i]) idx.push(i); sw.reborn(idx); }
    }
    this.t += 1 / FPS;
    this.frame += 1;
  }

  // ---------------------------------------------------------------- what to paint (render.js draws it)

  /** Final colours (0..1, n x 3) for a swarm, with brightness, fades and the paper rule applied. */
  paintColors(sw, out) {
    const p = this.p, L = sw.layer, n = sw.n;
    const base = this.dark * p.brightness * L.brightness;
    sw.colorsInto(out);
    const light = sw.light(base);
    const bg = p.background, additive = p.blend === "add";
    const paper = !additive && bg[0] + bg[1] + bg[2] >= 384;   // on paper, faint = closer to the paper colour
    const P0 = paper ? bg[0] : 0, P1 = paper ? bg[1] : 0, P2 = paper ? bg[2] : 0;
    for (let i = 0; i < n; i++) {
      const k = light ? light[i] : base, j = i * 3;
      out[j] = Math.min(255, Math.max(0, P0 + (out[j] - P0) * k)) / 255;
      out[j + 1] = Math.min(255, Math.max(0, P1 + (out[j + 1] - P1) * k)) / 255;
      out[j + 2] = Math.min(255, Math.max(0, P2 + (out[j + 2] - P2) * k)) / 255;
    }
    return light;
  }

  /** Constellation lines between nearby bodies (and the cursor): [x1, y1, x2, y2, ...] and colours. */
  links(sw, col) {
    const L = sw.layer, m = this.mouse;
    let idx = [];
    for (let i = 0; i < sw.n; i++)
      if (!(L.link_reveal > 0) || Math.hypot(sw.px[i] - m.x, sw.py[i] - m.y) < L.link_reveal + L.links) idx.push(i);
    const n = idx.length;
    if (n < 2 || n > MAX_LINK_BODIES) return null;
    const X = idx.map((i) => sw.px[i]), Y = idx.map((i) => sw.py[i]);
    const pairs = [];
    if (L.link_max > 0) {                                  // each body links only to its nearest few
      const seen = new Set(), k = Math.min(L.link_max, n - 1);
      for (let a = 0; a < n; a++) {
        const near = [];
        for (let b = 0; b < n; b++) {
          if (a === b) continue;
          const d = Math.hypot(X[a] - X[b], Y[a] - Y[b]);
          if (d < L.links) near.push([d, b]);
        }
        near.sort((u, v) => u[0] - v[0]);
        for (const [d, b] of near.slice(0, k)) {
          const key = Math.min(a, b) * n + Math.max(a, b);
          if (!seen.has(key)) { seen.add(key); pairs.push([Math.min(a, b), Math.max(a, b), d]); }
        }
      }
    } else {
      for (let a = 0; a < n; a++) for (let b = a + 1; b < n; b++) {
        const d = Math.hypot(X[a] - X[b], Y[a] - Y[b]);
        if (d < L.links) pairs.push([a, b, d]);
      }
    }
    let lines = pairs.map(([a, b, d]) => {
      let s = (1 - d / L.links) * L.link_brightness;
      if (L.link_reveal > 0) {
        const mx = (X[a] + X[b]) / 2, my = (Y[a] + Y[b]) / 2;
        s *= Math.min(1, Math.max(0, 1.5 * (1 - Math.hypot(mx - m.x, my - m.y) / L.link_reveal)));
      }
      return [a, b, s];
    }).filter((l) => l[2] > 0.01);
    const copies = Math.max(1, this.p.symmetry) * (this.p.mirror ? 2 : 1);
    const budget = Math.max(50, Math.floor(MAX_LINKS / copies));
    if (lines.length > budget) lines = lines.sort((u, v) => v[2] - u[2]).slice(0, budget);
    const verts = [], cols = [];
    const c = (i, s) => [col[idx[i] * 3] * s, col[idx[i] * 3 + 1] * s, col[idx[i] * 3 + 2] * s];
    for (const [a, b, s] of lines) { verts.push(X[a], Y[a], X[b], Y[b]); const cc = c(a, s); cols.push(...cc, ...cc); }
    if (L.link_mouse) {
      for (let a = 0; a < n; a++) {
        const dm = Math.hypot(X[a] - m.x, Y[a] - m.y);
        if (dm >= L.links * 1.4) continue;
        const s = (1 - dm / (L.links * 1.4)) * L.link_brightness * 1.2, cc = c(a, s);
        verts.push(m.x, m.y, X[a], Y[a]); cols.push(...cc, ...cc);
      }
    }
    return verts.length ? { verts: new Float32Array(verts), cols: new Float32Array(cols.map((v) => Math.min(1, v))) } : null;
  }

  /** The rods of a few of the double pendulums: lines, joints and the pivot. */
  arms(sw, col) {
    const L = sw.layer, [W, H] = this.world, n = sw.n;
    if (!sw.jx || !(L.pend_arms > 0)) return null;
    const k = Math.min(L.pend_arms, n), pick = new Set();
    for (let j = 0; j < k; j++) pick.add(Math.floor(k > 1 ? j * (n - 1) / (k - 1) : 0));
    const pvx = L.pend_pivot[0] * W, pvy = L.pend_pivot[1] * H;
    const verts = [], cols = [], dots = [], dcols = [];
    for (const i of pick) {
      const c = [0, 1, 2].map((q) => Math.min(1, col[i * 3 + q] * 0.8 + 30 / 255));
      verts.push(pvx, pvy, sw.jx[i], sw.jy[i], sw.jx[i], sw.jy[i], sw.px[i], sw.py[i]);
      for (let r = 0; r < 4; r++) cols.push(...c);
      dots.push(sw.jx[i], sw.jy[i]); dcols.push(...c);
    }
    dots.push(pvx, pvy); dcols.push(200 / 255, 200 / 255, 210 / 255);
    return { verts: new Float32Array(verts), cols: new Float32Array(cols), dots: new Float32Array(dots), dcols: new Float32Array(dcols) };
  }
}

Object.assign(DU, { TAU, FPS, makeRng, normalise, toPlain, clone, Universe, Swarm, Mouse, expandText, textPoints,
                    FLOWS_3D, hsvInto });
})();
