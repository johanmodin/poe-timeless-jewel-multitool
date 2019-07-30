from queue import Queue
from pymongo import MongoClient
from datetime import datetime
import logging
import time

from .trader import Trader
from .tree_navigator import TreeNavigator
from .utils import get_config
from .input_handler import InputHandler


class Bot:
    def __init__(self):
        logging.basicConfig(level=logging.INFO)
        self.log = logging.getLogger('bot')
        self.config = get_config('bot')
        self.resolution = self.split_res(self.config['resolution'])
        self.tree_nav = TreeNavigator(self.resolution)
        self.trader = Trader(self.resolution)
        self.input_handler = InputHandler(self.resolution)
        self.db = MongoClient(self.config['db_url'])['project_timeless']
        self.run = True

    def loop(self):
        time.sleep(2)
        while self.run:
            empty = self.trader.verify_empty_inventory()
            if not empty:
                self.trader.stash_items()
            username = self.trader.wait_for_trade()
            successfully_received = self.trader.get_items(username)
            if not successfully_received:
                continue
            jewels = []
            jewel_locations = self.trader.get_jewel_locations()
            self.log.info('Got new jewels at %s' % jewel_locations)
            #for jewel_location in jewel_locations:
            #    description, stats = self.tree_nav.eval_jewel(jewel_location)
            #    jewels.append((description, stats))
            #self.store_items(jewels, username)
            self.trader.return_items(username, jewel_locations)

    def store_items(self, items, reporter):
        item_list = []
        creation_time = datetime.utcnow()
        for item in items:
            new_item = {}
            description, stats = item
            new_item['description'] = description
            new_item['stats'] = stats
            new_item['reporter'] = reporter
            new_item['created'] = creation_time
            item_list.append(new_item)
        result = self.db['jewels'].insert_many(item_list)
        return result

    def split_res(self, resolution):
        resolution = [int(n) for n in resolution.split('x')]
        return resolution
