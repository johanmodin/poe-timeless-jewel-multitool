import logging
import numpy as np
import math
from matplotlib import pyplot
import time
from queue import Queue
from datetime import datetime, timedelta

from .input_handler import InputHandler
from .utils import get_config
from .grabscreen import grab_screen
import cv2

OWN_INVENTORY_ORIGIN = (0.6769531, 0.567361)
TRADE_PARTNER_ORIGIN = (0.17578, 0.2118)
INVITATION_TIMEOUT = 30
TRADE_TIMEOUT = 16
TRADE_RETRIES = 2
TRADE_TIMEOUT_AFTER_INITIATED = 30
RETURN_TRADE_TIMEOUT = 15

class Trader:
    def __init__(self, resolution, accept_trades):
        self.resolution = resolution
        self.config = get_config('trader')
        self.input_handler = InputHandler(self.resolution)
        logging.basicConfig(level=logging.INFO,
            format='%(asctime)s %(message)s', datefmt='[%H:%M:%S %d-%m-%Y]')
        self.log = logging.getLogger('trader')
        if accept_trades:
            self.trade_queue = Queue()
            self.invite_message = self.config['invite_message']
            self.trade_queue_set = set()
            with open(self.config['log_path'], 'r', encoding="utf8") as f:
                for i, l in enumerate(f):
                    pass
                byte_pos = f.tell()
            self.byte_pos = byte_pos

    def stash_items(self):
        stash_loc = self._find_stash()
        self.log.info('Found stash at %s' % stash_loc)
        stash_loc_br = [stash_loc[0] + 0.005, stash_loc[1] + 0.005]
        self.input_handler.click(*stash_loc, *stash_loc_br)
        self.input_handler.rnd_sleep(min=1200, mean=1500)
        slots = self.find_nonempty_inventory_slots(origin=OWN_INVENTORY_ORIGIN)
        item_locations = np.argwhere(slots == 1)
        for loc in item_locations:
            self.input_handler.inventory_click(loc[0], loc[1],
                inventory_base=OWN_INVENTORY_ORIGIN, ctrl_click=True)
        self.input_handler.click_keys([0x81])

        items_stashed = len(item_locations)

        if items_stashed > 0:
            self.log.info('Stashed %s items' % items_stashed)
        else:
            self.log.info('No stashing needed, inventory empty')

    def verify_empty_inventory(self):
        self.input_handler.click_hotkey('i')
        slots = self.find_nonempty_inventory_slots(origin=OWN_INVENTORY_ORIGIN)
        self.input_handler.click_hotkey('i')
        non_empty = int(np.sum(slots))
        self.log.info('Non-empty slots found: %d' % non_empty)
        return non_empty == 0

    def wait_for_trade(self):
        self.log.info('Waiting for trading partner')
        trade_partner_in_area = False
        while not trade_partner_in_area:
            while self.trade_queue.empty():
                messages = self.tail(set_seeker=True)
                for message in messages:
                    if message['text'] == self.invite_message and message['type'] == 'whisper':
                        self._put_in_trade_queue(message['user'])
                time.sleep(0.1)
            trade_partner = self._get_from_trade_queue()
            trade_partner_in_area = self._invite_and_wait_for_player(trade_partner)
        return trade_partner

    def _invite_and_wait_for_player(self, username):
        self.input_handler.type('/invite %s' % username)
        timeout_at = datetime.now() + timedelta(seconds=INVITATION_TIMEOUT)
        player_in_ho = False
        sought_message = username + ' has joined the area.'
        while datetime.now() < timeout_at:
            messages = self.tail(max_age=timedelta(seconds=10))
            for message in messages:
                if message['type'] == 'info' and message['text'] == sought_message:
                    return True
            time.sleep(0.1)
        return False

    def _put_in_trade_queue(self, user):
        if user not in self.trade_queue_set:
            self.trade_queue_set.add(user)
            self.trade_queue.put(user)

    def _get_from_trade_queue(self):
        user = self.trade_queue.get()
        self.trade_queue_set.remove(user)
        return user

    def tail(self, set_seeker=False, max_age=None):
        file_handle = open(self.config['log_path'], 'r', encoding="utf8")
        file_handle.seek(self.byte_pos)
        lines = []
        while True:
            line = file_handle.readline()
            if line:
                lines.append(line[:-1])
            else:
                break
        if set_seeker:
            self.byte_pos = file_handle.tell()
        file_handle.close()
        if max_age is None:
            messages = [self._split_chat_msg(line) for line in lines]
        else:
            messages = [self._split_chat_msg(line) for line in lines if
                        self._split_chat_msg(line)['time'] > datetime.now() - max_age]
        if messages:
            self.log.info('interpreted messages: %s' % messages)
        return messages

    def get_items(self, username):
        self.log.info('Trying to open trade with %s' % username)
        initiated = self._initiate_trade(username)
        if not initiated:
            self.log.info('Failed to open trade with %s' % username)
            return None
        self.log.info('Opened trade with %s' % username)
        trade_successful = self._get_partners_trade_items()
        return trade_successful

    def get_jewel_locations(self):
        self.input_handler.click_hotkey('i')
        slots = self.find_nonempty_inventory_slots(origin=OWN_INVENTORY_ORIGIN)
        item_locations = np.argwhere(slots == 1)
        jewel_descriptions = []
        for item_location in item_locations:
            item = self.input_handler.inventory_copy(item_location[0], item_location[1], OWN_INVENTORY_ORIGIN, speed_factor=3)
            item_type = item.split('\n')[2].strip()

            if item_type != 'Timeless Jewel':
                slots[item_location[0], item_location[1]] = 0
                self.log.info('Received item: %s' % item)
            else:
                item_desc = item.split('\n')[9].strip()
                self.log.info('Received jewel: %s' % item_desc)
                jewel_descriptions.append(item_desc)
        jewel_locations = np.argwhere(slots == 1)
        self.input_handler.click_hotkey('i')
        return jewel_locations, jewel_descriptions

    def return_items(self, username, locations):
        self.log.info('Trying to do a return trade with %s' % username)
        initiated = self._initiate_trade(username)
        if not initiated:
            self.log.info('Failed to do a return trade with %s' % username)
            return None
        self.log.info('Opened return trade with %s' % username)
        trade_successful = self._return_partners_trade_items(locations)
        return trade_successful

    def _return_partners_trade_items(self, locations):
        for location in locations:
            self.input_handler.inventory_click(location[0], location[1],
                                               OWN_INVENTORY_ORIGIN,
                                               ctrl_click=True, speed_factor=2)
        self._accept_trade()
        timeout = datetime.now() + timedelta(seconds=RETURN_TRADE_TIMEOUT)
        sought_message = 'Trade accepted.'
        while datetime.now() < timeout:
            messages = self.tail(max_age=timedelta(seconds=15))
            for message in messages:
                if message['type'] == 'info' and message['text'] == sought_message:
                    return True
        self.input_handler.click_keys([0x81]) # Escape trade screen
        return False

    def _initiate_trade(self, username):
        for try_idx in range(TRADE_RETRIES):
            self.input_handler.type('/tradewith %s' % username)
            timeout = datetime.now() + timedelta(seconds=TRADE_TIMEOUT)
            while datetime.now() < timeout:
                trade_initiated = self._trade_window_open()
                if trade_initiated:
                    return True
                time.sleep(0.1)
        return False

    def _trade_window_open(self):
        img_bgr = grab_screen((0, 0, *self.resolution))
        img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGRA2RGB)
        target_color = (183, 125, 66)
        x = int(0.29765 * self.resolution[0])
        y = int(0.08889 * self.resolution[1])
        actual_color = img_rgb[y, x]
        return self._close_colors(target_color, actual_color, max_distance=25)

    def _get_partners_trade_items(self):
        timeout = datetime.now() + timedelta(seconds=TRADE_TIMEOUT_AFTER_INITIATED)
        while datetime.now() < timeout:
            self._hover_trade_partner()
            self.input_handler.inventory_click(-1, -1,
                                               inventory_base=TRADE_PARTNER_ORIGIN)
            if self._partner_has_accepted():
                self._hover_trade_partner()
                self._accept_trade()
                self.input_handler.rnd_sleep()
                return True
        return False

    def _hover_trade_partner(self):
        slots = self.find_nonempty_inventory_slots(origin=TRADE_PARTNER_ORIGIN)
        item_locations = np.argwhere(slots == 1)
        for loc in item_locations:
            self.input_handler.inventory_click(loc[0], loc[1],
                                               inventory_base=TRADE_PARTNER_ORIGIN,
                                               button=None, speed_factor=3)

    def _accept_trade(self):
        self.input_handler.click(0.18086, 0.76041, 0.19148, 0.7607)

    def _partner_has_accepted(self):
        img_bgr = grab_screen((0, 0, *self.resolution))
        img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGRA2RGB)
        target_color = (49, 62, 42)
        x = int(0.32617 * self.resolution[0])
        y = int(0.18264 * self.resolution[1])
        actual_color = img_rgb[y, x]
        return self._close_colors(target_color, actual_color)


    def find_nonempty_inventory_slots(self, origin):
        slots = np.zeros((12, 5))
        img_bgr = grab_screen((0, 0, *self.resolution))
        img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGRA2RGB)
        target_color = (0, 0, 0)
        for x_idx in range(12):
            for y_idx in range(5):
                slot_color = self._color_at_slot(img_rgb, x_idx, y_idx, origin)
                empty = self._close_colors(target_color, slot_color)
                if not empty:
                    self.log.info('Slot (%d, %d) was not empty' % (x_idx, y_idx))
                    slots[x_idx, y_idx] = 1
        self.input_handler.rnd_sleep(min=300, mean=500)
        return slots

    def _color_at_slot(self, img, slot_x, slot_y, origin):
        x = int((origin[0] + slot_x * 0.02735) * self.resolution[0])
        y = int((origin[1] + slot_y * 0.04930555) * self.resolution[1])
        return img[y, x]

    def _close_colors(self, target_color, actual_color, max_distance=16):
        self.log.debug(actual_color)
        distance = math.sqrt((actual_color[0] - target_color[0])**2 + \
                   (actual_color[1] - target_color[1])**2 + \
                   (actual_color[2] - target_color[2])**2)
        self.log.debug('Measured color distance of: %s' % distance)
        return distance < max_distance

    def _find_stash(self):
        img_rgb = grab_screen((0, 0, *self.resolution))
        img_gray = cv2.cvtColor(img_rgb, cv2.COLOR_RGBA2GRAY)
        template = cv2.imread('data/images/stash.png', 0)
        res = cv2.matchTemplate(img_gray, template, cv2.TM_CCOEFF_NORMED)
        threshold = 0.8
        stash_corner = np.where(res >= threshold)
        if len(stash_corner[0]) > 0:
            return [stash_corner[1][0] / self.resolution[0],
                    stash_corner[0][0] / self.resolution[1]]
        return None

    def _split_chat_msg(self, line):
        msg = {}
        if len(line) < 30:
            msg['type'] = 'other'
            return msg
        time = line[:20]
        ms = line[26:29] + '000'
        full_time = time + ms
        msg['time'] = datetime.strptime(full_time, '%Y/%m/%d %H:%M:%S %f')
        last_info_idx = line.find(']') + 2
        content = line[last_info_idx: ]
        if content[0] == ':':
            msg['type'] = 'info'
        elif content[0] == '#':
            msg['type'] = 'global'
        elif content[0] == '%':
            msg['type'] = 'party'
        elif content[0] == '@':
            msg['type'] = 'whisper'
        else:
            msg['type'] = 'other'

        msg['user'] = None
        msg['text'] = None
        if msg['type'] in ['global', 'party', 'whisper']:
            name_start = last_info_idx + len(content.split(' ')[0])
            name_end = name_start + line[name_start: ].find(':')
            name = line[name_start: name_end].lower()
            if '>' in name:
                name = name[name.find('>') + 2: ]
            msg['user'] = name
            msg['text'] = line[name_end + 2: ]
        elif msg['type'] == 'info':
            msg['text'] = content[2:]
        return msg
