"""
Platform glue: reading the cursor anywhere on screen, and pinning the window
to the desktop as a live wallpaper (macOS, via pyobjc).
"""

from __future__ import annotations

import sys

import pygame


def _appkit():
    try:
        import AppKit  # noqa: F401  (pyobjc-framework-Cocoa)
        return AppKit
    except ImportError:
        return None


def mouse_reader(prefer_global: bool):
    """Return read() -> (x, y, left_button_down) in window coordinates.

    On macOS with pyobjc the cursor is read globally, so it keeps working when
    the window is a wallpaper or another app (the panel) has focus.
    """
    AppKit = _appkit() if sys.platform == "darwin" else None
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
            c = w.contentRectForFrameRect_(w.frame())   # the drawable area, same coordinates
            # to window coordinates: origin top-left of the content area
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
            print("pyautogui is not installed; falling back to the window's mouse")

    def read_pygame():
        x, y = pygame.mouse.get_pos()
        return x, y, pygame.mouse.get_pressed()[0]
    return read_pygame, "window"


def make_wallpaper() -> str | None:
    """Sink the pygame window under the desktop icons and let clicks pass
    through. Returns None on success, or a reason it could not be done."""
    if sys.platform != "darwin":
        return "wallpaper mode currently supports macOS only"
    AppKit = _appkit()
    try:
        import Quartz
    except ImportError:
        Quartz = None
    if AppKit is None or Quartz is None:
        return "install pyobjc first:  pip install pyobjc-framework-Quartz"

    app = AppKit.NSApplication.sharedApplication()
    # one level above the desktop picture, below the desktop icons
    level = Quartz.CGWindowLevelForKey(Quartz.kCGDesktopWindowLevelKey) + 1
    behavior = (AppKit.NSWindowCollectionBehaviorCanJoinAllSpaces      # every Space
                | AppKit.NSWindowCollectionBehaviorStationary          # stays put in Mission Control
                | AppKit.NSWindowCollectionBehaviorIgnoresCycle)       # not in Cmd-`
    screen = AppKit.NSScreen.screens()[0].frame()
    windows = list(app.windows())
    if not windows:
        return "could not find the pygame window"
    for w in windows:
        w.setLevel_(level)
        w.setIgnoresMouseEvents_(True)
        w.setCollectionBehavior_(behavior)
        w.setHasShadow_(False)
        w.setFrameOrigin_(screen.origin)
    # no Dock icon or menu bar for a wallpaper; quit from the panel or with Ctrl+C
    app.setActivationPolicy_(AppKit.NSApplicationActivationPolicyAccessory)
    return None
