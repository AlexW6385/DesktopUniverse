"""
The built-in presets (grouped; the first nine have hotkeys 1-9) and the library of your own.

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



# ------------------------------------------------------------------ cosmos

def black_hole():
    return Preset(
        "黑洞", "星尘从屏幕边缘出生，绕着中心的黑洞螺旋坠落，越近越快越亮，越过视界就消失；"
        "然后在边缘重生，吸积盘永不枯竭",
        layers=[Layer("disk", 30000, [
            Pull(CENTER, Field("classic", 90, min_dist=18)),
            Pull(CENTER, Field("vortex", 30, min_dist=18)),
            Pull(MOUSE, push(180, 120)),
        ], spawn="edges", velocity="orbit", start_speed=3, variety=0.5, jitter=0.02,
            life=700, life_jitter=0.8, fade=False,
            color_mode="speed", color=[120, 50, 30], color2=[255, 250, 230], speed_ref=7, brightness=1.3)],
        friction=0.004, trail=0.7, blend="add", glow=0.45,
    )


def comets():
    return Preset(
        "彗星", "五颗彗星沿一条大曲线列队飞行，身后拖着被太阳风吹散、慢慢熄灭的尾巴；鼠标能吹散彗尾",
        layers=[
            Layer("comet", 5, motion="path", path_size=[0.85, 0.7], path_freq=[1, 2], path_speed=0.03,
                  path_spread=0.18, look="dot", dot=7, color_mode="fixed", color=[255, 255, 240]),
            Layer("tail", 26000, [Pull(MOUSE, sweep(14, 220))], spawn="above", velocity="inherit",
                  start_speed=0.8, life=140, life_jitter=0.4, friction=0.01, jitter=0.03, wind=1.0,
                  color_mode="age", color=[200, 235, 255], color2=[60, 60, 160], brightness=1.2),
        ],
        wind=[0.03, -0.015], trail=0.5, blend="add", glow=0.5,
    )


def supernova():
    return Preset(
        "超新星", "所有粒子寿命完全同步：一起从中心炸开，被一根看不见的弹簧拉慢、拉回，"
        "坠回中心的瞬间一起死去，再一起炸开",
        layers=[Layer("ejecta", 30000, [
            Pull(CENTER, Field("classic", 0.0004, power=-1, min_dist=2)),
            Pull(MOUSE, push(40, 110)),
        ], spawn="center", velocity="outward", start_speed=9, life=320, life_jitter=0.0, fade=True,
            variety=0.3, color_mode="age", color=[255, 250, 220], color2=[200, 40, 60], brightness=1.5)],
        friction=0.0001, trail=0.75, blend="add", glow=0.4,
    )


def saturn():
    return Preset(
        "土星环", "三道星环绕着屏幕中心以不同的速度旋转；一颗牧羊犬卫星在最内环里巡逻，"
        "把它经过的地方清出一道缝",
        layers=[
            Layer("shepherd", 1, motion="path", path_size=[0.236, 0.378], path_freq=[1, 1], path_speed=0.05,
                  look="dot", dot=6, color_mode="fixed", color=[255, 230, 200]),
            Layer("inner", 9000, [Pull(CENTER, Field("ring", 2.0, radius=170)), Pull(CENTER, Field("vortex", 9, min_dist=30)),
                                  Pull(ABOVE, push(90, 40)), Pull(MOUSE, push(200, 120))],
                  variety=0.5, jitter=0.04, velocity="orbit", start_speed=3.5, spawn="circle", spawn_radius=170,
                  color_mode="speed", color=[170, 140, 100], color2=[255, 240, 210], speed_ref=5, brightness=1.6),
            Layer("middle", 14000, [Pull(CENTER, Field("ring", 2.0, radius=235)), Pull(CENTER, Field("vortex", 7, min_dist=30)),
                                    Pull(MOUSE, push(200, 120))],
                  variety=0.5, jitter=0.04, velocity="orbit", start_speed=3, spawn="circle", spawn_radius=235,
                  color_mode="speed", color=[150, 130, 110], color2=[240, 230, 220], speed_ref=4.5, brightness=1.6),
            Layer("outer", 10000, [Pull(CENTER, Field("ring", 2.0, radius=310)), Pull(CENTER, Field("vortex", 5.5, min_dist=30)),
                                   Pull(MOUSE, push(200, 120))],
                  variety=0.5, jitter=0.04, velocity="orbit", start_speed=2.6, spawn="circle", spawn_radius=310,
                  color_mode="speed", color=[120, 110, 100], color2=[220, 215, 210], speed_ref=4, brightness=1.6),
        ],
        friction=0.004, trail=0.3, blend="add", glow=0.35,
    )


def pocket_universe():
    return Preset(
        "掌中宇宙", "一个 de Jong 奇异吸引子跟着你的鼠标走：分形随着光标在桌面上游荡，形状还在慢慢变化",
        layers=[Layer("dust", 40000, [], motion="attractor", color_mode="rainbow")],
        trail=0.8, blend="add", glow=0.25, click_invert=False,
        palette=Palette(hue=30, hue_speed=6, saturation=0.7, value=0.95, spread=90),
        attractor=Attractor("dejong", 1.4, -2.3, 2.4, -2.1, scale=0.62, morph=0.3, morph_speed=0.01,
                            around=MOUSE),
    )


# ------------------------------------------------------------------ nature

def fish():
    return Preset(
        "鱼群", "一万条鱼被关在水族箱里：跟随邻居、互相避让、撞到玻璃就转向，几条领头鱼带着全群打转；"
        "鼠标是伸进水里的手",
        layers=[
            Layer("leader", 4, motion="path", path_size=[0.7, 0.6], path_freq=[3, 2], path_speed=0.01,
                  path_spread=0.25, look="none"),
            Layer("fish", 10000, [
                Pull(ABOVE, Field("classic", 4, power=0.5, min_dist=10, inner_radius=50, inner_gain=0.1)),
                Pull(MOUSE, push(300, 150)),
            ], align=0.14, pressure=0.1, cell=18, jitter=0.04, max_speed=3.8, min_speed=1.6, variety=0.4,
                velocity="random", start_speed=2, size=2,
                color_mode="speed", color=[40, 110, 150], color2=[220, 240, 255], speed_ref=4),
        ],
        friction=0.0003, edge="bounce", bounce=0.6, background=[4, 18, 34], click_invert=False,
    )


def fireflies():
    return Preset(
        "萤火虫", "夏夜的草地：几千只萤火虫随意游荡，各自按自己的节奏亮起又熄灭；鼠标靠近它们会散开",
        layers=[Layer("fly", 1400, [Pull(MOUSE, push(120, 110))], motion="wander", life=150, life_jitter=0.6,
                      fade=True, max_speed=1.2, friction=0.05, look="dot", dot=4,
                      color_mode="fixed", color=[255, 230, 120], brightness=1.3)],
        trail=0.4, blend="add", glow=0.8, background=[6, 14, 8], click_invert=False,
    )


def dandelion():
    return Preset(
        "蒲公英", "一颗蒲公英站在屏幕中央，种子不断飘离，顺着微风慢慢飞远、淡去；对着它吹口气（划一下鼠标）",
        layers=[
            Layer("head", 1, motion="fixed", spawn="center", look="dot", dot=10, color_mode="fixed",
                  color=[240, 235, 210]),
            Layer("seed", 3000, [Pull(MOUSE, sweep(22, 260))], spawn="above", velocity="outward",
                  start_speed=0.6, life=700, life_jitter=0.6, friction=0.03, flow=1.0, wind=1.0,
                  look="dot", dot=3, color_mode="fixed", color=[250, 250, 240], brightness=0.9),
        ],
        wind=[0.004, -0.003], flow=Flow(True, 0.04, 380, 0.1, mode="carry"),
        background=[20, 28, 40], click_invert=False,
    )


def campfire():
    return Preset(
        "篝火", "一簇火焰从屏幕中央升起：火星向上飘，被湍流拧成舌状，从白到橙再暗成灰烬；鼠标能拨动火苗",
        layers=[
            Layer("ember", 1, motion="fixed", spawn="center", look="none"),
            Layer("flame", 16000, [Pull(MOUSE, push(200, 110)), Pull(MOUSE, sweep(14, 200))],
                  spawn="above", velocity="random", start_speed=1.8, life=170, life_jitter=0.5,
                  jitter=0.08, friction=0.004, wind=1.0, flow=1.0,
                  color_mode="age", color=[255, 240, 190], color2=[160, 30, 10], brightness=1.6),
        ],
        wind=[0.0, -0.08], flow=Flow(True, 0.08, 140, 0.6), trail=0.6, blend="add", glow=0.5,
    )


def hourglass():
    return Preset(
        "沙漏", "一股细沙从屏幕中央落下，在地面堆成小山，堆高了会向两边滑开；沙粒寿命一到就回到上方再落一次；"
        "鼠标可以把沙堆铲开",
        layers=[Layer("sand", 20000, [Pull(MOUSE, push(260, 120)), Pull(MOUSE, sweep(10, 200))],
                      spawn="center", velocity="random", start_speed=0.6, pressure=0.3, cell=8, jitter=0.03,
                      life=1400, life_jitter=0.9, fade=False, wind=1.0,
                      color_mode="speed", color=[190, 160, 110], color2=[255, 240, 210], speed_ref=4)],
        friction=0.003, wind=[0.0, 0.08], edge="bounce", bounce=0.2, background=[14, 12, 10],
    )


def will_o_wisp():
    return Preset(
        "鬼火", "几团幽绿的鬼火在黑暗里游荡，身后拖着一缕缕慢慢消散的烟；鼠标靠近，它们会躲开",
        layers=[
            Layer("wisp", 6, [Pull(MOUSE, push(260, 160))], motion="wander", max_speed=1.6, friction=0.03,
                  look="dot", dot=9, color_mode="fixed", color=[150, 255, 190]),
            Layer("smoke", 9000, [], spawn="above", velocity="random", start_speed=0.5, life=220,
                  life_jitter=0.4, friction=0.02, jitter=0.03, flow=1.0,
                  color_mode="age", color=[120, 230, 170], color2=[20, 50, 60], brightness=0.9),
        ],
        flow=Flow(True, 0.03, 300, 0.2), trail=0.5, blend="add", glow=0.5, background=[4, 6, 8],
        click_invert=False,
    )


def lissajous():
    return Preset(
        "利萨如", "三条利萨如曲线各由几千个点铺满，以不同的速度转动，颜色随运动方向变化，"
        "长拖尾让它们织成一张发光的网",
        layers=[
            Layer("a", 6000, motion="path", path_size=[0.8, 0.7], path_freq=[3, 2], path_speed=0.02,
                  path_spread=1.0, color_mode="direction", brightness=1.5),
            Layer("b", 6000, motion="path", path_size=[0.6, 0.75], path_freq=[5, 4], path_speed=-0.013,
                  path_spread=1.0, color_mode="direction", brightness=1.5),
            Layer("c", 6000, motion="path", path_size=[0.85, 0.5], path_freq=[2, 3], path_speed=0.009,
                  path_spread=1.0, color_mode="direction", brightness=1.5),
        ],
        trail=0.9, blend="add", glow=0.5,
        palette=Palette(hue=0, hue_speed=8, saturation=0.7, value=0.9),
    )


def harmonics():
    return Preset(
        "谐振子", "屏幕中心是一根线性弹簧，每个粒子的弹性都略有不同：它们画出各自的椭圆，"
        "合在一起就是不断变化的拍频花纹",
        layers=[Layer("dust", 24000, [
            Pull(CENTER, Field("classic", 0.0005, power=-1, min_dist=1)),
            Pull(MOUSE, push(120, 110)),
        ], variety=0.3, spawn="circle", spawn_radius=230, velocity="orbit", start_speed=2.5,
            color_mode="direction", brightness=1.4)],
        friction=0.0, trail=0.88, blend="add", glow=0.3,
        palette=Palette(hue=160, hue_speed=3, saturation=0.65, value=0.9),
    )


def kaleidoscope():
    return Preset(
        "万花筒", "星尘绕着你的鼠标旋转，画面被六重旋转加镜像复制：你移动光标，就是在转动万花筒",
        layers=[Layer("dust", 7000, [
            Pull(ABOVE, Field("classic", 24, min_dist=12)),
            Pull(ABOVE, Field("vortex", 10, min_dist=12)),
        ], variety=0.8, jitter=0.04, spawn="mouse", velocity="orbit", start_speed=4,
            color_mode="rainbow", brightness=1.3)],
        friction=0.0015, trail=0.85, blend="add", glow=0.3, symmetry=6, mirror=True, click_invert=True,
        palette=Palette(hue=320, hue_speed=4, saturation=0.75, value=1.0, spread=120),
    )


def whirlpool():
    return Preset(
        "漩涡", "屏幕中心的引力加漩涡把三万个点卷成一个旋转的碗；鼠标在水面上压出一个洞，洞会被旋涡慢慢填平",
        layers=[Layer("water", 30000, [
            Pull(CENTER, Field("classic", 25, min_dist=10)),
            Pull(CENTER, Field("vortex", 14, min_dist=10)),
            Pull(MOUSE, push(180, 140)),
        ], jitter=0.06, variety=0.5, velocity="orbit", start_speed=3,
            color_mode="speed", color=[50, 40, 140], color2=[120, 230, 255], speed_ref=6, brightness=1.5)],
        friction=0.0005, trail=0.5, blend="add", glow=0.35,
    )


def atom():
    return Preset(
        "原子", "三层电子壳各自绕着原子核旋转，速度不同、颜色不同；核是一团互相吸引的粒子，鼠标能把壳层推变形",
        layers=[
            Layer("nucleus", 400, [Pull(CENTER, Field("classic", 30, min_dist=4))], pressure=-0.6, cell=10,
                  jitter=0.15, friction=0.02, spawn="circle", spawn_radius=30, size=2,
                  color_mode="fixed", color=[255, 120, 90]),
            Layer("shell1", 3000, [Pull(CENTER, Field("ring", 2.5, radius=110)), Pull(CENTER, Field("vortex", 10, min_dist=20)),
                                   Pull(MOUSE, push(160, 100))],
                  spawn="circle", spawn_radius=110, velocity="orbit", start_speed=4, jitter=0.03,
                  color_mode="fixed", color=[120, 220, 255]),
            Layer("shell2", 5000, [Pull(CENTER, Field("ring", 2.5, radius=210)), Pull(CENTER, Field("vortex", -8, min_dist=20)),
                                   Pull(MOUSE, push(160, 100))],
                  spawn="circle", spawn_radius=210, velocity="orbit", start_speed=-3, jitter=0.03,
                  color_mode="fixed", color=[200, 160, 255]),
            Layer("shell3", 8000, [Pull(CENTER, Field("ring", 2.5, radius=320)), Pull(CENTER, Field("vortex", 6, min_dist=20)),
                                   Pull(MOUSE, push(160, 100))],
                  spawn="circle", spawn_radius=320, velocity="orbit", start_speed=2.5, jitter=0.03,
                  color_mode="fixed", color=[150, 255, 200]),
        ],
        friction=0.003, trail=0.6, blend="add", glow=0.45,
    )


def halo():
    return Preset(
        "光环", "一圈圈光环始终套在你的鼠标上，跟着它走、围着它转；鼠标停下，环就慢慢收拢成一个整齐的圆",
        layers=[Layer("ring", 16000, [
            Pull(ABOVE, Field("ring", 2.0, radius=140)),
            Pull(ABOVE, Field("vortex", 12, min_dist=20)),
            Pull(ABOVE, Field("drag", 3, max_dist=600)),
        ], variety=0.7, jitter=0.05, spawn="mouse", velocity="orbit", start_speed=4,
            color_mode="speed", color=[255, 150, 60], color2=[255, 250, 220], speed_ref=7)],
        friction=0.003, trail=0.6, blend="add", glow=0.4, click_invert=False,
    )


def heartbeat():
    return Preset(
        "心跳", "一圈红色的环按心跳的节奏一胀一缩，每次收缩都把一圈光波推向外面",
        layers=[Layer("pulse", 24000, [
            Pull(CENTER, Field("ring", 1.6, radius=180, pulse=0.35, period=1.6)),
            Pull(CENTER, Field("vortex", 5, min_dist=20)),
            Pull(MOUSE, push(200, 120)),
        ], variety=0.7, jitter=0.06, velocity="orbit", start_speed=3,
            color_mode="speed", color=[140, 20, 40], color2=[255, 120, 140], speed_ref=7, brightness=1.6)],
        friction=0.003, trail=0.55, blend="add", glow=0.4,
    )


# ------------------------------------------------------------------ fluid & interaction

def incense():
    return Preset(
        "香烟", "一缕烟从你的鼠标尖升起，被湍流拧成丝带，越高越淡；鼠标慢慢移动，烟会在空中留下一道墙",
        layers=[Layer("smoke", 14000, [], spawn="mouse", velocity="random", start_speed=0.5, life=260,
                      life_jitter=0.4, friction=0.01, jitter=0.02, wind=1.0, flow=1.0, size=1,
                      color_mode="age", color=[230, 230, 240], color2=[40, 40, 60], brightness=0.8)],
        wind=[0.0, -0.035], flow=Flow(True, 0.06, 200, 0.5), trail=0.6, blend="add", glow=0.35,
        click_invert=False,
    )


def ripples():
    return Preset(
        "涟漪", "一张平静的水面，雨滴随机落下，每一滴都荡开一圈涟漪，然后水面慢慢恢复平静；"
        "鼠标划过水面会拖出一道波浪",
        layers=[
            Layer("drop", 3, motion="teleport", teleport_every=45, look="none"),
            Layer("water", 18000, [
                Pull(ABOVE, Field("classic", 4000, min_dist=2, inner_radius=120, inner_gain=-1, outer_gain=0)),
                Pull(MOUSE, sweep(40, 160)),
            ], spawn="grid", velocity="zero", home=0.02, friction=0.03, size=2,
                color_mode="speed", color=[40, 80, 130], color2=[220, 245, 255], speed_ref=2.5, brightness=1.6),
        ],
        background=[3, 8, 18], click_invert=False,
    )


def stardust_pen():
    return Preset(
        "星尘笔", "鼠标是一支笔：你划过的地方留下一道发光的星尘，星尘带着笔的速度飞出去，"
        "被缓慢的旋涡慢慢卷散、淡去；停下不动，它只会在笔尖积成一小团",
        layers=[Layer("dust", 20000, [], spawn="mouse", velocity="inherit", start_speed=0.8, life=420,
                      life_jitter=0.5, friction=0.01, jitter=0.02, flow=1.0,
                      color_mode="rainbow", brightness=1.2)],
        trail=0.7, blend="add", glow=0.4, click_invert=False,
        flow=Flow(True, 0.05, 360, 0.1, mode="carry"),
        palette=Palette(hue=200, hue_speed=12, saturation=0.7, value=1.0, spread=60),
    )


def sprites():
    return Preset(
        "精灵", "三只小精灵追着你的鼠标跑，跑得快就甩在后面，追上了就围着光标打转；"
        "每只身后都拖着一条会褪色的光尾",
        layers=[
            Layer("sprite", 3, [
                Pull(ABOVE, Field("classic", 20, power=0.5, min_dist=30)),
                Pull(ABOVE, Field("vortex", 14, min_dist=30, max_dist=160)),
                Pull(ABOVE, Field("drag", 2, max_dist=400)),
            ], spawn="mouse", velocity="orbit", start_speed=3, friction=0.0015, variety=0.4,
                look="dot", dot=7, color_mode="fixed", color=[255, 250, 230]),
            Layer("trail", 9000, [], spawn="above", velocity="inherit", start_speed=0.3, life=150,
                  life_jitter=0.3, friction=0.03, color_mode="age", color=[255, 220, 150], color2=[120, 60, 200],
                  brightness=1.3),
        ],
        trail=0.4, blend="add", glow=0.6, click_invert=False,
    )


def marbles():
    return Preset(
        "弹珠", "三百颗弹珠在桌面上永不停歇地弹来弹去，撞到边缘就反弹；鼠标是一根球杆，划过去就把它们打飞；"
        "快的发白，慢的发暗",
        layers=[Layer("marble", 300, [Pull(MOUSE, push(400, 90)), Pull(MOUSE, sweep(60, 120))],
                      velocity="random", start_speed=3, min_speed=1.2, max_speed=14, look="dot", dot=9,
                      color_mode="speed", color=[70, 90, 140], color2=[255, 255, 255], speed_ref=9)],
        friction=0.0003, edge="bounce", bounce=1.0, trail=0.5, blend="add", glow=0.5,
        background=[8, 10, 16], click_invert=False,
    )


GROUPS = [
    ("宇宙", [
        ("galaxy", galaxy), ("attractor", strange_attractor), ("orrery", orrery),
        ("black_hole", black_hole), ("comets", comets), ("supernova", supernova),
        ("saturn", saturn), ("pocket_universe", pocket_universe),
    ]),
    ("自然", [
        ("murmuration", murmuration), ("snow_globe", snow_globe), ("fireworks", fireworks),
        ("fish", fish), ("fireflies", fireflies), ("dandelion", dandelion),
        ("campfire", campfire), ("hourglass", hourglass), ("will_o_wisp", will_o_wisp),
    ]),
    ("几何", [
        ("mandala", mandala), ("lissajous", lissajous), ("harmonics", harmonics),
        ("kaleidoscope", kaleidoscope), ("whirlpool", whirlpool), ("atom", atom),
        ("halo", halo), ("heartbeat", heartbeat),
    ]),
    ("互动", [
        ("fabric", fabric), ("ink", ink), ("incense", incense), ("ripples", ripples),
        ("stardust_pen", stardust_pen), ("sprites", sprites), ("marbles", marbles),
    ]),
]

# keys 1-9 (hotkeys and the first nine of the menu) stay where they were
SLOTS = ["galaxy", "attractor", "mandala", "orrery", "murmuration", "fabric", "ink", "snow_globe", "fireworks"]

BUILTIN = [(k, make) for _, members in GROUPS for k, make in members]
BUILTIN_KEYS = [k for k, _ in BUILTIN]
GROUP_OF = {k: g for g, members in GROUPS for k, _ in members}
DEFAULT = SLOTS[0]


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
        out = [[k, self.builtin[k].title, GROUP_OF[k], SLOTS.index(k) + 1 if k in SLOTS else None, False]
               for k in BUILTIN_KEYS]
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

    # -- remember what was showing (and other app settings)
    def state(self) -> dict:
        try:
            return json.loads(self._path(STATE).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}

    def set_state(self, **values):
        try:
            self.folder.mkdir(exist_ok=True)
            st = {**self.state(), **values}
            self._path(STATE).write_text(json.dumps(st), encoding="utf-8")
        except OSError:
            pass

    def last(self):
        key = self.state().get("last")
        return key if key in self else None

    def remember(self, key):
        self.set_state(last=key)


def get(key: str) -> Preset:
    return Library().get(key)
