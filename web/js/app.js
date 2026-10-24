// The page: the loop, the cursor, the preset library, the gallery, the bar, the keys.
(function () {
"use strict";
const DU = window.DU, DATA = window.DU_DATA;
const $ = (id) => document.getElementById(id);
const REPO = "https://github.com/AlexW6385/DesktopUniverse";
const ROTATE_SECONDS = 30;

const store = {
  get(k, d) { try { const v = localStorage.getItem(k); return v === null ? d : JSON.parse(v); } catch (e) { return d; } },
  set(k, v) { try { localStorage.setItem(k, JSON.stringify(v)); } catch (e) { /* private mode */ } },
};

// ------------------------------------------------------------------ the library

const GROUP_OF = {}, ORDER = [];
for (const [group, keys] of DATA.groups) for (const k of keys) { GROUP_OF[k] = group; ORDER.push(k); }
const AUTOSAVE = "_autosave", MINE = "Mine", AUTOSAVED = "Autosaved";

const lib = {
  mine: store.get("du.mine", {}),                          // your presets, in this browser
  autosaved: store.get("du.autosave", null),
  has(k) { return k in DATA.presets || k in this.mine || (k === AUTOSAVE && !!this.autosaved); },
  raw(k) { return k in DATA.presets ? DATA.presets[k] : k === AUTOSAVE ? this.autosaved : this.mine[k]; },
  get(k) { return DU.normalise(this.raw(k)); },
  title(k) { const r = this.raw(k); return (r && r.title) || k; },
  isMine(k) { return k in this.mine; },
  slot(k) { const i = DATA.slots.indexOf(k); return i >= 0 ? i + 1 : null; },
  group(k) { return GROUP_OF[k] || (k === AUTOSAVE ? AUTOSAVED : MINE); },
  mineKeys() { return Object.keys(this.mine).sort(); },
  listing() {
    const out = ORDER.map((k) => [k, this.title(k), GROUP_OF[k], this.slot(k), false]);
    for (const k of this.mineKeys()) out.push([k, this.title(k), MINE, null, true]);
    if (this.autosaved) out.push([AUTOSAVE, "Last experiment (autosaved)", AUTOSAVED, null, false]);
    return out;
  },
  slug(name) { return name.trim().replace(/[^\p{L}\p{N}_-]+/gu, "_").replace(/^_+|_+$/g, "").slice(0, 60); },
  persist() { store.set("du.mine", this.mine); },
  save(name, preset) {
    const key = this.slug(name);
    if (!key || key in DATA.presets || key.startsWith("_")) throw new Error(`“${name}” can’t be used as a name (the built-in presets’ names are taken)`);
    const p = DU.toPlain(preset);
    if (!(key in this.mine)) p.title = name.trim() || key;
    this.mine[key] = p; this.persist();
    return key;
  },
  rename(key, name) {
    const nk = this.slug(name);
    if (!nk || nk in DATA.presets || nk.startsWith("_") || (nk in this.mine && nk !== key)) throw new Error(`“${name}” can’t be used as a name`);
    const p = this.mine[key]; delete this.mine[key];
    p.title = name.trim(); this.mine[nk] = p; this.persist();
    return nk;
  },
  remove(key) { delete this.mine[key]; this.persist(); },
  autosave(preset) { this.autosaved = DU.toPlain(preset); store.set("du.autosave", this.autosaved); },
};

// ------------------------------------------------------------------ size of the world

/** The simulation runs in "screen points" like the desktop app: small screens are simulated a
    little larger and drawn smaller, huge ones smaller and drawn larger, so presets keep their look. */
function measure() {
  const cw = Math.max(1, window.innerWidth), ch = Math.max(1, window.innerHeight);
  let s = 1;                                               // css px per world px
  if (Math.min(cw, ch) < 700) s = Math.min(cw, ch) / 700;
  if (Math.max(cw, ch) / s > 2560) s = Math.max(cw, ch) / 2560;
  const dpr = Math.min(window.devicePixelRatio || 1, 2), world = [Math.round(cw / s), Math.round(ch / s)];
  const scale = Math.min(s * dpr, 3840 / world[0], 2400 / world[1]);   // keep the trail buffers sane on 5K screens
  return { world, css: s, scale };
}

// ------------------------------------------------------------------ the cursor

const input = { x: 0, y: 0, down: false, tap: 0, real: false, outside: true, leftAt: 0, ghostT: 0, lastMove: 0, ghosting: false };
const mouse = new DU.Mouse(() => {
  const pressed = input.down || input.tap > 0;
  if (input.tap > 0) input.tap--;
  return [input.x, input.y, pressed];
});

// ------------------------------------------------------------------ state

const app = {
  key: null, preset: null, uni: null, renderer: null, geo: measure(),
  paused: false, rotate: store.get("du.rotate", false), hideUi: false,
  shownAt: 0, fps: 60, edited: false, message: "", messageAt: 0,
};

const canvas = $("sky");
try {
  app.renderer = new DU.Renderer(canvas);
} catch (e) {
  $("fatal").textContent = "This browser can’t run WebGL: " + e.message;
  $("fatal").classList.add("show");
  return;
}
canvas.style.width = "100vw"; canvas.style.height = "100vh";
app.renderer.resize(app.geo.world, app.geo.scale);
input.x = app.geo.world[0] * 0.5; input.y = app.geo.world[1] * 0.5;

function say(text, ms = 2600) {
  const t = $("toast");
  t.innerHTML = text; t.classList.add("show");
  clearTimeout(say.timer); say.timer = setTimeout(() => t.classList.remove("show"), ms);
  app.message = text.replace(/<[^>]+>/g, ""); app.messageAt = performance.now();
}

// ------------------------------------------------------------------ presets

function restart() {
  app.uni = new DU.Universe(DU.normalise(app.preset), app.geo.world, mouse);
  app.renderer.clear(app.preset.background);
  app.shownAt = performance.now();
}

function show(key, preset, { quiet = false } = {}) {
  app.key = key; app.preset = DU.normalise(preset); app.edited = false;
  restart();
  hud();
  if (key && key !== AUTOSAVE) { store.set("du.last", key); history.replaceState(null, "", "#" + encodeURIComponent(key)); }
  else history.replaceState(null, "", location.pathname + location.search);
  markGallery();
  panel.sync();
  if (!quiet) wake(7000);
}

function load(key, opts) { if (lib.has(key)) show(key, lib.get(key), opts); }

function step(dir) {
  const keys = [...ORDER, ...lib.mineKeys()];
  const i = keys.indexOf(app.key);
  load(keys[((i < 0 ? -1 : i) + dir + keys.length) % keys.length]);
}

function hud() {
  const p = app.preset, slot = lib.slot(app.key);
  $("hTitle").textContent = p.title;
  $("hSlot").textContent = slot ? `press ${slot}` : "";
  $("hGroup").textContent = app.key ? lib.group(app.key) : "New preset";
  $("hDesc").textContent = p.description || "";
  $("barTitle").textContent = p.title;
  document.title = `${p.title} · DesktopUniverse`;
}

// ------------------------------------------------------------------ the gallery

function buildGallery() {
  const root = $("gGroups");
  root.replaceChildren();
  const groups = DATA.groups.map(([g, keys]) => [g, keys]);
  if (lib.mineKeys().length) groups.push([MINE, lib.mineKeys()]);
  for (const [group, keys] of groups) {
    const h = document.createElement("h3");
    h.innerHTML = `${group}<span>${keys.length}</span>`;
    const grid = document.createElement("div");
    grid.className = "grid";
    for (const k of keys) {
      const b = document.createElement("button");
      b.className = "card"; b.dataset.key = k;
      if (k in DATA.presets) {
        const img = document.createElement("img");
        img.loading = "lazy"; img.alt = lib.title(k); img.src = `thumbs/${k}.jpg`;
        b.append(img);
      } else { const ph = document.createElement("div"); ph.className = "ph"; b.append(ph); }
      const name = document.createElement("div");
      name.className = "name";
      const slot = lib.slot(k);
      name.innerHTML = `<span></span>${slot ? `<small>${slot}</small>` : ""}`;
      name.firstChild.textContent = lib.title(k);
      b.append(name);
      b.onclick = () => { load(k); gallery(false); };
      grid.append(b);
    }
    root.append(h, grid);
  }
  markGallery();
}

function markGallery() {
  for (const c of document.querySelectorAll(".card")) c.classList.toggle("current", c.dataset.key === app.key);
}

function gallery(open) {
  const g = $("gallery");
  if (open === undefined) open = !g.classList.contains("open");
  if (open) { buildGallery(); panelOpen(false); }
  g.classList.toggle("open", open);
  if (open) { const cur = g.querySelector(".card.current"); if (cur) cur.scrollIntoView({ block: "center" }); }
}

// ------------------------------------------------------------------ the tuning panel

const panel = new DU.Panel({
  state: () => ({ key: app.key, preset: app.preset, editable: lib.isMine(app.key), fps: app.fps,
                  counts: app.uni ? app.uni.counts() : {}, paused: app.paused,
                  message: performance.now() - app.messageAt < 4000 ? app.message : "" }),
  listing: () => lib.listing(),
  apply(P) {                                               // a live edit
    app.preset = DU.normalise(P); app.edited = true;
    app.uni.reconfigure(app.preset);
    hud();
    clearTimeout(this.autosaveTimer);
    this.autosaveTimer = setTimeout(() => lib.autosave(app.preset), 1500);
  },
  load: (key) => load(key),
  blank() {
    show(null, { title: "New preset", layers: [{ name: "dust", count: 15000,
      pulls: [{ source: "above", field: { law: "classic", strength: 20, min_dist: 10 } }] }] });
  },
  save() {
    if (!lib.isMine(app.key)) return say("The built-in presets are read-only: use “Save as”");
    lib.mine[app.key] = DU.toPlain(app.preset); lib.persist(); app.edited = false;
    say("Saved");
  },
  saveAs(name) {
    try { const key = lib.save(name, app.preset); show(key, lib.get(key), { quiet: true }); say(`Saved as “${lib.title(key)}”`); }
    catch (e) { say(e.message); }
  },
  rename(name) {
    try { const key = lib.rename(app.key, name); app.key = key; show(key, lib.get(key), { quiet: true }); say("Renamed"); }
    catch (e) { say(e.message); }
  },
  remove() {
    if (!lib.isMine(app.key)) return;
    const title = lib.title(app.key);
    lib.remove(app.key); say(`Deleted “${title}”`); load(DATA.slots[0]);
  },
  reset() { if (app.key) load(app.key, { quiet: true }); },
  exportJson() {
    const p = DU.toPlain(app.preset);
    const blob = new Blob([JSON.stringify(p, null, 2)], { type: "application/json" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = (lib.slug(p.title) || "preset") + ".json";
    a.click();
    setTimeout(() => URL.revokeObjectURL(a.href), 1000);
    say("Downloaded: drop it into the desktop version’s <b>presets_user/</b> folder to find it in the menu");
  },
  importJson(text) {
    try {
      const p = DU.normalise(JSON.parse(text));
      if (!p.layers.length) throw new Error("it has no layers");
      show(null, p, { quiet: true }); say(`Opened “${p.title}”: use “Save as” to keep it`);
    } catch (e) { say("Can’t read this file: " + e.message); }
  },
  restart: () => restart(),
});

function panelOpen(open) {
  if (open === undefined) open = !$("panel").classList.contains("open");
  $("panel").classList.toggle("open", open);
  $("bTune").classList.toggle("on", open);
  if (open) { panel.sync(true); gallery(false); }
}

// ------------------------------------------------------------------ waking the interface

let wakeUntil = 0;
function wake(ms = 3500) { wakeUntil = Math.max(wakeUntil, performance.now() + ms); refreshUi(); }
function refreshUi() {
  const now = performance.now(), awake = now < wakeUntil || barHover || $("panel").classList.contains("open");
  $("bar").classList.toggle("away", app.hideUi || !awake);
  $("hud").classList.toggle("dim", app.hideUi || now > wakeUntil);
  document.body.classList.toggle("hide-ui", app.hideUi);
}
let barHover = false;
$("bar").addEventListener("pointerenter", () => { barHover = true; refreshUi(); });
$("bar").addEventListener("pointerleave", () => { barHover = false; wake(1500); });

// ------------------------------------------------------------------ input

function toWorld(e) {
  // the cursor jumped (the ghost handed over, it came back into the window, a new touch): start its
  // velocity afresh, or the jump would read as a violent swipe
  if (input.ghosting || input.outside || e.pointerType === "touch" && e.type === "pointerdown") mouse.first = true;
  input.ghosting = false;
  input.x = e.clientX / app.geo.css; input.y = e.clientY / app.geo.css;
}
canvas.addEventListener("pointermove", (e) => {
  toWorld(e); input.real = true; input.outside = false; input.lastMove = performance.now();
  if (e.clientY > window.innerHeight - 140 || e.pointerType === "touch") wake();
});
canvas.addEventListener("pointerdown", (e) => {
  toWorld(e); input.real = true; input.outside = false;
  if (e.pointerType === "touch") { input.tap = 2; wake(); }   // a tap is a click; holding is not "pressed"
  else {                                                  // held for at least one step, however quick the click
    input.down = true; input.tap = Math.max(input.tap, 1);
    try { canvas.setPointerCapture(e.pointerId); } catch (err) { /* ok */ }
  }
});
const up = () => { input.down = false; };
window.addEventListener("pointerup", up);
window.addEventListener("pointercancel", up);
document.addEventListener("pointerleave", () => { input.outside = true; input.leftAt = performance.now(); });
document.documentElement.addEventListener("mouseleave", () => { input.outside = true; input.leftAt = performance.now(); });

/** Nobody at the mouse (yet, or it left the window): a ghost cursor drifts slowly around the middle. */
function ghost() {
  const idle = !input.real || (input.outside && performance.now() - input.leftAt > 3000);
  if (!idle) return;
  if (!input.ghosting) mouse.first = true;                 // taking over from wherever the cursor was
  input.ghosting = true;
  input.ghostT += 1 / 60;
  const [W, H] = app.geo.world, t = input.ghostT;
  input.x = W / 2 + 0.36 * W * Math.cos(t / 7.0);
  input.y = H / 2 + 0.34 * H * Math.sin(t / 5.3);
}

$("bPrev").onclick = () => step(-1);
$("bNext").onclick = () => step(1);
$("bTitle").onclick = () => gallery(true);
$("gClose").onclick = () => gallery(false);
$("gallery").addEventListener("click", (e) => { if (e.target.id === "gallery") gallery(false); });
$("bPause").onclick = () => pause();
$("bClear").onclick = () => app.renderer.clear(app.preset.background);
$("bRestart").onclick = () => restart();
$("bRotate").onclick = () => rotate();
$("bTune").onclick = () => panelOpen();
$("pClose").onclick = () => panelOpen(false);
$("bFull").onclick = () => fullscreen();
$("bGithub").onclick = () => window.open(REPO, "_blank", "noopener");

function pause(v) {
  app.paused = v === undefined ? !app.paused : v;
  $("lPause").textContent = app.paused ? "Resume" : "Pause";
  $("iPause").innerHTML = app.paused ? '<path d="M7 5l12 7-12 7z"/>' : '<path d="M8 5v14M16 5v14"/>';
  $("bPause").classList.toggle("on", app.paused);
}
function rotate(v) {
  app.rotate = v === undefined ? !app.rotate : v;
  store.set("du.rotate", app.rotate);
  $("bRotate").classList.toggle("on", app.rotate);
  app.shownAt = performance.now();
  if (v === undefined) say(app.rotate ? `Slideshow: a new preset every ${ROTATE_SECONDS} seconds` : "Slideshow off");
}
function fullscreen() {
  if (document.fullscreenElement) document.exitFullscreen();
  else if (document.documentElement.requestFullscreen) document.documentElement.requestFullscreen().catch(() => {});
}

document.addEventListener("keydown", (e) => {
  const tag = (document.activeElement && document.activeElement.tagName) || "";
  if (["INPUT", "SELECT", "TEXTAREA"].includes(tag) || e.metaKey || e.ctrlKey || e.altKey) return;
  const k = e.key;
  if (k === "Escape") { gallery(false); panelOpen(false); return; }
  if (/^[1-9]$/.test(k)) load(DATA.slots[+k - 1]);
  else if (k === "ArrowRight") step(1);
  else if (k === "ArrowLeft") step(-1);
  else if (k === " ") pause();
  else if (k === "c" || k === "C") app.renderer.clear(app.preset.background);
  else if (k === "r" || k === "R") restart();
  else if (k === "g" || k === "G") gallery();
  else if (k === "p" || k === "P") panelOpen();
  else if (k === "f" || k === "F") fullscreen();
  else if (k === "h" || k === "H") { app.hideUi = !app.hideUi; refreshUi(); if (!app.hideUi) wake(); }
  else if (k === "i" || k === "I") $("fps").classList.toggle("show");
  else return;
  e.preventDefault();
  if (!app.hideUi) wake();
});

window.addEventListener("hashchange", () => {
  const k = decodeURIComponent(location.hash.slice(1));
  if (k && k !== app.key && lib.has(k)) load(k);
});

let resizeTimer = 0;
window.addEventListener("resize", () => {
  clearTimeout(resizeTimer);
  resizeTimer = setTimeout(() => {
    const g = measure();
    if (g.world[0] === app.geo.world[0] && g.world[1] === app.geo.world[1] && g.scale === app.geo.scale) return;
    const kx = g.world[0] / app.geo.world[0], ky = g.world[1] / app.geo.world[1];
    app.geo = g;
    input.x *= kx; input.y *= ky;
    app.renderer.resize(g.world, g.scale);
    restart();
  }, 250);
});

// ------------------------------------------------------------------ the loop

let last = 0, acc = 0, fpsFrames = 0, fpsT = 0;
function loop(now) {
  requestAnimationFrame(loop);
  const dt = last ? Math.min(0.1, (now - last) / 1000) : 1 / 60;
  last = now;
  if (now > wakeUntil - 50 && now < wakeUntil + 400) refreshUi();
  if (app.paused || !app.uni) return;
  acc += dt;
  if (acc < 1 / 60 - 0.002) return;                        // high refresh screens: still 60 steps a second
  acc = Math.min(acc - 1 / 60, 1 / 60);
  ghost();
  app.uni.step();
  app.renderer.frame(app.uni);
  fpsFrames++;
  if (now - fpsT > 1000) {
    app.fps = fpsFrames * 1000 / (now - fpsT); fpsFrames = 0; fpsT = now;
    const counts = Object.entries(app.uni.counts()).map(([k, v]) => `${k} ${v}`).join(" · ");
    $("fps").textContent = `${app.fps.toFixed(0)} fps · ${app.geo.world.join("×")}\n${counts}`;
    panel.status();
  }
  if (app.rotate && now - app.shownAt > ROTATE_SECONDS * 1000 && !$("panel").classList.contains("open")) step(1);
}

// ------------------------------------------------------------------ start

const fromHash = decodeURIComponent(location.hash.slice(1));
const first = lib.has(fromHash) ? fromHash : lib.has(store.get("du.last", "")) ? store.get("du.last") : DATA.slots[0];
load(first);
rotate(app.rotate);
$("bRotate").classList.toggle("on", app.rotate);
if (!store.get("du.seen", false)) {
  store.set("du.seen", true);
  const touch = window.matchMedia && window.matchMedia("(pointer: coarse)").matches;
  setTimeout(() => say(touch ? "Drag a finger through them to play, tap to click · the squares button shows them all"
                             : "Move the mouse to play · <kbd>←</kbd> <kbd>→</kbd> next / previous · <kbd>G</kbd> all presets · <kbd>P</kbd> tune", 7000), 1200);
}
requestAnimationFrame(loop);
window.DU_APP = app;                                       // for the console
})();
