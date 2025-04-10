import base64
import io
import math
import pygame
import pyautogui
import os
import sys
import time
import random

MODE = "随波逐流"

if MODE == "缘起性空":
    ABS_GRAVITY = 40
    STAR_GRAVITY = 50
    ABS_GRAVITY_RANGE = range(10, 9999)
    STAR_GRAVITY_RANGE = range(2, 9999)
    FRICTION = 0.0001
    DARK_VAR = 1
    COLOR_VAR = 3
    KARMA_ON = True
    COLOR_ON = True
    SAND_NUM = 5000
    STAR_NUM = 3
if MODE == "随波逐流":
    ABS_GRAVITY = -100
    STAR_GRAVITY = 0
    ABS_GRAVITY_RANGE = range(30, 200)
    STAR_GRAVITY_RANGE = 0
    FRICTION = 0.003
    DARK_VAR = 1
    COLOR_VAR = 3
    KARMA_ON = False
    COLOR_ON = True
    SAND_NUM = 15000
    STAR_NUM = 0
if MODE == "神女散花":
    ABS_GRAVITY = -100
    STAR_GRAVITY = 0
    ABS_GRAVITY_RANGE = range(30, 200)
    STAR_GRAVITY_RANGE = 0
    FRICTION = 0.003
    DARK_VAR = 1
    COLOR_VAR = 3
    KARMA_ON = True
    COLOR_ON = True
    SAND_NUM = 15000
    STAR_NUM = 0

img_sand_data = 'iVBORw0KGgoAAAANSUhEUgAAAAIAAAABCAIAAAB7QOjdAAAAAXNSR0IArs4c6QAAAARnQU1BAACxjwv8YQUAAAAJcEhZcwAADsMAAA7DAcdvqGQAAAAPSURBVBhXY/x/SoKBgQEACloB4/2+dYsAAAAASUVORK5CYII='
img_star_data = 'iVBORw0KGgoAAAANSUhEUgAAAAoAAAAKCAYAAACNMs+9AAAAAXNSR0IArs4c6QAAAARnQU1BAACxjwv8YQUAAAAJcEhZcwAADsMAAA7DAcdvqGQAAAB/SURBVChTjZDBFYNACEQZtIPYTArRQ6wilaSKeMgWYjPagXHc2Udu2af/Agw84A0s2NZ3b8QzC/ci0BKdqb2NSWUZ/C4TFWs03QPQJhCf0P5CcHDs6KOuo5fOzv7wiKd4XjdHXic74Aa+oqwimy7bU35UIgt0onQyekmaemZmB+E3L+9HkKERAAAAAElFTkSuQmCC'
img_sand = pygame.image.load(io.BytesIO(base64.b64decode(img_sand_data)))
img_star = pygame.image.load(io.BytesIO(base64.b64decode(img_star_data)))

pygame.init()
os.environ['SDL_VIDEO_CENTERED'] = '1'
screen = pygame.display.set_mode(pyautogui.size(), pygame.NOFRAME)


class CelestialBody:
    def __init__(self, image, x, y, vx, vy, gravity, gravity_range, attract_list, radius):
        self.image = image
        self.x = x
        self.y = y
        self.vx = vx
        self.vy = vy
        self.gravity = gravity
        self.gravity_range = gravity_range
        self.attract_list = attract_list
        self.radius = radius

    def you_must(self):
        for each in self.attract_list:
            dist_x = each.x - self.x
            dist_y = each.y - self.y
            dist = (dist_x ** 2 + dist_y ** 2) ** 0.5

            if round(dist) not in each.gravity_range:
                continue

            force = DARK_VAR * each.gravity / (dist ** 2)
            angle = math.atan2(dist_y, dist_x)
            fx = force * math.cos(angle)
            fy = force * math.sin(angle)

            fx *= abs(dist_x)
            fy *= abs(dist_y)
            self.vx += fx
            self.vy += fy

        self.vx *= max(0,(1 - FRICTION * (self.vx ** 2)))
        self.vy *= max(0,(1 - FRICTION * (self.vy ** 2)))

    def therefore_you_can(self):
        self.x += self.vx
        self.y += self.vy

        if self.x < 0:
            self.x = pyautogui.size().width
        elif self.x > pyautogui.size().width:
            self.x = 0

        if self.y < 0:
            self.y = pyautogui.size().height
        elif self.y > pyautogui.size().height:
            self.y = 0

        screen.blit(self.image, (self.x - self.radius, self.y - self.radius))


class Sand(CelestialBody):
    def __init__(self, x, y, vx, vy, attract_list):
        super().__init__(img_sand, x, y, vx, vy, 0, range(0, 0), attract_list, 1)


class Star(CelestialBody):
    def __init__(self, x, y, vx, vy, attract_list):
        super().__init__(img_star, x, y, vx, vy, STAR_GRAVITY, STAR_GRAVITY_RANGE, attract_list, 2.5)


class Absolute(CelestialBody):
    def __init__(self):
        super().__init__(None, None, None, None, None,
                         ABS_GRAVITY, ABS_GRAVITY_RANGE, None, None)

    def you_must(self):
        self.x = pyautogui.position().x

    def therefore_you_can(self):
        self.y = pyautogui.position().y


class Color:
    def __init__(self):
        # 0,1,2 = R,G,B
        self.color_list = [random.randint(150, 200), random.randint(150, 200), random.randint(150, 200)]
        self.dir_list = [random.choice([-1, 1]), random.choice([-1, 1]), random.choice([-1, 1])]

    def change(self):
        for i in range(3):
            if self.color_list[i] < 50:
                self.dir_list[i] = 1
            if self.color_list[i] > 200:
                self.dir_list[i] = -1

        temp = random.randint(0, 2)
        self.color_list[temp] += COLOR_VAR * self.dir_list[temp]

        time_dist = abs(60 - time.time() % 120) / 10
        global DARK_VAR
        DARK_VAR = 1 - math.exp(-time_dist ** 2)

        img_sand.fill((self.color_list[0] * DARK_VAR, self.color_list[1] * DARK_VAR, self.color_list[2] * DARK_VAR))


color = Color()

abs_list = [Absolute()]

star_list = [Star(random.randint(0, pyautogui.size().width),
                  random.randint(0, pyautogui.size().height),
                  random.randint(0, 0),
                  random.randint(0, 0),
                  abs_list)
             for _ in range(STAR_NUM)]

sand_list = [Sand(random.randint(0, pyautogui.size().width),
                  random.randint(0, pyautogui.size().height),
                  random.randint(-2, 2),
                  random.randint(-2, 2),
                  star_list + abs_list)
             for _ in range(SAND_NUM)]

everything = abs_list + star_list + sand_list


def event():
    screen.fill((0, 0, 0))
    pygame.display.update()
    time.sleep(1)

    while True:
        for events in pygame.event.get():
            if events.type == pygame.QUIT:
                sys.exit()

        if not KARMA_ON:
            screen.fill((0, 0, 0))

        if COLOR_ON:
            color.change()

        for each in everything:
            each.you_must()
            each.therefore_you_can()

        pygame.display.update()


event()
