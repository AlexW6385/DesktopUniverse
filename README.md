# DesktopUniverse

A living particle wallpaper. Tens of thousands of particles orbit, flock,
flow and burst behind your desktop icons, built from a small set of rules
that can be stacked into layers and tuned live from a browser panel.

![all presets](docs/all.jpg)

41 built-in universes in six groups (宇宙 · 自然 · 混沌 · 几何 · 互动 · 文字), picked
from the menu bar; nine of them also sit on hotkeys 1–9. Every one is a few hundred
bytes of parameters over the same engine, and the panel lets you make your own.

## Run

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

python universe.py               # live wallpaper, on the preset you used last
python universe.py 4             # start on preset 4
python universe.py --window 1280x720
python universe.py --rotate 15     # next preset every 15 minutes
python universe.py --autostart on  # start the wallpaper at login (macOS LaunchAgent)
python universe.py --list
```

Control it without leaving the wallpaper (the panel is only for editing and never opens by itself):

- **the menu bar ✦**: every preset by group plus your own, next / previous, **自动轮换**
  (rotate every 5 / 15 / 30 / 60 minutes, in order or **随机顺序**), pause, **被窗口盖住时暂停**
  (the simulation sleeps while windows cover the desktop or you are on another Space, so it costs
  nothing while you work), clear, restart, **登录时自动启动** (start at login), the panel, quit
- **hotkeys**: `⌃⌥1`–`⌃⌥9` presets, `⌃⌥←` / `⌃⌥→` previous / next, `⌃⌥P` pause, `⌃⌥C` clear,
  `⌃⌥R` restart. macOS asks for Accessibility permission for the app that runs Python
  (System Settings → Privacy & Security → Accessibility → your terminal)
- **the panel** at <http://127.0.0.1:8765>: every parameter, live; keys `1`–`9`, `Space`, `C`, `R` work there too
- in `--window` mode, the window itself: `1`–`9`, `←` `→`, `Space`, `C`, `R`, `F` info, `[` `]` frame cap, `Esc`

## How a universe is built

A preset is a **stack of layers**. Each layer is a swarm of identical bodies,
and **a layer is only pulled by the layer directly above it**; the cursor sits
at the very top. The cursor and the screen centre are also available to every
layer as global sources.

```
mouse
  sun      1      moves on its own Lissajous path
    planet 4      orbits the sun
      moon 12     orbits the planets
        dust 30k  born on the moons, fades out: spirograph trails
```

Keep upper layers small: every body above is a separate source for every
body below (pulls costing more than 600k pairs per frame are skipped and
flagged in the panel).

### Mechanisms

| | |
| --- | --- |
| **Forces** | `classic` attraction `strength / r^power` (with an inner radius that can push), `vortex` (sideways: swirl), `ring` (a spring toward a circle), `drag` (match the source's velocity), `wake` (pushed along by a moving source: the cursor stirs), `startle` (pushed away in proportion to how fast the source moves: a still cursor is ignored, a sudden swipe scatters everything); any force can **absorb** (swallow what comes too close: an event horizon) |
| **Pulse** | any force can breathe on a sine; past 1 it swings between pull and push; rings breathe in radius |
| **Neighbourhoods** | `pressure` (flow from crowded to empty: sand piles up; negative clumps) and `align` (match neighbours: flocking), computed on a density grid in O(N) |
| **Home** | a spring back to the birth position; with grid spawning, an elastic sheet; on a path, an elastic curve the cursor can push |
| **Life** | particles die and are reborn; synced lifetimes plus teleporting parents make fireworks |
| **Births** | on (or in a ring around) the bodies of the layer above, at or around the cursor, on the pixels of a line of text; a click can burst particles out at the cursor; bursts can be a 3D shell seen head-on |
| **Text** | bodies spring to the glyphs of a line of text; lines separated by `\|` take turns, `{time}` `{date}` `{weekday}` are filled in live, so a swarm can be a clock or a poem |
| **Motion** | physics, wander, paths (Lissajous, rose, Spirograph, sunflower: Vogel's golden-angle spiral), a morphing Clifford / de Jong attractor, **3D attractors** (Lorenz, Aizawa, Thomas, Halvorsen, Rössler) in perspective that the cursor turns, **double pendulums**, **crystal growth** (diffusion-limited aggregation with noise reduction, grown in one wedge and mirrored into a snowflake), **slime mould** (Physarum agents that smell a scent map, turn toward it and lay more), teleport, fixed |
| **World** | flow field (as wind, or as a current that carries), gravity / wind (fixed, or tilting toward the cursor), walls (wrap, bounce, respawn), friction shape, linear damping (1 = no momentum: bodies walk down field lines), per-body variety, speed limits, temperature, a breathing light |
| **Paint** | trails from none to minutes long (fading fully to the background, dark or paper), additive glow, soft glowing dots, per-body twinkle, lines between neighbours (all in range or the nearest few, everywhere or only around the cursor), kaleidoscope symmetry with mirror, colour by palette drift, speed, direction, age, rainbow, the moment of birth or position in the layer |

Every one of these is a field in `config.py`; the panel builds itself from
the schema at the bottom of that file.

## Presets

| Group | Presets |
| --- | --- |
| 宇宙 | 双星系 ¹ · 星轨 ⁴ · 黑洞 · 彗星 · 超新星 · 土星环 · 曲速 · 星座 |
| 自然 | 鸟群 ⁵ · 雪景球 ⁸ · 烟花 ⁹ · 冰晶 · 黏菌 · 极光 · 鱼群 · 萤火虫 · 蒲公英 · 篝火 · 鬼火 |
| 混沌 | 奇异吸引子 ² · 蝴蝶效应 · 苹果核 · 混沌摆 · 掌中宇宙 |
| 几何 | 曼陀罗 ³ · 向日葵 · 电场线 · 万花筒 · 谐振子 · 原子 · 心跳 |
| 互动 | 弹性布 ⁶ · 墨流 ⁷ · 水彩 · 星尘笔 · 香烟 · 涟漪 · 精灵 · 弹珠 |
| 文字 | 星尘时钟 · 诗 |

Superscripts are the hotkey slots. Each preset's description (what it is
made of, and what the mouse does to it) shows in the panel. The built-ins are
read-only; your own presets are JSON files in `presets_user/`, created from
the panel: **新建** (blank), **保存** (update), **另存为** (create), **重命名**,
**删除**. Unsaved edits are autosaved every few seconds as **上次的实验**, and
the app reopens on the preset you used last.

## Layout

```
universe.py     the app: window / wallpaper, controls, panel wiring, presets CRUD
engine.py       the simulation: forces, neighbourhoods, swarms, painting
config.py       the data model and the panel schema
presets.py      the built-ins and the preset library
panel.py/.html  the local tuning panel
desktop.py      macOS: wallpaper window, menu bar, hotkeys, global cursor
tests/          forces, mechanisms, every preset, the library (python -m pytest tests)
```

Physics advances per frame, so the frame cap sets the pace (`[` `]`, `--fps`).
The project started as a single pygame script; its history is in git.
