"""
DesktopUniverse: a living particle wallpaper.

    python universe.py                  # live wallpaper (macOS), last preset you used
    python universe.py 3                # start on built-in preset 3 (or a preset key)
    python universe.py --window 1280x720
    python universe.py --fullscreen
    python universe.py --list

Control it without leaving the wallpaper: the menu-bar ✦ (presets, next /
previous, timed rotation, pause, start at login, quit) or the hotkeys
⌃⌥1-9, ⌃⌥← / ⌃⌥→, ⌃⌥P, ⌃⌥C, ⌃⌥R. The tuning panel at http://127.0.0.1:8765 is
only for editing (every parameter, live; create, save, rename and delete your
own presets) and never opens by itself in wallpaper mode. When the window has focus (not in
wallpaper mode): 1-9 presets, ← → all presets, Space pause, C clear,
R restart, F info, [ ] frame cap, Esc / Q quit.
"""

from __future__ import annotations

import argparse
import os
import queue
import sys
import time
import webbrowser

import pygame

import desktop
import presets
from config import from_dict, layer_template, problems, to_dict
from engine import Mouse, Universe, font_names
from panel import Panel


class App:
    def __init__(self, key=None, fps=60, mode="wallpaper", size=None, port=8765,
                 open_panel=None, global_mouse=False, rotate=None):
        os.environ.setdefault("SDL_VIDEO_CENTERED", "1")
        pygame.init()
        self.screen = pygame.display.set_mode(size or (0, 0), 0 if size else pygame.NOFRAME)
        pygame.display.set_caption("DesktopUniverse")

        self.mode = "window" if size else "fullscreen"
        if mode == "wallpaper" and not size:
            why = desktop.make_wallpaper()
            if why:
                print(f"wallpaper mode unavailable ({why}); running full screen")
            else:
                self.mode = "wallpaper"
        read, how = desktop.mouse_reader(prefer_global=global_mouse or self.mode == "wallpaper")
        self.mouse = Mouse(read)

        self.fps = fps
        self.clock = pygame.time.Clock()
        self.fonts = {}                         # for the overlay, by whether the text needs CJK glyphs
        self.paused = False
        self.show_info = False
        self.banner_until = 0.0
        self.running = True
        self.version = 0
        self.last_publish = 0.0
        self.dirty_since = None
        self.message = ""

        self.inbox: queue.Queue = queue.Queue()
        self.library = presets.Library()
        st = self.library.state()
        # by default a new preset every 15 minutes, in random order; the clock keeps running while
        # paused or covered, so it is "every quarter of an hour", not "every 15 minutes of showing"
        self.rotate = float(rotate if rotate is not None else st.get("rotate", 15))
        self.rotate_random = bool(st.get("rotate_random", True))
        self.pause_hidden = bool(st.get("pause_hidden", True))
        self.hidden = False
        self.last_visibility_check = 0.0
        self.switched_at = time.time()
        start = key or self.library.last() or presets.DEFAULT
        self.load(start if start in self.library else presets.DEFAULT)

        self.panel = None
        if port:
            try:
                self.panel = Panel(port, self.inbox)
            except OSError as e:
                print(f"panel disabled: {e}")
        self.controls = desktop.MacControls(lambda cmd, data: self.inbox.put((cmd, data)))

        print(f"mode: {self.mode} · mouse: {how} · menu bar: {'yes' if self.controls.ok else 'no'}"
              f" · hotkeys: {'⌃⌥1-9' if self.controls.hotkeys else 'no'}"
              f" · rotate: {f'every {self.rotate:g} min' if self.rotate else 'off'}")
        if self.panel:
            print(f"panel (for editing): {self.panel.url}")
            # a wallpaper should just run: the browser opens only when asked for
            if open_panel or (open_panel is None and self.mode != "wallpaper"):
                webbrowser.open(self.panel.url)
        if self.mode == "wallpaper" and not self.controls.ok:
            print("no menu bar: switch with ⌃⌥1-9 if hotkeys are on, quit with Ctrl+C here")

    # ---------------------------------------------------------- presets
    def load(self, key, preset=None):
        self.key = key
        self.preset = preset if preset is not None else self.library.get(key)
        self.universe = Universe(self.preset, self.screen, self.mouse)
        self.banner_until = time.time() + 2.5
        self.switched_at = time.time()
        self.version += 1
        if key:
            self.library.remember(key)

    def slot(self, n):
        if 1 <= n <= len(presets.SLOTS):
            self.load(presets.SLOTS[n - 1])

    def cycle(self, step):
        keys = [k for k in self.library.keys() if k != presets.AUTOSAVE]
        i = keys.index(self.key) if self.key in keys else -1
        self.load(keys[(i + step) % len(keys)])

    def set_rotate(self, minutes):
        self.rotate = max(0.0, float(minutes))
        self.switched_at = time.time()
        self.library.set_state(rotate=self.rotate)
        self.say(f"Rotating presets every {self.rotate:g} minutes" if self.rotate else "Rotating presets: off")

    def random_other(self):
        """A random preset that is not the current one (built-ins and yours)."""
        import random
        keys = [k for k in self.library.keys() if k != presets.AUTOSAVE and k != self.key]
        if keys:
            self.load(random.choice(keys))

    def check_visibility(self):
        """Pause the simulation while the wallpaper is covered by windows or off-Space."""
        now = time.time()
        if now - self.last_visibility_check < 0.5:
            return
        self.last_visibility_check = now
        visible = desktop.wallpaper_visible() if (self.pause_hidden and self.mode == "wallpaper") else None
        hidden = visible is False
        if hidden and not self.hidden:
            self.hidden_since = now
        elif not hidden and self.hidden:
            # don't count the time spent hidden toward rotation
            self.switched_at += now - self.hidden_since
        self.hidden = hidden

    def say(self, text):
        self.message = text
        print(text)

    # ---------------------------------------------------------- requests (panel, menu, hotkeys)
    def handle(self, kind, data):
        lib = self.library
        if kind == "preset":                       # a live edit from the panel
            self.preset = from_dict(data)
            self.universe.reconfigure(self.preset)
            self.dirty_since = time.time()
        elif kind == "load" and data.get("key") in lib:
            self.load(data["key"])
        elif kind == "slot":
            self.slot(int(data.get("slot", 0)))
        elif kind == "next":
            self.cycle(1)
        elif kind == "prev":
            self.cycle(-1)
        elif kind == "rotate":
            self.set_rotate(data.get("minutes", data.get("key", 0)) or 0)
        elif kind == "rotate_random":
            self.rotate_random = not self.rotate_random
            self.library.set_state(rotate_random=self.rotate_random)
            self.say("Rotating presets in random order" if self.rotate_random else "Rotating presets in list order")
        elif kind == "pause_hidden":
            self.pause_hidden = not self.pause_hidden
            self.library.set_state(pause_hidden=self.pause_hidden)
            self.say("Pause when covered by windows: on" if self.pause_hidden else "Pause when covered by windows: off")
        elif kind == "random":
            self.random_other()
        elif kind == "autostart":
            want = not desktop.autostart_enabled()
            why = desktop.set_autostart(want, launch_args())
            self.say(why or ("Starts at login from now on" if want else "No longer starts at login"))
        elif kind == "new":
            self.load(None, presets.blank())
        elif kind == "restart":
            self.load(self.key, self.preset)
        elif kind == "reset":
            lib.reload()
            if self.key in lib:
                self.load(self.key)
        elif kind == "pause":
            self.paused = not self.paused
        elif kind == "clear":
            self.screen.fill(tuple(self.preset.background))
        elif kind == "save":                       # create, or update when the name is the current one
            preset = from_dict(data["preset"]) if data.get("preset") else self.preset
            name = str(data.get("name") or "").strip()
            if not name and lib.is_custom(self.key):
                name = self.key
            try:
                key = lib.save(name, preset)
            except ValueError as e:
                return self.say(str(e))
            self.key, self.preset = key, lib.get(key)
            self.universe.reconfigure(self.preset)
            lib.remember(key)
            self.version += 1
            self.say(f"Saved: {self.preset.title}")
        elif kind == "rename":
            try:
                key = lib.rename(data.get("key", self.key), str(data.get("name", "")))
            except (KeyError, ValueError) as e:
                return self.say(str(e))
            if data.get("key", self.key) == self.key:
                self.key, self.preset.title = key, lib.get(key).title
                lib.remember(key)
            self.version += 1
            self.say("Renamed")
        elif kind == "delete":
            key = data.get("key", self.key)
            if lib.delete(key):
                self.say(f"Deleted: {key}")
                if key == self.key:
                    self.load(presets.DEFAULT)
                self.version += 1
        elif kind == "panel" and self.panel:
            webbrowser.open(self.panel.url)
        elif kind == "quit":
            self.running = False

    def drain(self):
        while True:
            try:
                kind, data = self.inbox.get_nowait()
            except queue.Empty:
                return
            try:
                self.handle(kind, data or {})
            except Exception as e:                 # a bad request must never kill the wallpaper
                self.say(f"request {kind!r} failed: {e}")

    def autosave(self, force=False):
        if self.dirty_since and (force or time.time() - self.dirty_since > 3):
            self.dirty_since = None
            try:
                self.library.autosave(self.preset)
            except OSError as e:
                print(f"autosave failed: {e}")

    def publish(self):
        if time.time() - self.last_publish < 0.25:
            return
        self.last_publish = time.time()
        listing = self.library.listing()
        if self.panel:
            self.panel.publish({
                "version": self.version,
                "current": self.key,
                "editable": self.library.is_custom(self.key),
                "presets": listing,
                "preset": to_dict(self.preset),
                "fps": self.clock.get_fps(),
                "counts": self.universe.counts(),
                "paused": self.paused,
                "hidden": self.hidden,
                "mode": self.mode,
                "hotkeys": self.controls.hotkeys,
                "problems": problems(self.preset),
                "message": self.message,
                "layer_template": layer_template(),
            })
        self.controls.update(listing, self.key, self.paused, self.panel.url if self.panel else None,
                             self.rotate, desktop.autostart_enabled(), self.rotate_random,
                             self.pause_hidden, self.hidden)

    # ---------------------------------------------------------- window
    def on_event(self, e):
        if e.type == pygame.QUIT:
            self.running = False
        if e.type != pygame.KEYDOWN:
            return
        k = e.key
        if k in (pygame.K_ESCAPE, pygame.K_q):
            self.running = False
        elif pygame.K_1 <= k <= pygame.K_9:
            self.slot(k - pygame.K_0)
        elif k == pygame.K_RIGHT:
            self.cycle(1)
        elif k == pygame.K_LEFT:
            self.cycle(-1)
        elif k == pygame.K_r:
            self.handle("restart", {})
        elif k == pygame.K_c:
            self.handle("clear", {})
        elif k == pygame.K_SPACE:
            self.paused = not self.paused
        elif k == pygame.K_f:
            self.show_info = not self.show_info
        elif k == pygame.K_RIGHTBRACKET:
            self.fps = min(240, self.fps + 10) if self.fps else 0
        elif k == pygame.K_LEFTBRACKET:
            self.fps = max(10, self.fps - 10) if self.fps else 60

    def overlay(self):
        lines = []
        if time.time() < self.banner_until or self.show_info:
            slot = presets.SLOTS.index(self.key) + 1 if self.key in presets.SLOTS else None
            lines.append(f"{slot} · {self.preset.title}" if slot else self.preset.title)
        if self.show_info:
            counts = "  ".join(f"{k} {v}" for k, v in self.universe.counts().items())
            lines.append(f"{self.clock.get_fps():.0f} fps (cap {self.fps or 'off'})   {counts}")
            if self.panel:
                lines.append(self.panel.url)
        if self.paused:
            lines.append("Paused")
        return lines

    def font_for(self, text):
        names = font_names(text)
        if names not in self.fonts:
            self.fonts[names] = pygame.font.SysFont(names, 22)
        return self.fonts[names]

    def present(self):
        """Draw the overlay for this flip only, so it never burns into trails."""
        lines = self.overlay()
        if not lines:
            pygame.display.flip()
            return
        surfs = [self.font_for(t).render(t, True, (215, 215, 215)) for t in lines]
        x, y = 28, self.screen.get_height() - 40 - 28 * len(surfs)     # bottom left, clear of the menu bar
        rect = pygame.Rect(x - 4, y - 4, max(s.get_width() for s in surfs) + 8, 28 * len(surfs) + 8)
        rect = rect.clip(self.screen.get_rect())
        backup = self.screen.subsurface(rect).copy()
        for i, s in enumerate(surfs):
            self.screen.blit(s, (x, y + 28 * i))
        pygame.display.flip()
        self.screen.blit(backup, rect)

    def run(self):
        try:
            while self.running:
                for e in pygame.event.get():
                    self.on_event(e)
                self.drain()
                self.check_visibility()
                if self.rotate and time.time() - self.switched_at >= self.rotate * 60:
                    self.random_other() if self.rotate_random else self.cycle(1)
                if self.hidden:                       # covered: sleep, keep the menu responsive
                    self.publish()
                    self.clock.tick(4)
                    continue
                if not self.paused:
                    self.universe.step()
                    self.universe.draw()
                self.present()
                self.publish()
                self.autosave()
                self.clock.tick(self.fps)
        except KeyboardInterrupt:
            pass
        finally:
            self.autosave(force=True)
            self.controls.close()
            if self.panel:
                self.panel.close()
            pygame.quit()


def launch_args():
    """How to start this wallpaper again (used for start-at-login)."""
    return [sys.executable, os.path.abspath(__file__)]


def main():
    ap = argparse.ArgumentParser(description="DesktopUniverse: a living particle wallpaper")
    ap.add_argument("preset", nargs="?", help="1-9 or a preset key (default: the last one you used)")
    ap.add_argument("--window", metavar="WxH", help="a normal window, e.g. 1280x720")
    ap.add_argument("--fullscreen", action="store_true", help="borderless full screen instead of wallpaper")
    ap.add_argument("--rotate", type=float, metavar="MIN", help="switch to the next preset every MIN minutes (0 = off)")
    ap.add_argument("--fps", type=int, default=60, help="frame cap, 0 = uncapped (default 60)")
    ap.add_argument("--port", type=int, default=8765, help="panel port (default 8765)")
    ap.add_argument("--no-panel", action="store_true", help="do not start the tuning panel at all")
    ap.add_argument("--open-panel", action="store_true", help="open the panel in the browser at start")
    ap.add_argument("--global-mouse", action="store_true", help="follow the cursor outside the window")
    ap.add_argument("--autostart", choices=["on", "off"], help="start the wallpaper when you log in (macOS)")
    ap.add_argument("--list", action="store_true", help="list presets and exit")
    args = ap.parse_args()

    if args.autostart:
        why = desktop.set_autostart(args.autostart == "on", launch_args())
        print(why or f"start at login: {args.autostart}")
        return
    lib = presets.Library()
    if args.list:
        for key, title, group, slot, _ in lib.listing():
            levels = " → ".join(f"{l.name} {l.count}" for l in lib.get(key).layers)
            print(f"{slot or ' '}  {key:16s} {title:20s} {f'[{group}]  ' if group else ''}{levels}")
        return
    key = args.preset
    if key and key.isdigit() and 1 <= int(key) <= len(presets.SLOTS):
        key = presets.SLOTS[int(key) - 1]
    if key and key not in lib:
        sys.exit(f"unknown preset {key!r}; try --list")
    size = tuple(map(int, args.window.lower().split("x"))) if args.window else None
    App(key, args.fps, "fullscreen" if args.fullscreen else "wallpaper", size,
        None if args.no_panel else args.port, True if args.open_panel else None,
        args.global_mouse, args.rotate).run()


if __name__ == "__main__":
    main()
