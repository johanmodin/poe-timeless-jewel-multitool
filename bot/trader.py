import logging
import numpy as np
import math
from matplotlib import pyplot
import time


from .input_handler import InputHandler
from .utils import get_config
from .grabscreen import grab_screen
import cv2

OWN_INVENTORY_ORIGIN = (0.6769531, 0.567361)
TRADE_PARTNER_ORIGIN = ()

class Trader:
    def __init__(self, resolution):
        self.resolution = resolution
        self.config = get_config('trader')
        self.input_handler = InputHandler(self.resolution)
        logging.basicConfig(level=logging.INFO)
        self.log = logging.getLogger('trader')

    def stash_items(self):
        slots = self.find_nonempty_inventory_slots(origin=OWN_INVENTORY_ORIGIN)
        if int(np.sum(slots)) > 0:
            stash_loc = self._find_stash()
            self.log.info('Found stash at %s' % stash_loc)
            stash_loc_br = [stash_loc[0] + 0.005, stash_loc[1] + 0.005]
            self.input_handler.click(*stash_loc, *stash_loc_br)
            item_locations = np.argwhere(slots == 1)
            for loc in item_locations:
                self.input_handler.inventory_click(loc[0], loc[1], ctrl_click=True)
            self.input_handler.click_keys([0x81])
            self.log.info('Stashed %s items' % int(np.sum(slots)))
        else:
            self.log.info('No stashing needed, inventory empty')

    def verify_empty_inventory(self):
        slots = self.find_nonempty_inventory_slots(origin=OWN_INVENTORY_ORIGIN)
        non_empty = int(np.sum(slots))
        self.log.info('Non-empty slots found: %d' % non_empty)
        return non_empty > 0

    def wait_for_trade(self):
        return NotImplemented('This needs to be done first')

    def get_items(self):
        return NotImplemented('This needs to be done first')

    def return_items(self):
        return NotImplemented('This needs to be done first')

    def find_nonempty_inventory_slots(self, origin):
        self.input_handler.click_hotkey('i')
        slots = np.zeros((12, 5))
        img_bgr = grab_screen((0, 0, self.resolution[0], self.resolution[1]))
        img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGRA2RGB)
        target_color = (0, 0, 0)
        for x_idx in range(12):
            for y_idx in range(5):
                slot_color = self._color_at_slot(img_rgb, x_idx, y_idx, origin)
                empty = self._slot_is_empty(target_color, slot_color)
                if not empty:
                    self.log.info('Slot (%d, %d) was not empty' % (x_idx, y_idx))
                    slots[x_idx, y_idx] = 1
        self.input_handler.rnd_sleep(min=300, mean=500)
        self.input_handler.click_hotkey('i')
        return slots

    def _color_at_slot(self, img, slot_x, slot_y, origin):
        x = int((origin[0] + slot_x * 0.02735) * self.resolution[0])
        y = int((origin[1] + slot_y * 0.04930555) * self.resolution[1])
        return img[y, x]

    def _slot_is_empty(self, target_color, actual_color, max_distance=16):
        distance = math.sqrt((actual_color[0] - target_color[0])**2 + \
                   (actual_color[1] - target_color[1])**2 + \
                   (actual_color[2] - target_color[2])**2)
        return distance < max_distance

    def _find_stash(self):
        img_rgb = grab_screen((0, 0, self.resolution[0], self.resolution[1]))
        img_gray = cv2.cvtColor(img_rgb, cv2.COLOR_RGBA2GRAY)
        template = cv2.imread('data/images/stash.png', 0)
        res = cv2.matchTemplate(img_gray, template, cv2.TM_CCOEFF_NORMED)
        threshold = 0.8
        stash_corner = np.where(res >= threshold)
        if len(stash_corner[0]) > 0:
            return [stash_corner[1][0] / self.resolution[0],
                    stash_corner[0][0] / self.resolution[1]]
        return None
