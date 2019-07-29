from queue import Queue
from pymongo import MongoClient
from logging import Logger
from datetime import datetime

from trader import Trader
from tree_navigator import TreeNavigator
from utils import get_config


class Bot:
    def __init__(self):
        self.log = Logger('bot')
        self.config = get_config('bot')
        self.resolution = self.split_res(self.config['resolution'])
        self.tree_nav = TreeNavigator(self.resolution)
        self.trader = Trader(self.resolution)
        self.input_handler = InputHandler(self.resolution)
        self.db = MongoClient(self.config['db_url'])
        self.run = True

    def loop(self):
        while self.run:
            empty = self.trader.verify_empty_inventory()
            if not empty:
                self.trader.stash_items()
            username = self.trader.wait_for_trade()
            item_locations = self.trader.get_items()
            if not item_locations:
                continue
            jewels = []
            for item_location in item_locations:
                description, stats = self.tree_nav.eval_jewel(item_location)
                jewels.append((description, stats))
            self.store_items(jewels, username)
            self.trader.return_items(username, item_locations)

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
        result = self.db['timeless'].insert_many(item_list)
        return result

    def split_res(self, resolution):
        resolution = resolution.split('x')
        return resolution
