"""
macOS glue: the global cursor, the wallpaper window, the menu-bar icon and
global hotkeys. Everything degrades quietly when pyobjc (or macOS) is missing.

Menu and hotkey actions are handed to `post(cmd, data)`, the same queue the
web panel uses, so the main loop treats them all alike.
"""

from __future__ import annotations

import os
import plistlib
import sys
from pathlib import Path

import pygame

DIGITS = "123456789"
# US layout key codes for 1-9, in case a layout reports other characters with Option held
DIGIT_KEYCODES = {18: "1", 19: "2", 20: "3", 21: "4", 23: "5", 22: "6", 26: "7", 28: "8", 25: "9"}
LEFT_ARROW, RIGHT_ARROW = 123, 124
ROTATE_CHOICES = [(0, "关闭"), (5, "每 5 分钟"), (15, "每 15 分钟"), (30, "每 30 分钟"), (60, "每小时")]
LAUNCH_AGENT = Path.home() / "Library" / "LaunchAgents" / "com.desktopuniverse.wallpaper.plist"



def _appkit():
    if sys.platform != "darwin":
        return None
    try:
        import AppKit
        return AppKit
    except ImportError:
        return None


# ------------------------------------------------------------------ cursor

def mouse_reader(prefer_global: bool):
    """read() -> (x, y, left_button_down) in window coordinates, plus a description."""
    AppKit = _appkit()
    if AppKit is not None:
        NSEvent = AppKit.NSEvent
        app = AppKit.NSApplication.sharedApplication()

        def read_mac():
            p = NSEvent.mouseLocation()                 # screen points, origin bottom-left
            pressed = bool(NSEvent.pressedMouseButtons() & 1)
            wins = app.windows()
            if not wins:
                return p.x, p.y, pressed
            w = wins[0]
            c = w.contentRectForFrameRect_(w.frame())
            return p.x - c.origin.x, c.origin.y + c.size.height - p.y, pressed
        return read_mac, "global (macOS)"

    if prefer_global:
        try:
            import pyautogui

            def read_pyautogui():
                p = pyautogui.position()
                return p.x, p.y, pygame.mouse.get_pressed()[0]
            return read_pyautogui, "global (pyautogui)"
        except ImportError:
            pass

    def read_pygame():
        x, y = pygame.mouse.get_pos()
        return x, y, pygame.mouse.get_pressed()[0]
    return read_pygame, "window"


# ------------------------------------------------------------------ wallpaper

def make_wallpaper() -> str | None:
    """Sink the pygame window under the desktop icons, on every Space, and let
    clicks pass through. Returns None on success, or why it could not."""
    AppKit = _appkit()
    if AppKit is None:
        return "needs macOS with pyobjc (pip install -r requirements.txt)"
    try:
        import Quartz
    except ImportError:
        return "pip install pyobjc-framework-Quartz"
    app = AppKit.NSApplication.sharedApplication()
    windows = list(app.windows())
    if not windows:
        return "could not find the pygame window"
    level = Quartz.CGWindowLevelForKey(Quartz.kCGDesktopWindowLevelKey) + 1   # above the picture
    behavior = (AppKit.NSWindowCollectionBehaviorCanJoinAllSpaces
                | AppKit.NSWindowCollectionBehaviorStationary
                | AppKit.NSWindowCollectionBehaviorIgnoresCycle)
    screen = AppKit.NSScreen.screens()[0].frame()
    for w in windows:
        w.setLevel_(level)
        w.setIgnoresMouseEvents_(True)
        w.setCollectionBehavior_(behavior)
        w.setHasShadow_(False)
        w.setFrameOrigin_(screen.origin)
    app.setActivationPolicy_(AppKit.NSApplicationActivationPolicyAccessory)   # no Dock icon
    return None


# ------------------------------------------------------------------ menu bar + hotkeys

_TARGET_CLASS = None


def _target_class():
    """An Objective-C object whose act: method forwards menu clicks to Python."""
    global _TARGET_CLASS
    if _TARGET_CLASS is None:
        import objc
        from Foundation import NSObject

        class DesktopUniverseMenuTarget(NSObject):
            def initWithPost_(self, post):
                self = objc.super(DesktopUniverseMenuTarget, self).init()
                if self is None:
                    return None
                self.post = post
                return self

            def act_(self, sender):
                cmd, _, arg = str(sender.representedObject()).partition(":")
                self.post(cmd, {"key": arg} if arg else {})

        _TARGET_CLASS = DesktopUniverseMenuTarget
    return _TARGET_CLASS


class MacControls:
    """A ✦ in the menu bar and ⌃⌥ hotkeys, so the wallpaper never needs a browser.

    ⌃⌥1-9 switch preset, ⌃⌥← / ⌃⌥→ previous / next, ⌃⌥P pause, ⌃⌥C clear,
    ⌃⌥R restart. Global hotkeys
    need Accessibility permission for the app that runs Python (System
    Settings → Privacy & Security → Accessibility → your terminal)."""

    def __init__(self, post):
        self.post = post
        self.ok = False
        self.hotkeys = False
        self._sig = None
        AppKit = _appkit()
        if AppKit is None:
            return
        try:
            self.AppKit = AppKit
            self.target = _target_class().alloc().initWithPost_(post)
            bar = AppKit.NSStatusBar.systemStatusBar()
            self.item = bar.statusItemWithLength_(AppKit.NSVariableStatusItemLength)
            self.item.button().setTitle_("✦")
            self.item.button().setToolTip_("DesktopUniverse")
            self.ok = True
        except Exception as e:                      # never let the menu bar stop the wallpaper
            print(f"menu bar unavailable: {e}")
            return
        self._install_hotkeys()

    def _install_hotkeys(self):
        AppKit = self.AppKit
        need = AppKit.NSEventModifierFlagControl | AppKit.NSEventModifierFlagOption

        def on_key(event):
            try:
                if event.modifierFlags() & need != need:
                    return
                code = event.keyCode()
                if code == RIGHT_ARROW:
                    return self.post("next", {})
                if code == LEFT_ARROW:
                    return self.post("prev", {})
                ch = (event.charactersIgnoringModifiers() or "").lower()
                ch = DIGIT_KEYCODES.get(code, ch) if ch not in DIGITS else ch
                if ch in DIGITS:
                    self.post("slot", {"slot": int(ch)})
                elif ch == "p":
                    self.post("pause", {})
                elif ch == "c":
                    self.post("clear", {})
                elif ch == "r":
                    self.post("restart", {})
            except Exception:
                pass

        try:
            self._monitor = AppKit.NSEvent.addGlobalMonitorForEventsMatchingMask_handler_(
                AppKit.NSEventMaskKeyDown, on_key)
            self.hotkeys = True
        except Exception as e:
            print(f"global hotkeys unavailable: {e}")
            return
        try:
            from ApplicationServices import AXIsProcessTrusted
            if not AXIsProcessTrusted():
                print("hotkeys ⌃⌥1-9 need Accessibility permission: System Settings → Privacy & "
                      "Security → Accessibility → turn on your terminal app, then restart")
        except ImportError:
            pass

    def update(self, listing, current, paused, panel_url, rotate=0, autostart=False):
        """Rebuild the menu when something it shows has changed."""
        if not self.ok:
            return
        sig = (tuple(map(tuple, listing)), current, paused, panel_url, rotate, autostart)
        if sig == self._sig:
            return
        self._sig = sig
        AppKit = self.AppKit
        mods = AppKit.NSEventModifierFlagControl | AppKit.NSEventModifierFlagOption
        menu = AppKit.NSMenu.alloc().init()
        menu.setAutoenablesItems_(False)

        def add(title, payload=None, key="", checked=False, enabled=True, into=None):
            target_menu = into or menu
            if payload is None and not title:
                target_menu.addItem_(AppKit.NSMenuItem.separatorItem())
                return None
            it = AppKit.NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(title, "act:", key)
            if key:
                it.setKeyEquivalentModifierMask_(mods)
            it.setTarget_(self.target)
            it.setRepresentedObject_(payload or "")
            it.setState_(1 if checked else 0)
            it.setEnabled_(enabled and payload is not None)
            target_menu.addItem_(it)
            return it

        # built-ins by group, as submenus; the first nine carry ⌃⌥1-9
        groups: dict = {}
        for key, title, group, slot, editable in listing:
            groups.setdefault(group, []).append((key, title, slot, editable))
        for group, rows in groups.items():
            if all(e for *_, e in rows) or group == "自动保存":
                continue
            sub = AppKit.NSMenu.alloc().init()
            sub.setAutoenablesItems_(False)
            for key, title, slot, _ in rows:
                add(title, f"load:{key}", str(slot) if slot else "", key == current, into=sub)
            label = group + ("  ·  " + next(t for k, t, *_ in rows if k == current) if any(k == current for k, *_ in rows) else "")
            holder = AppKit.NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(label, None, "")
            holder.setSubmenu_(sub)
            menu.addItem_(holder)
        mine = [row for row in listing if row[4] or row[2] == "自动保存"]
        if mine:
            add("")
            for key, title, *_ in mine:
                add(title, f"load:{key}", "", key == current)
        add("")
        add("下一个", "next", "\uf703")                 # ⌃⌥→
        add("上一个", "prev", "\uf702")                 # ⌃⌥←
        rot = AppKit.NSMenu.alloc().init()
        rot.setAutoenablesItems_(False)
        for minutes, label in ROTATE_CHOICES:
            add(label, f"rotate:{minutes}", "", float(rotate or 0) == minutes, into=rot)
        holder = AppKit.NSMenuItem.alloc().initWithTitle_action_keyEquivalent_("自动轮换", None, "")
        holder.setSubmenu_(rot)
        menu.addItem_(holder)
        add("")
        add("继续" if paused else "暂停", "pause", "p")
        add("清屏", "clear", "c")
        add("重新开始", "restart", "r")
        add("")
        add("登录时自动启动", "autostart", "", autostart)
        add("打开调参面板（编辑预设）…", "panel" if panel_url else None)
        add("退出 DesktopUniverse", "quit")
        self.item.setMenu_(menu)

    def close(self):
        if self.ok:
            try:
                if getattr(self, "_monitor", None) is not None:
                    self.AppKit.NSEvent.removeMonitor_(self._monitor)
                self.AppKit.NSStatusBar.systemStatusBar().removeStatusItem_(self.item)
            except Exception:
                pass


# ------------------------------------------------------------------ start at login

def autostart_enabled() -> bool:
    return sys.platform == "darwin" and LAUNCH_AGENT.exists()


def set_autostart(on: bool, argv) -> str | None:
    """Install or remove a LaunchAgent that starts the wallpaper at login (no
    terminal window). Returns None on success, or why it could not."""
    if sys.platform != "darwin":
        return "start at login is only set up for macOS"
    try:
        if on:
            LAUNCH_AGENT.parent.mkdir(parents=True, exist_ok=True)
            log = Path.home() / "Library" / "Logs" / "DesktopUniverse.log"
            with open(LAUNCH_AGENT, "wb") as f:
                plistlib.dump({
                    "Label": "com.desktopuniverse.wallpaper",
                    "ProgramArguments": list(argv),
                    "WorkingDirectory": os.path.dirname(os.path.abspath(argv[-1])),
                    "RunAtLoad": True,
                    "LimitLoadToSessionType": "Aqua",
                    "ProcessType": "Interactive",
                    "StandardOutPath": str(log),
                    "StandardErrorPath": str(log),
                }, f)
        elif LAUNCH_AGENT.exists():
            LAUNCH_AGENT.unlink()
    except OSError as e:
        return f"could not change start at login: {e}"
    return None
