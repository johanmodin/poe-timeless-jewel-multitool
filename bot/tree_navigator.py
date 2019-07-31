import logging

from .input_handler import InputHandler

OWN_INVENTORY_ORIGIN = (0.6769531, 0.567361)
SOCKETS = {
1: (-650.565, -376.013),
2: (648.905, -396.45),
3: (6.3354, 765.658),
4: (-1700.9, 2424.17),
5: (-2800.66, -215.34),
6: (-1435.02, -2635.39),
7: (1855.53, -2360.1),
8: (2835.84, 230.5361),
9: (1225.37, 2625.76),
10: (-120.12471, 5195.44),
11: (-3580.19, 5905.92),
12: (-5395.86, 2120.42),
13: (-6030.95, -115.7007),
14: (-5400.59, -1985.18),
15: (-3035.14, -5400.87),
16: (160.10728, -5196.32),
17: (3382.05, -5195.21),
18: (5730.2, -1625.75),
19: (6465.24, 190.3341),
20: (5542.76, 1690.07),
21: (3322.76, 6090.5)}

MOVE_POS = {
1: (-650.565, -226.013),
2: (648.905, -246.45),
3: (6.3354, 915.658),
4: (-1719.9, 1774.17),
5: (-2470.66, -106.1434),
6: (-1549.02, -2464.39),
7: (1695.53, -2377.1),
8: (2800.84, 81.5361),
9: (1334.37, 2500.76),
10: (3.12471, 5195.44),
11: (-4822.19, 4244.92),
12: (-5446.86, 1991.42),
13: (-5886.95, -203.7007),
14: (-5644.59, -2155.18),
15: (-3144.14, -5558.87),
16: (200.10728, -5336.32),
17: (3522.05, -5287.21), #
18: (5454.2, -2502.75),
19: (5465.24, 41.3341),
20: (5068.94, 2921.07),
21: (3372.76, 5112.5)}

X_SCALE = 0.2
Y_SCALE = 0.2

### TO DO:
# Fixa så att trädnavigeraren inte har följdfel genom t ex kontrollpunkter
# och så att den blir robustare mot brus i musrörelsen
# Fixa _analyze_nodes

class TreeNavigator:
    def __init__(self, resolution):
        self.resolution = resolution
        self.input_handler = InputHandler(self.resolution)
        logging.basicConfig(level=logging.INFO)
        self.log = logging.getLogger('tree_nav')
        self.origin_pos = (self.resolution[0] / 2, self.resolution[1] / 2)
        self.ingame_pos = None

    def eval_jewel(self, item_location):
        item_stats = {}
        self.ingame_pos = [0, 0]
        item_desc = self._setup(item_location, copy=True)
        self.log.info('Analyzing %s' % item_desc)

        for socket_id in sorted(SOCKETS.keys()):
            self._move_screen_to_socket(socket_id)
            self._click_socket(socket_id)
            item_stats[socket_id] = self._analyze_nodes()

        self._setup(item_location)
        self.log.info('Analyzed %s' % item_desc)
        return

    def _move_screen_to_socket(self, socket_id):
        self.log.info('Moving close to socket %s' % socket_id)
        tree_pos_x, tree_pos_y = MOVE_POS[socket_id]

        xy = self._tree_pos_to_xy([tree_pos_x, tree_pos_y])
        xy = [xy[0] + self.origin_pos[0], xy[1] + self.origin_pos[1]]

        self.input_handler.click(*xy, *xy, button=None, raw=True)
        self.input_handler.drag(self.origin_pos[0], self.origin_pos[1])
        self.input_handler.rnd_sleep(min=1000, mean=1000)
        self.ingame_pos = [tree_pos_x, tree_pos_y]

    def _click_socket(self, socket_id):
        self.log.info('Clicking socket %s' % socket_id)
        tree_pos_x, tree_pos_y = SOCKETS[socket_id]
        xy = self._tree_pos_to_xy([tree_pos_x, tree_pos_y])
        xy = [xy[0] + self.origin_pos[0], xy[1] + self.origin_pos[1]]
        self.input_handler.click(*xy, *xy, button=None, raw=True)
        self.input_handler.rnd_sleep(min=1000, mean=1000)

    def _tree_pos_to_xy(self, pos):
        return [(pos[0] - self.ingame_pos[0]) * X_SCALE,
                (pos[1] - self.ingame_pos[1]) * Y_SCALE]


    def _analyze_nodes(self):
        return 0

    def _setup(self, item_location, copy=False):
        item_desc = None
        self.input_handler.click_hotkey('p')
        self.input_handler.rnd_sleep(min=50, mean=150)
        self.input_handler.click_hotkey('i')
        if copy:
            self.input_handler.rnd_sleep(min=50, mean=150)
            item = self.input_handler.inventory_copy(*item_location, OWN_INVENTORY_ORIGIN, speed_factor=2)
            item_desc = item.split('\n')[9].strip()
        self.input_handler.rnd_sleep(min=50, mean=150)
        self.input_handler.inventory_click(*item_location, OWN_INVENTORY_ORIGIN)
        self.input_handler.rnd_sleep(min=50, mean=150)
        self.input_handler.click_hotkey('i')
        self.input_handler.rnd_sleep(min=50, mean=150)
        return item_desc
