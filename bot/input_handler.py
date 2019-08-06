import win32api
import win32con
import win32clipboard
from random import randint, random
import sys

import pyautogui
from .directkeys import *
import numpy as np

from .utils import get_config

class InputHandler:
    def __init__(self, resolution):
        self.res_w = resolution[0]
        self.res_h = resolution[1]
        self.config = get_config('input_handler')

    def click(self, x_top,  y_top, x_bot, y_bot, button='left', speed_factor=3, raw=False):
        if not raw:
            x_top *= self.res_w
            x_bot *= self.res_w
            y_top *= self.res_h
            y_bot *= self.res_h

        x = x_top + random() * (x_bot - x_top)
        y = y_top + random() * (x_bot - x_top)
        pyautogui.moveTo(x, y, self._rnd(min=100 / speed_factor,
                                         mean=150 / speed_factor,
                                         sigma=100 / speed_factor) / 1000,
                         pyautogui.easeOutQuad)
        self._hw_move(x, y)
        if button is not None:
            self.rnd_sleep(mean=self.config['mouse_click_interval'] / speed_factor)
            pyautogui.click(x=None, y=None, button=button)

    def click_keys(self, keys):
        self._press_keys(keys)
        self._release_keys(keys)

    def click_hotkey(self, hotkey):
        pyautogui.press(hotkey)
        self.rnd_sleep(mean=self.config['key_press_interval'])

    def _press_keys(self, keys):
        for key in keys:
            PressKey(key)
            self.rnd_sleep(mean=self.config['key_press_interval'])

    def _release_keys(self, keys):
        for key in keys:
            ReleaseKey(key)
            self.rnd_sleep(mean=self.config['key_press_interval'])

    def type(self, text):
        self.click_keys([0x1c])
        pyautogui.typewrite(text, interval=self.config['key_press_interval']/1000)
        self.click_keys([0x1c])

    def _hw_move(self, x, y):
        nx = int(x*65535/win32api.GetSystemMetrics(0))
        ny = int(y*65535/win32api.GetSystemMetrics(1))
        win32api.mouse_event(win32con.MOUSEEVENTF_ABSOLUTE|win32con.MOUSEEVENTF_MOVE,nx,ny)

    def rnd_sleep(self, min=50, mean=300, sigma=300):
        time.sleep(self._rnd(min, mean, sigma=sigma) / 1000)

    def _rnd(self, min, mean, sigma=500):
        r = np.random.normal(mean, sigma)
        while r < min:
            r = np.random.normal(mean, sigma)
        return r

    def inventory_click(self, slot_x, slot_y, inventory_base, ctrl_click=False, button='left', speed_factor=2):
        if ctrl_click:
            self._press_keys([0x1d])
        self.click(inventory_base[0] + slot_x * 0.02735 - 0.006625,
                   inventory_base[1] + slot_y * 0.04930555 - 0.009777,
                   inventory_base[0] + slot_x * 0.02735 + 0.006625,
                   inventory_base[1] + slot_y * 0.04930555 + 0.009777,
                   speed_factor=speed_factor, button=button)
        if ctrl_click:
            self._release_keys([0x1d])

    def inventory_copy(self, slot_x, slot_y, inventory_base, speed_factor=1):
        self.click(inventory_base[0] + slot_x * 0.02735 - 0.006625,
                   inventory_base[1] + slot_y * 0.04930555 - 0.009777,
                   inventory_base[0] + slot_x * 0.02735 + 0.005625,
                   inventory_base[1] + slot_y * 0.04930555 + 0.007777,
                   speed_factor=speed_factor, button=None)
        self._copy()
        win32clipboard.OpenClipboard()
        data = win32clipboard.GetClipboardData()
        win32clipboard.CloseClipboard()
        return data

    def _copy(self):
        self.click_keys([0x1d, 0x2e])

    def zoom(self, clicks):
        # Did not work in testing
        dx = int(self.res_w / 2 * 65535 / win32api.GetSystemMetrics(0))
        dy = int(self.res_h / 2 * 65535 / win32api.GetSystemMetrics(1))
        self.click(0.499, 0.499, 0.501, 0.501, button=None)
        win32api.mouse_event(win32con.MOUSEEVENTF_WHEEL, dx, dy, clicks, 0)

    def drag(self, x, y, delta=False, speed_factor=1):
        if delta:
            pyautogui.drag(x, y, self._rnd(min=500 / speed_factor,
                                           mean=800 / speed_factor,
                                           sigma=400 / speed_factor) / 1000,
                           pyautogui.easeOutQuad, button='left')
        else:
            pyautogui.dragTo(x, y, self._rnd(min=500 / speed_factor,
                                             mean=800 / speed_factor,
                                             sigma=400 / speed_factor) / 1000,
                             pyautogui.easeOutQuad, button='left')
