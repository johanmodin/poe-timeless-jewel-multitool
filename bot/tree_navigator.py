import logging
import cv2
import numpy as np
from PIL import Image
import pytesseract
import os
import time
from multiprocessing import Pool
import json

from .input_handler import InputHandler
from .grabscreen import grab_screen
from .utils import get_config

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
NODE_TEMPLATE_THRESHOLD = 0.1
TEXTBOX_MOUSE_OFFSET = [32, 0]
CIRCLE_EFFECTIVE_RADIUS = 300

IMAGE_FOLDER = 'data/images/'
TEMPLATES = {'Notable.png': {'size': (32, 32), 'threshold': 0.8},
             'NotableAllocated.png': {'size': (32, 32), 'threshold': 0.9},
             'Skill.png': {'size': (21, 21), 'threshold': 0.87},
             'SkillAllocated.png': {'size': (21, 21), 'threshold':  0.92}}

TXT_BOX = {'x': 30, 'y': 0, 'w': 900, 'h': 320}

mod_files = {
    "passives":  "data/passives.json",
    "passivesAlt": "data/passivesAlternatives.json",
    "passivesAdd": "data/passivesAdditions.json",
    "passivesVaalAdd": "data/passivesVaalAdditions.json",
}

### TO DO:
# Fixa så att trädnavigeraren inte har följdfel genom t ex kontrollpunkter
# och så att den blir robustare mot brus i musrörelsen
# Fixa _analyze_nodes
# Fixa så att keystones känns igen

class TreeNavigator:
    def __init__(self, resolution):
        self.resolution = resolution
        self.input_handler = InputHandler(self.resolution)
        logging.basicConfig(level=logging.INFO)
        self.log = logging.getLogger('tree_nav')
        self.config = get_config('tree_nav')
        self.origin_pos = (self.resolution[0] / 2, self.resolution[1] / 2)
        self.ingame_pos = [0, 0]
        self.templates_and_masks = self.load_templates()
        self.accepted_node_strings = self.generate_good_strings(mod_files)


    def eval_jewel(self, item_location):
        item_stats = {}
        self.ingame_pos = [0, 0]
        item_desc = self._setup(item_location, copy=True)
        self.log.info('Analyzing %s' % item_desc)

        #pool = Pool(self.config['ocr_threads'])
        jobs = []
        #for socket_id in sorted(SOCKETS.keys()):
        for socket_id in [1, 3]:
            self._move_screen_to_socket(socket_id)
            socket_nodes = self._analyze_nodes(socket_id)
            socket_nodes = OCR.nodes_to_strings(socket_nodes)
            socket_nodes = self._filter_ocr_lines(socket_nodes)
            self.log.info(socket_nodes)
            item_stats[socket_id] = socket_nodes
            # Convert stats for the socket from image to lines in separate process
            #jobs.append({socket_id: pool.apply_async(OCR.nodes_to_string, socket_nodes)})

        #results = [socket_id: jobs[socket_id].get(timeout=120) for socket_id in jobs]
        self._setup(item_location)
        self.log.info('Analyzed %s' % item_desc)
        return item_desc, item_stats

    def load_templates(self, threshold = 128):
        templates_and_masks = {}
        for template_name in TEMPLATES.keys():
            template_path = os.path.join(IMAGE_FOLDER, template_name)
            img = cv2.imread(template_path, cv2.IMREAD_UNCHANGED)

            channels = cv2.split(img)
            mask = np.array(channels[3])

            mask[mask <= threshold] = 0
            mask[mask > threshold] = 255
            img = cv2.imread(template_path, 0)

            size = TEMPLATES[template_name]['size']
            img = cv2.resize(img, size)
            mask = cv2.resize(mask, size)
            templates_and_masks[template_name] = {'image':img, 'mask': mask}
        return templates_and_masks



    def _move_screen_to_socket(self, socket_id):
        self.log.info('Moving close to socket %s' % socket_id)
        tree_pos_x, tree_pos_y = MOVE_POS[socket_id]

        xy = self._tree_pos_to_xy([tree_pos_x, tree_pos_y])

        self.input_handler.click(*xy, *xy, button=None, raw=True)
        self.input_handler.drag(self.origin_pos[0], self.origin_pos[1])
        self.input_handler.rnd_sleep(min=1000, mean=1000)
        self.ingame_pos = [tree_pos_x, tree_pos_y]

    def _click_socket(self, socket_id, insert=True):

        self.log.info('Clicking socket %s' % socket_id)
        tree_pos_x, tree_pos_y = SOCKETS[socket_id]
        xy = self._tree_pos_to_xy([tree_pos_x, tree_pos_y])
        if insert:
            self.input_handler.click(*xy, *xy, button='left', raw=True)
        else:
            self.input_handler.click(*xy, *xy, button='right', raw=True)
        self.input_handler.rnd_sleep(min=1000, mean=1000)

    def _tree_pos_to_xy(self, pos):
        uncentered_xy =  [(pos[0] - self.ingame_pos[0]) * X_SCALE,
               (pos[1] - self.ingame_pos[1]) * Y_SCALE]
        xy = [uncentered_xy[0] + self.origin_pos[0],
              uncentered_xy[1] + self.origin_pos[1]]
        return xy

    def _analyze_nodes(self, socket_id):
        self.log.info('Analyzing nodes for socket id %s' % socket_id)
        nodes = []
        node_locations = self._find_nodes(socket_id)
        self.log.info('Found %s nodes for socket id %s' % (len(node_locations), socket_id))
        self._click_socket(socket_id)
        for location in node_locations:
            node_stats = self._get_node_data(location)
            node = {'location': location, 'stats': node_stats}
            nodes.append(node)
        self._click_socket(socket_id, insert=False)
        return nodes

    def _filter_ocr_lines(self, nodes_lines):
        filtered_nodes = []
        for node in nodes_lines:
            filtered_stats = [l for l in node['stats'] if
                              self._filter_nonalpha(l) in self.accepted_node_strings]
            filtered_nodes.append({'location': node['location'],
                                   'stats': filtered_stats})
        return filtered_nodes

    def _find_nodes(self, socket_id):
        socket_pos = self._tree_pos_to_xy(SOCKETS[socket_id])
        x1 = int(socket_pos[0] - CIRCLE_EFFECTIVE_RADIUS)
        y1 = int(socket_pos[1] - CIRCLE_EFFECTIVE_RADIUS)
        x2 = int(x1 + 2 * CIRCLE_EFFECTIVE_RADIUS)
        y2 = int(y1 + 2 * CIRCLE_EFFECTIVE_RADIUS)
        xy = self._tree_pos_to_xy(MOVE_POS[socket_id])
        self.input_handler.click(*xy, *xy, button=None, raw=True)

        nodes = self._get_node_locations_from_screen((x1, y1, x2, y2))
        nodes = self._filter_nodes(nodes, socket_pos)

        '''
        jewel_area_bgr = grab_screen((x1, y1, x2, y2))
        for pt in nodes:
            pt -= [x1, y1]
            cv2.rectangle(jewel_area_bgr, (pt[0]-2, pt[1]-2), (pt[0] + 2, pt[1] + 2), (0,0,255), 2)
        cv2.imshow('nodes', jewel_area_bgr)
        cv2.waitKey()
        '''

        return nodes

    def _filter_nodes(self, nodes, socket_pos, duplicate_min_dist=10):
        # filter duplicate nodes
        kept_node_indices = [len(nodes) - 1]
        z = np.array([[complex(c[0], c[1]) for c in nodes]])
        dist_matrix = abs(z.T-z)
        for node_idx in range(len(nodes) - 1):
            if np.min(dist_matrix[node_idx + 1:, node_idx]) >= duplicate_min_dist:
                kept_node_indices.append(node_idx)
        nodes = np.array(nodes)
        nodes = nodes[kept_node_indices, :]

        # filter nodes outside jewel socket radius
        distances_to_socket = np.sqrt(np.sum((nodes - socket_pos)**2, axis=1))
        nodes = nodes[distances_to_socket <= CIRCLE_EFFECTIVE_RADIUS]
        return nodes


    def _get_node_locations_from_screen(self, box):
        jewel_area_bgr = grab_screen(box)
        jewel_area_gray = cv2.cvtColor(jewel_area_bgr, cv2.COLOR_BGR2GRAY)

        locations = np.zeros((CIRCLE_EFFECTIVE_RADIUS * 2, CIRCLE_EFFECTIVE_RADIUS * 2))

        for idx, template_name in enumerate(self.templates_and_masks.keys()):
            template = self.templates_and_masks[template_name]['image']
            mask = self.templates_and_masks[template_name]['mask']
            res = cv2.matchTemplate(jewel_area_gray, template, cv2.TM_CCORR_NORMED, mask=mask)
            coordinates = np.where(res >= TEMPLATES[template_name]['threshold'])
            icon_size = TEMPLATES[template_name]['size']
            icon_center_offset = [int(icon_size[0] / 2), int(icon_size[1] / 2)]
            centered_coordinates = [coordinates[0] + icon_center_offset[0],
                                    coordinates[1] + icon_center_offset[1]]
            locations[centered_coordinates] = 1

        rel_node_pos_yx = np.argwhere(locations == 1)
        rel_node_pos = rel_node_pos_yx.T[::-1].T
        abs_node_pos = rel_node_pos + [box[0], box[1]]
        return abs_node_pos

    def _get_node_data(self, location):
        self.log.info('Getting node stats at location %s' % location)
        self.input_handler.click(*location, *location, button=None, raw=True, speed_factor=3)
        textbox_lt = location + TEXTBOX_MOUSE_OFFSET
        textbox_rb = textbox_lt + [TXT_BOX['w'], TXT_BOX['h']]


        jewel_area_bgr = grab_screen(tuple(np.concatenate([textbox_lt, textbox_rb])))
        return jewel_area_bgr


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

    def generate_good_strings(self, files):
        mods = set()
        for name in files:
            path = files[name]
            with open(path) as f:
                data = json.load(f)
                if isinstance(data, dict):
                    mods.update([self._filter_nonalpha(k) for k in data.keys()])
                    for key in data.keys():
                        if isinstance(data[key]['passives'][0], list):
                            mods.update([self._filter_nonalpha(e) for e in data[key]['passives'][0]])
                        else:
                            mods.update([self._filter_nonalpha(e) for e in data[key]['passives']])
                else:
                    mods.update([self._filter_nonalpha(e) for e in data])
        mods.remove('')
        return mods

    def _filter_nonalpha(self, value):
        return ''.join(list(filter(lambda x: x.isalpha(), value)))

# Adapted from https://github.com/klayveR/python-poe-timeless-jewel
class OCR:
    @staticmethod
    def clahe(img, clip_limit = 2.0, grid_size = (8,8)):
        clahe = cv2.createCLAHE(clipLimit = clip_limit, tileGridSize = grid_size)
        return clahe.apply(img)

    @staticmethod
    def getFilteredImage(src):
        srcH, srcW = src.shape[:2]
        src = cv2.resize(src, (int(srcW * 1.5), int(srcH * 1.5)))

        # HSV thresholding to get rid of as much background as possible
        src = cv2.cvtColor(src, cv2.COLOR_BGRA2BGR)
        hsv = cv2.cvtColor(src.copy(), cv2.COLOR_BGR2HSV)
        lower_blue = np.array([0, 0, 180])
        upper_blue = np.array([180, 38, 255])
        mask = cv2.inRange(hsv, lower_blue, upper_blue)
        result = cv2.bitwise_and(src, src, mask = mask)
        b, g, r = cv2.split(result)
        g = OCR.clahe(g, 5, (5, 5))
        inverse = cv2.bitwise_not(g)
        return inverse

    @staticmethod
    def imageToStringArray(img):
        t = pytesseract.image_to_string(img, lang='eng', \
            config='--oem 3 --psm 12 poe')
        t = t.replace("\n\n", "\n")
        lines = t.split("\n")
        return lines

    @staticmethod
    def nodes_to_strings(nodes):
        converted_nodes = []
        for node in nodes:
            img = node['stats']
            filt_img = OCR.getFilteredImage(img)
            text = OCR.imageToStringArray(img)
            converted_nodes.append({'location': node['location'],
                                    'stats': text})
        return converted_nodes
