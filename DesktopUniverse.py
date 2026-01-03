import base64
import pygame
import pyautogui
import os
import sys
import time
import random
import math

# initialize key parameters

star_num = 3
sand_num = 5000
color_var_max = 1



class Sand:
    pos_x = 0
    pos_y = 0
    speed_x = 0
    speed_y = 0


class Star:
    pos_x = 0
    pos_y = 0
    speed_x = 0
    speed_y = 0


def speed_change(x, y, speed_x, speed_y, gravity_x, gravity_y):
    dist_x = gravity_x - x
    dist_y = gravity_y - y
    dist = (dist_x ** 2 + dist_y ** 2) ** 0.5

    if dist < stop_dist:
        return speed_x, speed_y

    speed_x = speed_x + gravity * dist_x / dist ** 2
    speed_y = speed_y + gravity * dist_y / dist ** 2

    return speed_x, speed_y


def move(x, y, speed_x, speed_y, img, width, height, paint):
    speed_x = speed_x * (1 - friction * speed_x ** 2)
    speed_y = speed_y * (1 - friction * speed_y ** 2)

    x = x + speed_x
    y = y + speed_y

    if x < 0 or x > window_size.width:
        x = abs(x - window_size.width)
    if y < 0 or y > window_size.height:
        y = abs(y - window_size.height)

    rect = pygame.Rect(round(x - width / 2), round(y - height / 2), 0, 0)
    if paint:
        screen.blit(img, rect)

    return x, y, speed_x, speed_y


def run_game():

    #initialize screen
    screen.fill((0, 0, 0))
    screen.blit(img_sand, pygame.Rect(round(window_size.width / 2), round(window_size.height / 2), 0, 0))
    pygame.display.update()
    time.sleep(1)

    reset_index = 0

    fps_time = 0

    color_list = [random.randint(50,200),random.randint(50,200),random.randint(50,200)]

    red_dir = 1
    green_dir = 1
    blue_dir = 1
    dir_list = [red_dir,green_dir,blue_dir]

    while True:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                sys.exit()

        mouse_pos = pyautogui.position()

        #screen.fill((0, 0, 0))

        if(print_fps):
            print("fps:", round(1 / (time.time() - fps_time)))
            fps_time = time.time()

        time_dist = abs(60 - time.time() % 120)/10
        dark_var = 1 - math.exp(-time_dist ** 2)
        global friction, gravity
        friction = friction_o * dark_var
        gravity = gravity_o * dark_var
        #print(time_dist)
        #print(dark_var)

        old_color = color_list
        color_var = random.randint(1,color_var_max)

        rand012 = random.randint(0,2)
        color_list[rand012] += dir_list[rand012] * color_var
        if (color_list[rand012] > 255-color_var_max-1):
            dir_list[rand012] = -1
        if (color_list[rand012] < 0+color_var_max+1):
            dir_list[rand012] = 1

        old_color = color_list


        img_sand.fill((old_color[0]*dark_var, old_color[1]*dark_var, old_color[2]*dark_var))
        #img_star.fill((color_list[0] * dark_var, color_list[1] * dark_var, color_list[2] * dark_var))

        #print(time.time())

        # print((color_list[0], color_list[1], color_list[2]))


        '''for i in range(50):
            sand[reset_index].pos_x = 0
            sand[reset_index].pos_y = 0
            sand[reset_index].speed_x = random.uniform(1,10)
            sand[reset_index].speed_y = random.uniform(1,10)
            reset_index = (reset_index + 1) % sand_num'''


        """font = pygame.font.Font(None, 36)
        # Get current time and format it as text
        current_time = (round(color_list[0]*dark_var), round(color_list[1]*dark_var), round(color_list[2]*dark_var))
        time_text = font.render(str(current_time), True, (255, 255, 255))  # White color

        # Position the text in the center of the screen
        text_rect = time_text.get_rect(center=(400, 150))
        pygame.draw.rect(screen, (30, 30, 30), text_rect)
        screen.blit(time_text, text_rect)"""





        for i in range(star_num):
            star[i].speed_x, star[i].speed_y = speed_change(star[i].pos_x, star[i].pos_y,
                                                            star[i].speed_x, star[i].speed_y,
                                                            mouse_pos.x, mouse_pos.y)

            star[i].pos_x, star[i].pos_y, star[i].speed_x, star[i].speed_y = move(star[i].pos_x, star[i].pos_y,
                                                                                  star[i].speed_x, star[i].speed_y,
                                                                                  img_star, star_width, star_height, True)

        for i in range(sand_num):
            sand[i].speed_x, sand[i].speed_y = speed_change(sand[i].pos_x, sand[i].pos_y,
                                                            sand[i].speed_x, sand[i].speed_y,
                                                            mouse_pos.x, mouse_pos.y)

            for j in range(star_num):
                sand[i].speed_x, sand[i].speed_y = speed_change(sand[i].pos_x, sand[i].pos_y,
                                                                sand[i].speed_x, sand[i].speed_y,
                                                                star[j].pos_x, star[j].pos_y)

            sand[i].pos_x, sand[i].pos_y, sand[i].speed_x, sand[i].speed_y = move(sand[i].pos_x, sand[i].pos_y,
                                                                                  sand[i].speed_x, sand[i].speed_y,
                                                                                  img_sand, sand_width, sand_height, True)

        pygame.display.update()



#generating the image of star and sand

img_sand = 'iVBORw0KGgoAAAANSUhEUgAAAAIAAAABCAIAAAB7QOjdAAAAAXNSR0IArs4c6QAAAARnQU1BAACxjwv8YQUAAAAJcEhZcwAADsMAAA7DAcdvqGQAAAAPSURBVBhXY/x/SoKBgQEACloB4/2+dYsAAAAASUVORK5CYII='
temp = open(r'img_sand.png', 'wb')
temp.write(base64.b64decode(img_sand))

img_star = 'iVBORw0KGgoAAAANSUhEUgAAAAoAAAAKCAYAAACNMs+9AAAAAXNSR0IArs4c6QAAAARnQU1BAACxjwv8YQUAAAAJcEhZcwAADsMAAA7DAcdvqGQAAAB/SURBVChTjZDBFYNACEQZtIPYTArRQ6wilaSKeMgWYjPagXHc2Udu2af/Agw84A0s2NZ3b8QzC/ci0BKdqb2NSWUZ/C4TFWs03QPQJhCf0P5CcHDs6KOuo5fOzv7wiKd4XjdHXic74Aa+oqwimy7bU35UIgt0onQyekmaemZmB+E3L+9HkKERAAAAAElFTkSuQmCC'
temp = open(r'img_star.png', 'wb')
temp.write(base64.b64decode(img_star))

temp.close()
img_sand = pygame.image.load(r'img_sand.png')
img_star = pygame.image.load(r'img_star.png')


#initialize basic parameters

window_size = pyautogui.size()
print_fps = False
gravity_o = 40
friction_o = 0.0001
stop_dist = 1
big_bang_speed_range = 10
star_width = 5
star_height = 5
sand_width = 1
sand_height = 1


#initialize the pygame window


pygame.init()
os.environ['SDL_VIDEO_CENTERED'] = '1'
screen = pygame.display.set_mode(window_size, pygame.NOFRAME)

#create and initialize sand and star objects

sand = []
for i in range(sand_num):
    sand.append(Sand())
    sand[i].pos_x = window_size.width / 2
    sand[i].pos_y = window_size.height / 2

    big_bang_speed = random.randint(0, big_bang_speed_range * 100)
    sand[i].speed_x = random.randint(-big_bang_speed, big_bang_speed)
    sand[i].speed_y = round((big_bang_speed ** 2 - sand[i].speed_x ** 2) ** 0.5)
    sand[i].speed_x = sand[i].speed_x / 100
    sand[i].speed_y = sand[i].speed_y / 100
    rand4 = random.randint(0, 1)
    if rand4 == 1:
        sand[i].speed_y = -1 * sand[i].speed_y

star = []
for i in range(star_num):
    star.append(Star())
    star[i].pos_x = random.randint(0, window_size.width)
    star[i].pos_y = random.randint(0, window_size.height)
    star[i].speed_x = random.randint(-2, 1) + 0.5
    star[i].speed_y = random.randint(-1, 2) - 0.5


# run the game

run_game()