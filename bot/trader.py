from logging import Logger

from grabscreen import grab_screen
import cv2

class Trader:
    def __init__(self, resolution):
        self.resolution = resolution
        self.config = get_config('trader')

    def stash_items(self):
        return NotImplemented('This needs to be done first')

    def verify_empty_inventory(self):
        return NotImplemented('This needs to be done first')

    def wait_for_trade(self):
        return NotImplemented('This needs to be done first')

    def get_items(self):
        return NotImplemented('This needs to be done first')

    def return_items(self):
        return NotImplemented('This needs to be done first')


    def _find_stash(self):
            img_rgb = grab_screen((0, 0, self.resolution[0], self.resolution[1]))
            img_gray = cv2.cvtColor(img_rgb, cv2.COLOR_BGR2GRAY)
            template = cv2.imread('stash.png', 0)
            res = cv2.matchTemplate(img_gray, template, cv2.TM_CCOEFF_NORMED)
            threshold = 0.8
            return np.where(res >= threshold)
