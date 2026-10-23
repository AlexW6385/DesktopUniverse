"""
The nine built-in presets (keys 1-9) and the library of your own.

Your presets live in presets_user/<key>.json, one file each, created by the
panel (or by hand: any field you leave out takes its default). The library
also keeps _autosave.json (your latest unsaved experiment) and _state.json
(which preset was showing last).
"""

from __future__ import annotations

import copy
import json
import re
from pathlib import Path

from config import ABOVE, CENTER, MOUSE, Attractor, Field, Flow, Layer, Palette, Preset, Pull, from_dict, to_dict

USER_DIR = Path(__file__).with_name("presets_user")
AUTOSAVE = "_autosave"
STATE = "_state"


def push(strength=250, radius=150):
    """The cursor shoves things out of a circle around it."""
    return Field("classic", strength, min_dist=3, inner_radius=radius, inner_gain=-1, outer_gain=0)


def sweep(strength=10, reach=220):
    """Moving the cursor stirs whatever it passes (a still cursor does nothing)."""
    return Field("wake", strength, max_dist=reach)


# ------------------------------------------------------------------ 1-9

def galaxy():
    return Preset(
        "双星系", "两个引力核心沿着同一条椭圆互相追逐，三万多颗星尘同时被吸引和旋转，"
        "被扯出旋臂和连接两者的星桥；鼠标划过会搅动它们",
        layers=[
            Layer("core", 2, motion="path", path_size=[0.36, 0.26], path_freq=[1, 1],
                  path_speed=0.01, path_spread=0.5, look="none"),
            Layer("stars", 34000, [
                Pull(ABOVE, Field("classic", 22, min_dist=10)),
                Pull(ABOVE, Field("vortex", 6, min_dist=10)),
                Pull(MOUSE, sweep(8, 260)),
            ], velocity="orbit", start_speed=4, jitter=0.05, variety=0.9,
                color_mode="speed", color=[60, 80, 200], color2=[255, 214, 160], speed_ref=5.5),
        ],
        friction=0.0004, trail=0.55, blend="add", glow=0.45,
    )


def strange_attractor():
    return Preset(
        "奇异吸引子", "六万个点每一帧都按 Clifford 映射跳一步，聚成一张会慢慢变形的分形；鼠标能把它推开",
        layers=[Layer("dust", 60000, [Pull(MOUSE, push(220, 140))], motion="attractor",
                      friction=0.05, color_mode="rainbow")],
        trail=0.82, blend="add", glow=0.22,
        palette=Palette(hue=200, hue_speed=5, saturation=0.65, value=0.9, spread=140),
        attractor=Attractor("clifford", -1.7, 1.8, -1.9, -0.4, scale=0.92, morph=0.18, morph_speed=0.012),
    )


def orrery():
    return Preset(
        "星轨", "四级层级：太阳沿轨迹漂移 → 行星绕太阳 → 卫星绕行星 → 卫星洒下会褪色的尘埃，画出一圈圈螺旋",
        layers=[
            Layer("sun", 1, motion="path", path_size=[0.22, 0.16], path_freq=[1, 1], path_speed=0.015,
                  look="dot", dot=16, color_mode="fixed", color=[255, 210, 140]),
            Layer("planet", 4, [Pull(ABOVE, Field("classic", 26, min_dist=20))],
                  spawn="above_ring", spawn_radius=170, velocity="orbit", start_speed=5.1, friction=0.0,
                  look="dot", dot=8, color_mode="fixed", color=[140, 190, 255]),
            Layer("moon", 12, [Pull(ABOVE, Field("classic", 40, min_dist=4, max_dist=80))],
                  spawn="above_ring", spawn_radius=18, velocity="orbit", start_speed=6.3, friction=0.0,
                  life=600, life_jitter=0.5, fade=False,
                  look="dot", dot=4, color_mode="fixed", color=[230, 230, 255]),
            Layer("dust", 30000, [Pull(MOUSE, sweep(12, 220))], spawn="above", velocity="inherit",
                  start_speed=0.4, life=260, life_jitter=0.5, friction=0.02,
                  color_mode="age", color=[255, 240, 210], color2=[60, 90, 220], brightness=1.3),
        ],
        friction=0.0005, blend="add", glow=0.6, trail=0.3, edge="respawn",
    )


def murmuration():
    return Preset(
        "鸟群", "三只领头鸟沿着看不见的曲线飞；一万五千只鸟被它们吸引，同时跟随邻居、互相避让、"
        "永不停下；鼠标是一只鹰",
        layers=[
            Layer("leader", 3, motion="path", path_size=[0.75, 0.6], path_freq=[2, 3], path_speed=0.012,
                  path_spread=0.12, look="none"),
            Layer("birds", 15000, [
                Pull(ABOVE, Field("classic", 5, power=0.5, min_dist=10, inner_radius=60, inner_gain=0.2)),
                Pull(MOUSE, push(320, 170)),
            ], align=0.1, pressure=0.06, cell=20, jitter=0.06, max_speed=4.5, min_speed=2.2,
                variety=0.5, velocity="random", start_speed=2, color_mode="fixed", color=[24, 20, 32]),
        ],
        friction=0.0002, background=[214, 178, 160], click_invert=False,
    )


def fabric():
    return Preset(
        "弹性布", "一张由网格点组成的布，每个点都被弹簧拉回原位；一个看不见的漩涡游魂把布拧出旋纹，"
        "你的鼠标在上面划出涟漪，松开后慢慢愈合",
        layers=[
            Layer("wisp", 1, motion="path", path_size=[0.8, 0.7], path_freq=[2, 3], path_speed=0.01,
                  look="none"),
            Layer("cloth", 16000, [
                Pull(ABOVE, Field("vortex", 40, min_dist=5, max_dist=230)),
                Pull(ABOVE, push(120, 70)),
                Pull(MOUSE, push(300, 130)),
                Pull(MOUSE, sweep(18, 200)),
            ], spawn="grid", velocity="zero", home=0.03, friction=0.02, size=2,
                color_mode="speed", color=[80, 95, 150], color2=[255, 215, 150], speed_ref=2.5),
        ],
        flow=Flow(True, 0.02, 420, 0.15),
    )


def mandala():
    return Preset(
        "曼陀罗", "三个种子沿利萨如曲线游走，星尘围着它们旋转（旋转力每 11 秒涨落一次）；"
        "画面被六重旋转加镜像复制成万花筒",
        layers=[
            Layer("seed", 3, motion="path", path_size=[0.42, 0.42], path_freq=[2, 3], path_speed=0.02,
                  path_spread=1.0, look="none"),
            Layer("dust", 9000, [
                Pull(ABOVE, Field("classic", 18, min_dist=8)),
                Pull(ABOVE, Field("vortex", 9, min_dist=8, pulse=0.8, period=11)),
            ], jitter=0.03, velocity="random", start_speed=2, color_mode="direction"),
        ],
        friction=0.001, trail=0.88, blend="add", glow=0.25, symmetry=6, mirror=True,
        palette=Palette(hue=280, hue_speed=4, saturation=0.6, value=0.9),
    )


def ink():
    return Preset(
        "墨流", "没有引力，只有一片缓慢变化的旋涡流场；四万个点顺着它流动，颜色随方向变化，"
        "长曝光的拖尾把流线画成大理石纹",
        layers=[Layer("ink", 25000, [Pull(MOUSE, push(220, 140)), Pull(MOUSE, sweep(14, 240))],
                      flow=1.0, velocity="zero", color_mode="direction")],
        friction=0.05, trail=0.94, blend="add", glow=0.28,
        flow=Flow(True, 0.12, 420, 0.06, mode="carry"),
        palette=Palette(hue=190, hue_speed=2, saturation=0.75, value=1.0),
    )


def snow_globe():
    return Preset(
        "雪景球", "重力向下，墙壁是实的，压力让雪真正堆起来；每片雪都有寿命，化掉后又从空中落下，"
        "所以雪一直在下；慢风把雪扬起，鼠标能扫开它",
        layers=[Layer("snow", 22000, [
            Pull(MOUSE, push(240, 150)),
            Pull(MOUSE, sweep(14, 220)),
        ], pressure=0.25, cell=10, jitter=0.02, velocity="zero", life=1500, life_jitter=0.6,
            color_mode="speed", color=[190, 205, 240], color2=[255, 255, 255], speed_ref=3, brightness=1.2)],
        friction=0.002, wind=[0.0, 0.05], edge="bounce", bounce=0.3,
        background=[8, 10, 22], flow=Flow(True, 0.1, 450, 0.12),
    )


def fireworks():
    return Preset(
        "烟花", "三个看不见的引信每隔一阵瞬移一次；火花寿命一致，所以同时死去、同时在新位置炸开",
        layers=[
            Layer("shell", 3, motion="teleport", teleport_every=110, look="none"),
            Layer("spark", 24000, [Pull(MOUSE, sweep(10, 200))], spawn="above", velocity="random",
                  start_speed=7, life=110, life_jitter=0.0, friction=0.002,
                  color_mode="age", color=[255, 245, 210], color2=[255, 60, 40]),
        ],
        wind=[0.0, 0.09], trail=0.8, blend="add", glow=0.55,
    )


BUILTIN = [
    ("galaxy", galaxy),
    ("attractor", strange_attractor),
    ("mandala", mandala),
    ("orrery", orrery),
    ("murmuration", murmuration),
    ("fabric", fabric),
    ("ink", ink),
    ("snow_globe", snow_globe),
    ("fireworks", fireworks),
]
BUILTIN_KEYS = [k for k, _ in BUILTIN]
DEFAULT = BUILTIN_KEYS[0]


def blank() -> Preset:
    """A starting point for a new preset: one layer of dust around the cursor."""
    return Preset("新预设", layers=[Layer("dust", 15000, [Pull(ABOVE, Field("classic", 20, min_dist=10))])])


# ------------------------------------------------------------------ library

def slug(name: str) -> str:
    return re.sub(r"[^\w\-]+", "_", name, flags=re.UNICODE).strip("_")[:60]


class Library:
    """Built-ins (read only) plus your presets in presets_user/ (create, read,
    update, rename, delete)."""

    def __init__(self, folder: Path = USER_DIR):
        self.folder = Path(folder)
        self.reload()

    def _path(self, key):
        return self.folder / f"{key}.json"

    def reload(self):
        self.builtin = {k: make() for k, make in BUILTIN}
        self.custom: dict[str, Preset] = {}
        self.autosaved = None
        if self.folder.is_dir():
            for path in sorted(self.folder.glob("*.json")):
                if path.stem == STATE:
                    continue
                try:
                    p = from_dict(json.loads(path.read_text(encoding="utf-8")))
                except Exception as e:                 # a broken file must not stop the show
                    print(f"skipping {path.name}: {e}")
                    continue
                if path.stem == AUTOSAVE:
                    self.autosaved = p
                elif path.stem not in self.builtin:
                    self.custom[path.stem] = p

    # -- read
    def __contains__(self, key):
        return key in self.builtin or key in self.custom or (key == AUTOSAVE and self.autosaved)

    def get(self, key) -> Preset:
        if key in self.builtin:
            return copy.deepcopy(self.builtin[key])
        if key in self.custom:
            return copy.deepcopy(self.custom[key])
        if key == AUTOSAVE and self.autosaved:
            return copy.deepcopy(self.autosaved)
        raise KeyError(key)

    def keys(self):
        return BUILTIN_KEYS + sorted(self.custom) + ([AUTOSAVE] if self.autosaved else [])

    def listing(self):
        """[key, title, group, slot (1-9 or None), editable] for the panel and menus."""
        out = [[k, self.builtin[k].title, "内置", i + 1, False] for i, k in enumerate(BUILTIN_KEYS)]
        out += [[k, self.custom[k].title, "我的", None, True] for k in sorted(self.custom)]
        if self.autosaved:
            out.append([AUTOSAVE, "上次的实验（自动保存）", "自动保存", None, False])
        return out

    def is_custom(self, key):
        return key in self.custom

    # -- write
    def _write(self, key, preset):
        self.folder.mkdir(exist_ok=True)
        self._path(key).write_text(json.dumps(to_dict(preset), ensure_ascii=False, indent=2),
                                   encoding="utf-8")

    def save(self, name: str, preset: Preset) -> str:
        """Create or update a custom preset; returns its key."""
        key = slug(name)
        if not key or key in self.builtin or key.startswith("_"):
            raise ValueError(f"'{name}' 不能用作名字（内置预设的名字是保留的）")
        preset = copy.deepcopy(preset)
        if key not in self.custom:
            preset.title = name.strip() or key
        self._write(key, preset)
        self.custom[key] = preset
        return key

    def rename(self, key: str, new_name: str) -> str:
        if key not in self.custom:
            raise KeyError(key)
        new_key = slug(new_name)
        if not new_key or new_key in self.builtin or new_key.startswith("_") or (
                new_key in self.custom and new_key != key):
            raise ValueError(f"'{new_name}' 不能用作名字")
        preset = self.custom.pop(key)
        preset.title = new_name.strip()
        if new_key != key:
            self._path(key).unlink(missing_ok=True)
        self._write(new_key, preset)
        self.custom[new_key] = preset
        return new_key

    def delete(self, key: str) -> bool:
        if key not in self.custom:
            return False
        self._path(key).unlink(missing_ok=True)
        del self.custom[key]
        return True

    def autosave(self, preset: Preset):
        self._write(AUTOSAVE, preset)
        self.autosaved = copy.deepcopy(preset)

    # -- remember what was showing
    def last(self):
        try:
            key = json.loads(self._path(STATE).read_text(encoding="utf-8")).get("last")
            return key if key in self else None
        except (OSError, ValueError):
            return None

    def remember(self, key):
        try:
            self.folder.mkdir(exist_ok=True)
            self._path(STATE).write_text(json.dumps({"last": key}), encoding="utf-8")
        except OSError:
            pass


def get(key: str) -> Preset:
    return Library().get(key)
