import pygame
import win32api
import win32con
import win32gui
import time
from multiprocessing import Process, Manager

class RectManager:
    def __init__(self, managed_dict):
        self.managed_dict = managed_dict
        self.object_counter = 0

    def add_rect(self, x, y, side, thickness, color):
        r = Rectangle(x, y, side, thickness, color)
        rect_id = self.object_counter
        self.managed_dict[rect_id] = r
        self.object_counter += 1
        return rect_id

    def remove_rect(self, rect_id):
        result = self.managed_dict.pop(rect_id, None)
        return result is not None

    def move_rect(self, rect_id, x, y):
        if rect_id in self.managed_dict[rect_id]:
            self.managed_dict[rect_id].x = x
            self.managed_dict[rect_id].y = y
            return True
        return False

class Rectangle:
    def __init__(self, x, y, side_length, thickness, color):
        self.x = x
        self.y = y
        self.side_length = side_length
        self.thickness = thickness
        self.color = color

def _draw_worker(draw_list):
    print('nd')
    pygame.init()
    screen = pygame.display.set_mode((2560, 1440), pygame.NOFRAME)
    fuchsia = (255, 0, 128)  # Transparency color
    # Set window transparency color
    hwnd = pygame.display.get_wm_info()["window"]
    win32gui.SetWindowLong(hwnd, win32con.GWL_EXSTYLE,
                           win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE) | win32con.WS_EX_LAYERED)
    win32gui.SetLayeredWindowAttributes(hwnd, win32api.RGB(*fuchsia), 0, win32con.LWA_COLORKEY)
    done = False
    while not done:
        print('nd')
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                done = True
        for rect_key in draw_list.keys():
            rect = draw_list[rect_key]
            screen.fill(fuchsia)  # Transparent background
            pygame.draw.rect(screen, rect.color, pygame.Rect(rect.x, rect.y, rect.side_length, rect.thickness))
            pygame.draw.rect(screen, rect.color, pygame.Rect(rect.x, rect.y, rect.thickness, rect.side_length))
            pygame.draw.rect(screen, rect.color, pygame.Rect(rect.x + rect.side_length, rect.y, rect.thickness, rect.side_length))
            pygame.draw.rect(screen, rect.color, pygame.Rect(rect.x, rect.y + rect.side_length, rect.side_length + rect.thickness, rect.thickness))
        pygame.display.update()
#
