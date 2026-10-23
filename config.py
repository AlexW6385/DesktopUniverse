"""
The data model. A universe is plain data, so it can be edited live from the
panel, saved as JSON and loaded back. SCHEMA at the bottom describes every
field (label, range, when it applies) and the panel builds itself from it.

A Preset is a stack of Layers, top to bottom. Each layer is a swarm of
identical bodies and can only be pulled by the layer directly above it:

    mouse            the very top
      sun            pulled by the mouse (or moving on its own path)
        planet       pulled by the sun
          dust       pulled by the planets

Pull sources: "above" (every body of the layer above; the mouse for the top
layer), plus two global ones that reach any level: "mouse" and "center".
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass, field, fields

ABOVE, MOUSE, CENTER = "above", "mouse", "center"
SOURCES = (ABOVE, MOUSE, CENTER)
MAX_PAIRS = 600_000     # a pull costing more body pairs per frame is skipped (~25 ms)


@dataclass
class Field:
    """One force. d = source - body, r = |d|.

    classic  strength / r^power toward the source (power 1: gentle and long
             range, 2: Newton, negative: a spring that grows with distance);
             inner_gain applies inside inner_radius (negative = push away)
    vortex   the same strength, but sideways: bodies swirl around the source
    ring     a spring toward a circle of `radius` around the source
             (for rings, pulse makes the radius breathe instead of the strength)
    drag     pulls the body's velocity toward the source's velocity
             (strength = % per frame): bodies get carried along with the source
    wake     pushes bodies the way the source is moving (strength = % of its
             velocity per frame); a still source does nothing, a moving cursor
             stirs everything it passes

    pulse > 0 makes the strength breathe: strength * (1 + pulse * sin(2 pi t / period + phase));
    with pulse > 1 it swings between pulling and pushing.
    """
    law: str = "classic"
    strength: float = 20.0
    power: float = 1.0
    min_dist: float = 0.0
    max_dist: float = math.inf
    inner_radius: float = 0.0
    inner_gain: float = 1.0
    outer_gain: float = 1.0
    radius: float = 150.0
    pulse: float = 0.0
    period: float = 8.0
    phase: float = 0.0


@dataclass
class Pull:
    source: str = ABOVE
    field: Field = field(default_factory=Field)
    enabled: bool = True


@dataclass
class Layer:
    name: str = "dust"
    count: int = 10000
    pulls: list[Pull] = field(default_factory=list)

    # how it moves
    motion: str = "physics"        # physics | wander | path | attractor | teleport | fixed
    friction: float | None = None  # None = the preset's friction
    jitter: float = 0.0            # random kick per frame (temperature)
    max_speed: float = 0.0         # 0 = unlimited
    min_speed: float = 0.0         # bodies never slow below this (birds keep flying)
    variety: float = 0.0           # each body feels the pulls 1 +- variety times as strongly,
                                   # so they settle at different places instead of one ring
    wind: float = 1.0              # share of the preset's wind / gravity
    flow: float = 1.0              # share of the preset's flow field
    home: float = 0.0              # spring back to the birth position
    pressure: float = 0.0          # push from crowded to empty (negative: clump together)
    align: float = 0.0             # match the average velocity of neighbours (flocking)
    cell: int = 16                 # neighbourhood size for pressure / align, px

    # path: bodies trace a Lissajous curve on their own
    path_around: str = CENTER      # center | mouse
    path_size: list[float] = field(default_factory=lambda: [0.5, 0.4])  # of half the screen
    path_freq: list[float] = field(default_factory=lambda: [1.0, 2.0])
    path_speed: float = 0.1        # cycles per second
    path_spread: float = 1.0       # how far apart the bodies sit along the curve (1 = evenly)

    # attractor: bodies hop along the preset's strange attractor
    map_blend: float = 1.0         # 1 = jump onto the map each frame, smaller = drift toward it

    teleport_every: int = 60       # teleport: every N frames all bodies jump somewhere new

    # life
    life: int = 0                  # frames; 0 = forever
    life_jitter: float = 0.3       # +- share of life, so deaths don't all line up
    fade: bool = True              # fade in after birth and out before death

    # birth
    spawn: str = "random"          # random | center | mouse | edges | grid | circle | above | above_ring
    spawn_radius: float = 200.0    # circle / above_ring
    velocity: str = "random"       # zero | random | orbit | outward | inherit
    start_speed: float = 2.0

    # looks
    look: str = "pixel"            # pixel | dot | none
    size: int = 1                  # pixel square size
    dot: int = 8                   # dot diameter
    color_mode: str = "palette"    # palette | fixed | speed | direction | age | rainbow
    color: list[int] = field(default_factory=lambda: [120, 160, 255])
    color2: list[int] = field(default_factory=lambda: [255, 230, 190])
    speed_ref: float = 6.0         # speed that gets the full second colour
    brightness: float = 1.0


@dataclass
class Palette:
    """The shared drifting colour: a hue that slowly turns."""
    hue: float = 210.0             # degrees
    hue_speed: float = 3.0         # degrees per second
    saturation: float = 0.55
    value: float = 0.95
    spread: float = 90.0           # rainbow mode: hue range across a layer


@dataclass
class Flow:
    """A slowly changing, swirling wind over the whole screen."""
    enabled: bool = False
    strength: float = 0.05
    scale: float = 300.0           # swirl size, px
    speed: float = 0.2             # how fast the pattern changes
    mode: str = "force"            # force: a wind that accelerates | carry: moves bodies directly
                                   # along the streamlines (no clumping, like ink in water)


@dataclass
class Attractor:
    """A strange attractor for layers whose motion is 'attractor'."""
    kind: str = "clifford"         # clifford | dejong
    a: float = -1.7
    b: float = 1.8
    c: float = -1.9
    d: float = -0.4
    scale: float = 0.9             # of the screen's shorter side
    morph: float = 0.15            # how far a..d wander over time
    morph_speed: float = 0.02      # cycles per second
    around: str = CENTER           # center | mouse


@dataclass
class Preset:
    title: str = "Untitled"
    description: str = ""
    layers: list[Layer] = field(default_factory=list)

    friction: float = 0.0005
    friction_shape: str = "round"  # round: by total speed | axis: x and y separately
    wind: list[float] = field(default_factory=lambda: [0.0, 0.0])
    edge: str = "wrap"             # wrap | bounce | respawn
    bounce: float = 0.8
    click_invert: bool = True      # hold the left mouse button to flip the mouse's forces

    brightness: float = 1.0
    breathe_period: float = 0.0    # seconds; 0 = off. Fades to dark and back once a period
    breathe_depth: float = 0.9
    breathe_forces: bool = True    # forces fade with the light (everything drifts in the dark)

    background: list[int] = field(default_factory=lambda: [0, 0, 0])
    trail: float = 0.0             # 0 = clear each frame, 1 = keep forever, between = fade
    blend: str = "replace"         # replace | add (overlaps glow)
    glow: float = 0.5              # add: brightness of each hit
    symmetry: int = 1              # kaleidoscope: copies around the centre
    mirror: bool = False

    palette: Palette = field(default_factory=Palette)
    flow: Flow = field(default_factory=Flow)
    attractor: Attractor = field(default_factory=Attractor)


# ---------------------------------------------------------------- JSON

def _clean(v):
    if isinstance(v, float) and math.isinf(v):
        return None
    if isinstance(v, dict):
        return {k: _clean(x) for k, x in v.items()}
    if isinstance(v, list):
        return [_clean(x) for x in v]
    return v


def to_dict(p: Preset) -> dict:
    return _clean(asdict(p))


def layer_template() -> dict:
    """Every layer field with its default, for the panel's "add layer" buttons."""
    return _clean(asdict(Layer()))


def _build(cls, d):
    d = d if isinstance(d, dict) else {}
    names = {f.name for f in fields(cls)}
    return cls(**{k: v for k, v in d.items() if k in names})


def from_dict(d: dict) -> Preset:
    layers = []
    for ld in d.get("layers", []):
        pulls = []
        for pd in ld.get("pulls", []):
            fd = dict(pd.get("field", {}))
            if fd.get("max_dist") is None:
                fd["max_dist"] = math.inf
            src = pd.get("source", ABOVE)
            pulls.append(Pull(src if src in SOURCES else ABOVE, _build(Field, fd),
                              bool(pd.get("enabled", True))))
        layer = _build(Layer, {**ld, "pulls": pulls})
        layer.count = max(0, int(layer.count))
        layers.append(layer)
    return _build(Preset, {**d, "layers": layers,
                           "palette": _build(Palette, d.get("palette")),
                           "flow": _build(Flow, d.get("flow")),
                           "attractor": _build(Attractor, d.get("attractor"))})


def problems(p: Preset) -> list[str]:
    out = []
    for i, layer in enumerate(p.layers):
        if i and any(pl.enabled and pl.source == ABOVE for pl in layer.pulls):
            above = p.layers[i - 1]
            if above.count * layer.count > MAX_PAIRS:
                out.append(f"{layer.name} ← {above.name}: {above.count} × {layer.count} 对太多，"
                           f"这个力被跳过了（上层要少）")
    names = [l.name for l in p.layers]
    for n in set(names):
        if names.count(n) > 1:
            out.append(f"层名 {n} 重复了")
    return out


# ---------------------------------------------------------------- schema
# kind: num | int | log | sel | bool | color | vec2 | text
# when: {"field": [values]} shows the control only when another field of the
#       same object has one of those values; "preset.x" looks at the preset.

def F(key, label, kind, **kw):
    return {"key": key, "label": label, "kind": kind, **kw}


SCHEMA = {
    "preset": [
        ("说明", [
            F("title", "名字", "text"),
            F("description", "描述", "text"),
        ]),
        ("运动", [
            F("friction", "摩擦", "log", min=1e-6, max=0.05),
            F("friction_shape", "摩擦形状", "sel", options=[["round", "按总速度（圆）"], ["axis", "按轴（略方）"]]),
            F("wind", "重力 / 风", "vec2", min=-0.3, max=0.3, step=0.005, labels=["→", "↓"]),
            F("edge", "墙壁", "sel", options=[["wrap", "环绕"], ["bounce", "反弹"], ["respawn", "出界重生"]]),
            F("bounce", "弹性", "num", min=0, max=1, step=0.01, when={"edge": ["bounce"]}),
            F("click_invert", "按住鼠标反转", "bool", hint="按住左键时，鼠标的所有力反向"),
        ]),
        ("光", [
            F("brightness", "亮度", "num", min=0, max=1.5, step=0.01),
            F("breathe_period", "呼吸周期 秒", "num", min=0, max=600, step=1, hint="0 = 关闭；每个周期暗下去一次再亮回来"),
            F("breathe_depth", "呼吸深度", "num", min=0, max=1, step=0.01, when={"breathe_period": "nonzero"}),
            F("breathe_forces", "力随光变弱", "bool", when={"breathe_period": "nonzero"},
              hint="暗的时候力也消失，粒子散开，亮起来再重新聚合"),
        ]),
        ("画面", [
            F("background", "背景色", "color"),
            F("trail", "拖尾", "num", min=0, max=1, step=0.01, hint="0 = 每帧清屏，1 = 永久保留，中间 = 渐隐"),
            F("blend", "混合", "sel", options=[["replace", "覆盖"], ["add", "叠加发光"]]),
            F("glow", "发光强度", "num", min=0.02, max=1, step=0.01, when={"blend": ["add"]}),
            F("symmetry", "万花筒对称", "int", min=1, max=12, step=1, hint="1 = 关闭"),
            F("mirror", "镜像", "bool"),
        ]),
        ("调色（颜色模式为 调色 / 方向 / 彩虹 的层用它）", [
            F("palette.hue", "色相", "num", min=0, max=360, step=1),
            F("palette.hue_speed", "色相漂移 度/秒", "num", min=-60, max=60, step=0.5, symmetric=True),
            F("palette.saturation", "饱和度", "num", min=0, max=1, step=0.01),
            F("palette.value", "明度", "num", min=0, max=1, step=0.01),
            F("palette.spread", "彩虹跨度 度", "num", min=0, max=360, step=1),
        ]),
        ("流场（全屏缓慢流动的风）", [
            F("flow.enabled", "开启", "bool"),
            F("flow.strength", "强度", "num", min=0, max=0.5, step=0.005, when={"flow.enabled": [True]}),
            F("flow.scale", "漩涡大小 px", "num", min=40, max=1500, step=10, when={"flow.enabled": [True]}),
            F("flow.speed", "变化速度", "num", min=0, max=2, step=0.01, when={"flow.enabled": [True]}),
            F("flow.mode", "方式", "sel", options=[["force", "风（加速）"], ["carry", "水流（直接带着走）"]],
              when={"flow.enabled": [True]}),
        ]),
        ("奇异吸引子（运动方式为 吸引子 的层用它）", [
            F("attractor.kind", "类型", "sel", options=[["clifford", "Clifford"], ["dejong", "de Jong"]]),
            F("attractor.a", "a", "num", min=-3, max=3, step=0.01, symmetric=True),
            F("attractor.b", "b", "num", min=-3, max=3, step=0.01, symmetric=True),
            F("attractor.c", "c", "num", min=-3, max=3, step=0.01, symmetric=True),
            F("attractor.d", "d", "num", min=-3, max=3, step=0.01, symmetric=True),
            F("attractor.scale", "大小", "num", min=0.1, max=2, step=0.01),
            F("attractor.morph", "变形幅度", "num", min=0, max=1, step=0.01),
            F("attractor.morph_speed", "变形速度", "num", min=0, max=0.3, step=0.001),
            F("attractor.around", "中心", "sel", options=[["center", "屏幕中心"], ["mouse", "鼠标"]]),
        ]),
    ],
    "layer": [
        ("", [
            F("name", "名字", "text"),
            F("count", "数量", "log", min=1, max=200000, int=True),
        ]),
        ("运动", [
            F("motion", "方式", "sel", options=[
                ["physics", "受力运动"], ["wander", "随机游走 + 受力"], ["path", "沿轨迹（利萨如曲线）"],
                ["attractor", "奇异吸引子"], ["teleport", "瞬移"], ["fixed", "固定"]]),
            F("path_around", "轨迹中心", "sel", options=[["center", "屏幕中心"], ["mouse", "鼠标"]], when={"motion": ["path"]}),
            F("path_size", "轨迹大小", "vec2", min=0, max=1.2, step=0.01, labels=["宽", "高"], when={"motion": ["path"]}),
            F("path_freq", "轨迹频率", "vec2", min=0, max=7, step=0.25, labels=["x", "y"], when={"motion": ["path"]}),
            F("path_speed", "轨迹速度 圈/秒", "num", min=-0.5, max=0.5, step=0.005, symmetric=True, when={"motion": ["path"]}),
            F("path_spread", "间隔", "num", min=0, max=1, step=0.01, when={"motion": ["path"]}, hint="1 = 均匀铺满整条曲线"),
            F("map_blend", "贴合吸引子", "num", min=0, max=1, step=0.01, when={"motion": ["attractor"]}),
            F("teleport_every", "每 N 帧瞬移", "int", min=1, max=600, step=1, when={"motion": ["teleport"]}),
        ]),
        ("阻力与扰动", [
            F("friction", "摩擦", "log", min=1e-6, max=0.05, nullable_label="用全局"),
            F("jitter", "抖动（温度）", "num", min=0, max=1, step=0.005),
            F("max_speed", "速度上限", "num", min=0, max=30, step=0.1, hint="0 = 不限"),
            F("min_speed", "最低速度", "num", min=0, max=10, step=0.05, hint="永远不会慢于它（鸟一直在飞）"),
            F("variety", "个体差异", "num", min=0, max=1, step=0.01,
              hint="每个粒子受力的倍数在 1±差异 之间随机，避免全都挤到同一个圈上"),
            F("wind", "受重力/风", "num", min=0, max=3, step=0.05),
            F("flow", "受流场", "num", min=0, max=3, step=0.05),
        ]),
        ("相互作用", [
            F("home", "回家弹簧", "num", min=0, max=0.1, step=0.001, hint="拉回出生的位置：网格出生 + 回家 = 弹性布"),
            F("pressure", "压力", "num", min=-3, max=3, step=0.05, symmetric=True, hint="正 = 从密处挤向稀处（流体、堆积），负 = 抱团"),
            F("align", "对齐", "num", min=0, max=0.3, step=0.005, hint="跟随邻居的平均速度（鸟群）"),
            F("cell", "邻域大小 px", "int", min=4, max=120, step=1),
        ]),
        ("寿命", [
            F("life", "寿命 帧", "int", min=0, max=1200, step=1, hint="0 = 永生；死后按出生规则重生"),
            F("life_jitter", "寿命随机", "num", min=0, max=1, step=0.01, when={"life": "nonzero"}),
            F("fade", "淡入淡出", "bool", when={"life": "nonzero"}),
        ]),
        ("出生", [
            F("spawn", "位置", "sel", options=[
                ["random", "随机"], ["center", "屏幕中心"], ["mouse", "鼠标处"], ["edges", "四周边缘"],
                ["grid", "网格"], ["circle", "屏幕中心圆环"], ["above", "上一层的天体上（发射器）"],
                ["above_ring", "上一层天体周围的圆环（卫星）"]]),
            F("spawn_radius", "圆环半径", "num", min=0, max=1000, step=1, when={"spawn": ["circle", "above_ring"]}),
            F("velocity", "初速度", "sel", options=[
                ["zero", "静止"], ["random", "随机方向"], ["orbit", "绕行（切向）"], ["outward", "向外炸开"],
                ["inherit", "继承上一层速度"]]),
            F("start_speed", "初速度大小", "num", min=0, max=20, step=0.1),
        ]),
        ("外观", [
            F("look", "画法", "sel", options=[["pixel", "像素点"], ["dot", "圆点"], ["none", "不画"]]),
            F("size", "像素大小", "int", min=1, max=4, step=1, when={"look": ["pixel"]}),
            F("dot", "圆点直径", "int", min=2, max=40, step=1, when={"look": ["dot"]}),
            F("color_mode", "颜色", "sel", options=[
                ["palette", "调色（漂移）"], ["fixed", "固定"], ["speed", "按速度"], ["direction", "按方向（色相环）"],
                ["age", "按年龄"], ["rainbow", "彩虹散布"]]),
            F("color", "颜色 1", "color", when={"color_mode": ["fixed", "speed", "age"]}),
            F("color2", "颜色 2", "color", when={"color_mode": ["speed", "age"]}),
            F("speed_ref", "满色速度", "num", min=0.2, max=20, step=0.1, when={"color_mode": ["speed"]}),
            F("brightness", "亮度", "num", min=0, max=2, step=0.01),
        ]),
    ],
    "field": [
        F("law", "公式", "sel", options=[["classic", "引力"], ["vortex", "漩涡"], ["ring", "轨道环"],
                                         ["drag", "拖拽（同速）"], ["wake", "尾流（顺着推）"]]),
        F("strength", "强度", "num", min=-200, max=200, symmetric=True),
        F("power", "衰减指数", "num", min=-1, max=3, step=0.05, when={"law": ["classic", "vortex"]},
          hint="1 = 柔和远程，2 = 牛顿，负数 = 弹簧"),
        F("radius", "环半径 px", "num", min=0, max=900, step=1, when={"law": ["ring"]}),
        F("min_dist", "最小距离", "num", min=0, max=500, step=1),
        F("max_dist", "最大距离", "num", min=0, max=3000, step=1, nullable=True),
        F("inner_radius", "内圈半径", "num", min=0, max=1000, step=1, when={"law": ["classic", "vortex"]}),
        F("inner_gain", "内圈增益", "num", min=-3, max=3, step=0.05, symmetric=True, when={"law": ["classic", "vortex"]},
          hint="负数 = 内圈变成排斥"),
        F("outer_gain", "外圈增益", "num", min=-3, max=3, step=0.05, symmetric=True, when={"law": ["classic", "vortex"]}),
        F("pulse", "脉动幅度", "num", min=0, max=3, step=0.01, hint=">1 时吸引和排斥交替；轨道环则是半径在呼吸"),
        F("period", "脉动周期 秒", "num", min=0.2, max=60, step=0.1, when={"pulse": "nonzero"}),
        F("phase", "脉动相位", "num", min=0, max=1, step=0.01, when={"pulse": "nonzero"}),
    ],
}

LAW_HINTS = {
    "classic": "强度 / r^指数，指向源。内圈增益为负时，靠近会被推开",
    "vortex": "侧向力：让粒子绕着源转。和引力叠加就是星系",
    "ring": "弹簧：把粒子拉向半径固定的圆。配合漩涡就是土星环",
    "drag": "把粒子的速度拉向源的速度：粒子被源带着一起走；源静止时就像刹车（强度 = 每帧 %）",
    "wake": "顺着源的运动方向推粒子：鼠标划过时搅动经过的地方，鼠标不动就没有作用（强度 = 每帧 %）",
}
