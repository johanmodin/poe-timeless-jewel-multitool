import logging

from .input_handler import InputHandler


class TreeNavigator:
    def __init__(self, resolution):
        self.resolution = resolution
        self.input_handler = InputHandler(self.resolution)
        logging.basicConfig(level=logging.INFO)
        self.log = logging.getLogger('tree_nav')

    def eval_jewel(self, item_location):
        return NotImplemented('This needs to be done first')
