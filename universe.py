"""
DesktopUniverse: a full-screen particle playground.

    python universe.py                      # default preset, panel opens in the browser
    python universe.py galaxy               # pick a preset
    python universe.py --wallpaper          # live wallpaper under the desktop icons (macOS)
    python universe.py --window 1280x720    # a normal window
    python universe.py --list               # list presets

Tune everything live in the panel (http://127.0.0.1:8765). Keys, when the
window has focus:

    Esc / Q   quit              1-9, <- ->  switch preset
    R         restart           C           clear screen
    Space     pause             F           show info
    [  ]      frame cap
"""

from __future__ import annotations

import argparse
import copy
import os
import re
import sys
import time
import webbrowser

import pygame

import desktop
import presets
from config import from_dict, problems, to_dict
from engine import Mouse, Universe
from panel import Panel


class App:
    def __init__(self, key, fps, size=None, wallpaper=False, panel_port=8765,
                 open_browser=True, global_mouse=False):
        os.environ.setdefault("SDL_VIDEO_CENTERED", "1")
        pygame.init()
        flags = 0 if size else pygame.NOFRAME
        self.screen = pygame.display.set_mode(size or (0, 0), flags)
        pygame.display.set_caption("DesktopUniverse")

        self.mode = "window" if size else "fullscreen"
        if wallpaper:
            why = desktop.make_wallpaper()
            if why:
                print(f"wallpaper mode unavailable: {why}")
            else:
                self.mode = "wallpaper"
        read, how = desktop.mouse_reader(prefer_global=global_mouse or wallpaper)
        self.mouse = Mouse(read)
        print(f"mode: {self.mode}, mouse: {how}")

        self.fps = fps
        self.clock = pygame.time.Clock()
        self.font = pygame.font.SysFont(
            "pingfangsc,hiraginosansgb,microsoftyaheiui,microsoftyahei,"
            "notosanscjksc,notosanscjk,wenquanyimicrohei,simhei", 20)
        self.paused = False
        self.show_info = False
        self.banner_until = 0.0
        self.running = True
        self.version = 0
        self.last_publish = 0.0
        self.dirty_since = None          # when the panel last changed something unsaved

        self.library = presets.Library()
        self.key = key
        self.load(key)

        self.panel = None
        if panel_port:
            try:
                self.panel = Panel(panel_port)
                print(f"panel: {self.panel.url}")
                if open_browser:
                    webbrowser.open(self.panel.url)
            except OSError as e:
                print(f"panel disabled: {e}")
        if self.mode == "wallpaper" and not self.panel:
            print("the wallpaper ignores the keyboard: quit with Ctrl+C here")

    # ---------------------------------------------------------- presets
    def load(self, key, preset=None):
        self.key = key
        self.preset = preset or self.library.get(key)
        self.universe = Universe(self.preset, self.screen, self.mouse)
        self.banner_until = time.time() + 2.0
        self.version += 1

    def switch(self, step=None, index=None):
        keys = self.library.keys()
        i = keys.index(self.key) if self.key in keys else 0
        i = index if index is not None else i + step
        if 0 <= i < len(keys) or step is not None:
            self.load(keys[i % len(keys)])

    def save(self, name, data):
        name = re.sub(r"[^\w\-]+", "_", name, flags=re.UNICODE).strip("_")[:60]
        if not name or name == presets.AUTOSAVE:
            return
        preset = from_dict(data) if data else self.preset
        if name != self.key:
            preset.title = name          # a new save is listed under the name you typed
        print(f"saved {self.library.save(name, preset)}")
        self.library.reload()
        self.key, self.preset = name, preset
        self.universe.reconfigure(preset)
        self.version += 1

    def delete(self, key):
        if self.library.delete(key):
            print(f"deleted presets_user/{key}.json")
            self.library.reload()
            # a deleted copy of a built-in falls back to the built-in, anything else to default
            self.load(key if key in self.library else presets.DEFAULT)

    def autosave(self):
        """Keep the latest experiment on disk, a few seconds after the last change."""
        if self.dirty_since and time.time() - self.dirty_since > 3:
            self.dirty_since = None
            try:
                self.library.autosave(self.preset)
                self.library.reload()            # refreshes the panel's list, not the form
            except OSError as e:
                print(f"autosave failed: {e}")

    # ---------------------------------------------------------- panel
    def handle_panel(self):
        if not self.panel:
            return
        for kind, data in self.panel.messages():
            try:
                if kind == "preset":
                    self.preset = from_dict(data)
                    self.universe.reconfigure(self.preset)
                    self.dirty_since = time.time()
                elif kind == "load" and data.get("key") in self.library:
                    self.load(data["key"])
                elif kind == "restart":
                    self.load(self.key, copy.deepcopy(self.preset))
                elif kind == "reset":
                    self.library.reload()
                    self.load(self.key if self.key in self.library else presets.DEFAULT)
                elif kind == "pause":
                    self.paused = not self.paused
                elif kind == "clear":
                    self.screen.fill((0, 0, 0))
                elif kind == "save":
                    self.save(str(data.get("name", "")), data.get("preset"))
                elif kind == "delete":
                    self.delete(str(data.get("key", "")))
                elif kind == "quit":
                    self.running = False
            except Exception as e:      # a bad edit must not kill the wallpaper
                print(f"panel request {kind!r} failed: {e}")

    def publish(self):
        if not self.panel or time.time() - self.last_publish < 0.25:
            return
        self.last_publish = time.time()
        self.panel.publish({
            "version": self.version,
            "current": self.key,
            "presets": self.library.listing(),
            "preset": to_dict(self.preset),
            "fps": self.clock.get_fps(),
            "counts": self.universe.counts(),
            "paused": self.paused,
            "mode": self.mode,
            "problems": problems(self.preset),
        })

    # ---------------------------------------------------------- window
    def handle_event(self, e):
        if e.type == pygame.QUIT:
            self.running = False
        if e.type != pygame.KEYDOWN:
            return
        k = e.key
        if k in (pygame.K_ESCAPE, pygame.K_q):
            self.running = False
        elif pygame.K_1 <= k <= pygame.K_9:
            self.switch(index=k - pygame.K_1)
        elif k == pygame.K_RIGHT:
            self.switch(step=1)
        elif k == pygame.K_LEFT:
            self.switch(step=-1)
        elif k == pygame.K_r:
            self.load(self.key, copy.deepcopy(self.preset))
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

    def overlay_lines(self):
        lines = []
        if time.time() < self.banner_until or self.show_info:
            lines.append(self.preset.title)
        if self.show_info:
            counts = "  ".join(f"{k} {v}" for k, v in self.universe.counts().items())
            lines.append(f"fps {self.clock.get_fps():.0f} (cap {self.fps or 'off'})   {counts}")
            if self.panel:
                lines.append(f"panel {self.panel.url}")
            if self.paused:
                lines.append("paused")
        return lines

    def present(self):
        """Draw the overlay for this flip only, so it never burns into trails."""
        lines = self.overlay_lines()
        if not lines:
            pygame.display.flip()
            return
        surfs = [self.font.render(t, True, (200, 200, 200)) for t in lines]
        rect = pygame.Rect(12, 12, max(s.get_width() for s in surfs) + 8, 24 * len(surfs) + 4)
        rect = rect.clip(self.screen.get_rect())
        backup = self.screen.subsurface(rect).copy()
        for i, s in enumerate(surfs):
            self.screen.blit(s, (16, 14 + 24 * i))
        pygame.display.flip()
        self.screen.blit(backup, rect)

    def run(self):
        try:
            while self.running:
                for e in pygame.event.get():
                    self.handle_event(e)
                self.handle_panel()
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
            if self.dirty_since:
                self.dirty_since = 0.0
                self.autosave()
            if self.panel:
                self.panel.close()
            pygame.quit()


def main():
    ap = argparse.ArgumentParser(description="DesktopUniverse particle playground")
    ap.add_argument("preset", nargs="?", default=presets.DEFAULT, help="preset key (see --list)")
    ap.add_argument("--list", action="store_true", help="list presets and exit")
    ap.add_argument("--fps", type=int, default=60, help="frame cap, 0 = uncapped (default 60)")
    ap.add_argument("--window", metavar="WxH", help="run in a normal window, e.g. 1280x720")
    ap.add_argument("--wallpaper", action="store_true", help="live wallpaper under the icons (macOS)")
    ap.add_argument("--port", type=int, default=8765, help="panel port (default 8765)")
    ap.add_argument("--no-panel", action="store_true", help="do not start the tuning panel")
    ap.add_argument("--no-browser", action="store_true", help="start the panel but do not open it")
    ap.add_argument("--global-mouse", action="store_true",
                    help="track the cursor outside the window (pyautogui; automatic on macOS)")
    args = ap.parse_args()

    library = presets.Library()
    if args.list:
        group = None
        for i, (k, title, g, _) in enumerate(library.listing(), 1):
            if g != group:
                print(f"\n{g}")
                group = g
            levels = " -> ".join(f"{l.name} {l.count}" for l in library.items[k].layers)
            print(f"{i:3d}. {k:18s} {title}   ({levels})")
        return
    if args.preset not in library:
        sys.exit(f"unknown preset {args.preset!r}; try --list")
    size = tuple(map(int, args.window.lower().split("x"))) if args.window else None
    App(args.preset, args.fps, size, wallpaper=args.wallpaper,
        panel_port=None if args.no_panel else args.port,
        open_browser=not args.no_browser, global_mouse=args.global_mouse).run()


if __name__ == "__main__":
    main()
