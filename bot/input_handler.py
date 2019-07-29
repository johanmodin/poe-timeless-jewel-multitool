import win32api
import win32con
from random import randint, random
import sys

import pyautogui
import directkeys
import numpy as np

from utils import get_config

class InputHandler:
    def __init__(self, resolution):
        self.res_w = resolution[0]
        self.res_h = resolution[1]
        self.config = get_config('input_handler')

    def click(self, x_top,  y_top, x_bot, y_bot, button='left'):
        x_top *= self.res_w
        x_bot *= self.res_w
        y_top *= self.res_h
        y_bot *= self.res_h

        x = x_top + randint(0, x_bot - x_top)
        y = y_top + randint(0, y_bot - y_top)
        pyautogui.moveTo(x, y, 0.2 + self._rnd(), pyautogui.easeOutQuad)
        self._hw_move(x, y)
        self.rnd_sleep(mean=self.config['mouse_click_interval'])
        pyautogui.click(x=None, y=None, button=button)
        self.rnd_sleep(mean=self.config['mouse_click_interval'])

    def click_keys(self, keys):
        self._press_keys(keys)
        self._release_keys(keys)

    def _press_keys(self, keys):
        for key in keys:
            directkeys.PressKey(key)
            self.rnd_sleep(mean=self.config['key_press_interval'])

    def _release_keys(self, keys):
        for key in keys:
            directkeys.ReleaseKey(key)
            self.rnd_sleep(mean=self.config['key_press_interval'])

    def type(self, text):
        self.click_keys([0x0D])
        pyautogui.typewrite(text, interval=self.config['key_press_interval'])
        self.click_keys([0x0D])

    def _hw_move(self, x, y):
        nx = int(x*65535/win32api.GetSystemMetrics(0))
        ny = int(y*65535/win32api.GetSystemMetrics(1))
        win32api.mouse_event(win32con.MOUSEEVENTF_ABSOLUTE|win32con.MOUSEEVENTF_MOVE,nx,ny)

    def rnd_sleep(self, min=50, mean=300):
        time.sleep(self._rnd(min, mean) / 1000)

    def _rnd(self, min, mean, sigma=500):
        r = np.random.normal(mean, sigma)
        while r < min:
            r = np.random.normal(mean, sigma)
        return r

    def inventory_click(self, slot_x, slot_y, ctrl_click=False):
        if ctrl_click:
            self._press_keys([0xA2])
        inventory_base = (0.665625‬, 0.552083)
        self.click(inventory_base[0] + slot_x*0.02773,
                   inventory_base[1] + slot_y*0.49305,
                   inventory_base[0] + slot_x*0.02773 + 0.015625‬,
                   inventory_base[1] + slot_y*0.49305 + 0.027777)
        if ctrl_click:
            self._release_keys([0xA2])

    def _copy(self):
        self.click_keys([0xA2, 0x43])
