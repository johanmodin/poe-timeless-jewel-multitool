import logging
import cv2
import numpy as np
import pytesseract
import os
import time
import json
import re


from multiprocessing import Pool
from Levenshtein import distance

from .input_handler import InputHandler
from .grabscreen import grab_screen
from .utils import get_config, filter_mod

# This is a position of the inventory as fraction of the resolution
OWN_INVENTORY_ORIGIN = (0.6769531, 0.567361)

# These are the sockets positions as measured on 2560x1440 resolution
# with X_SCALE and Y_SCALE applied, i.e., scale * SOCKETS[i] is the i:th
# sockets absolute pixel position with origin in the middle of the skill tree
# I think the SCALE variables are in fact useless and a relics from the
# positions initially being measured at a view which wasn't zoomed out maximally
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
    21: (3322.76, 6090.5),
}

# The offsets are specified in the same fashion as SOCKETS and are rough
# guesses which allow us to move to the general area and later refine the
# position of the socket through template matching
SOCKET_MOVE_OFFSET = {
    1: (0, 150),
    2: (0, 150),
    3: (0, 200),
    4: (0, 150),
    5: (-300, 200),
    6: (-100, 150),
    7: (-150, 0),
    8: (0, -150),
    9: (-100, -125),
    10: (170, 0),
    11: (-400, -900),
    12: (0, 300),
    13: (400, 200),
    14: (-250, -150),
    15: (-100, -150),
    16: (150, -150),
    17: (150, 500),  #
    18: (-300, 400),
    19: (-1000, -150),
    20: (-500, 500),
    21: (100, -1000),
}


# Scalers for the SOCKETS positions to convert them to 2560x1440 pixel positions
X_SCALE = 0.2
Y_SCALE = 0.2
CIRCLE_EFFECTIVE_RADIUS = 300

IMAGE_FOLDER = "data/images/"

# We're using a lot of template matching and all templates are defined here
# with matching thresholds (scores) and sizes per resolution
TEMPLATES = {
    "AmbidexterityCluster.png": {
        "1440p_size": (34, 34),
        "1440p_threshold": 0.95,
        "1080p_size": (26, 26),
        "1080p_threshold": 0.95,
    },
    "FreeSpace.png": {
        "1440p_size": (41, 41),
        "1440p_threshold": 0.98,
        "1080p_size": (30, 30),
        "1080p_threshold": 0.98,
    },
    "Notable.png": {
        "1440p_size": (30, 30),
        "1440p_threshold": 0.89,
        "1080p_size": (23, 23),
        "1080p_threshold": 0.85,
    },
    "NotableAllocated.png": {
        "1440p_size": (30, 30),
        "1440p_threshold": 0.93,
        "1080p_size": (23, 23),
        "1080p_threshold": 0.90,
    },
    "Jewel.png": {
        "1440p_size": (30, 30),
        "1440p_threshold": 0.92,
        "1080p_size": (23, 23),
        "1080p_threshold": 0.92,
    },
    "JewelSocketed.png": {
        "1440p_size": (30, 30),
        "1440p_threshold": 0.9,
        "1080p_size": (23, 23),
        "1080p_threshold": 0.9,
    },
    "LargeJewel.png": {
        "1440p_size": (39, 39),
        "1440p_threshold": 0.9,
        "1080p_size": (30, 30),
        "1080p_threshold": 0.88,
    },
    "LargeJewelSocketed.png": {
        "1440p_size": (39, 39),
        "1440p_threshold": 0.9,
        "1080p_size": (30, 30),
        "1080p_threshold": 0.88,
    },
    "Skill.png": {
        "1440p_size": (21, 21),
        "1440p_threshold": 0.87,
        "1080p_size": (15, 15),
        "1080p_threshold": 0.91,
    },
    "SkillAllocated.png": {
        "1440p_size": (21, 21),
        "1440p_threshold": 0.93,
        "1080p_size": (15, 15),
        "1080p_threshold": 0.91,
    },
}

# Defines the position of the text box which is cropped out and OCR'd per node
TXT_BOX = {"x": 32, "y": 0, "w": 900, "h": 320}

mod_files = {
    "passives": "data/passives.json",
    "passivesAlt": "data/passivesAlternatives.json",
    "passivesAdd": "data/passivesAdditions.json",
    "passivesVaalAdd": "data/passivesVaalAdditions.json",
}


class TreeNavigator:
    def __init__(self, resolution, halt_value):
        self.resolution = resolution
        self.input_handler = InputHandler(self.resolution)
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s %(message)s",
            datefmt="[%H:%M:%S %d-%m-%Y]",
        )
        self.log = logging.getLogger("tree_nav")
        self.config = get_config("tree_nav")
        self.find_mod_value_re = re.compile("(\(?(?:[0-9]*\.?[0-9]-?)+\)?)")
        self.nonalpha_re = re.compile("[^a-zA-Z]")
        self.origin_pos = (self.resolution[0] / 2, self.resolution[1] / 2)
        self.ingame_pos = [0, 0]
        self.px_multiplier = self.resolution[0] / 2560
        self.resolution_prefix = str(self.resolution[1]) + "p_"
        self.templates_and_masks = self.load_templates()
        self.passive_mods, self.passive_names = self.generate_good_strings(mod_files)
        self.passive_nodes = list(self.passive_mods.keys()) + list(
            self.passive_names.keys()
        )
        self.halt = halt_value
        self.first_run = True

    def _run(self):
        return not bool(self.halt.value)

    def eval_jewel(self, item_location):
        self.ingame_pos = [0, 0]
        item_name, item_desc = self._setup(item_location, copy=True)

        pool = Pool(self.config["ocr_threads"])
        jobs = {}

        if self.first_run:
            # We just initiated the module and not sure where we are
            # Thus, we better rectify our position estimate before starting
            self._refind_position(SOCKETS[1])
            self.first_run = False

        for socket_id in sorted(SOCKETS.keys()):
            if not self._run():
                return None, None, None
            found_socket = self._move_screen_to_socket(socket_id)
            if not found_socket and socket_id == 1:
                self.log.info("We are lost - trying to find known location")
                # We just initiated the search and have no clue where we are
                # Thus, we better rectify our position estimate before starting
                self._refind_position(SOCKETS[1])
            socket_nodes = self._analyze_nodes(socket_id)

            # Convert stats for the socket from image to lines in separate process
            self.log.info("Performing asynchronous OCR")
            jobs[socket_id] = pool.map_async(OCR.node_to_strings, socket_nodes)
            self.log.info("Analyzed socket %s" % socket_id)

        # Return to socket 1 to ease next search
        self._move_to_tree_pos_using_spaces(SOCKETS[1])

        self._setup(item_location)
        self.log.info("Waiting for last OCR to finish")
        item_stats = [
            {
                "socket_id": socket_id,
                "socket_nodes": self._filter_ocr_lines(
                    jobs[socket_id].get(timeout=300)
                ),
            }
            for socket_id in jobs
        ]
        pool.close()
        pool.join()
        return item_name, item_desc, item_stats

    def load_templates(self, threshold=128):
        templates_and_masks = {}
        for template_name in TEMPLATES.keys():
            template_path = os.path.join(IMAGE_FOLDER, template_name)
            img = cv2.imread(template_path, cv2.IMREAD_UNCHANGED)
            size = TEMPLATES[template_name][self.resolution_prefix + "size"]
            channels = cv2.split(img)
            mask = None
            if len(channels) > 3:
                mask = np.array(channels[3])
                mask[mask <= threshold] = 0
                mask[mask > threshold] = 255
                mask = cv2.resize(mask, size)

            img = cv2.imread(template_path, 0)
            img = cv2.resize(img, size)
            templates_and_masks[template_name] = {"image": img, "mask": mask}
        return templates_and_masks

    def _move_screen_to_socket(self, socket_id):
        self.log.debug("Moving close to socket %s" % socket_id)
        move_offset_tx, move_offset_ty = SOCKET_MOVE_OFFSET[socket_id]
        move_offset = self._tree_pos_to_xy(
            [move_offset_tx, move_offset_ty], offset=True
        )

        socket_tx, socket_ty = SOCKETS[socket_id]
        socket_xy = self._tree_pos_to_xy([socket_tx, socket_ty])
        compensation_offset = self._find_socket(socket_xy)
        if compensation_offset is None:
            found_socket = False
            compensation_offset = [0, 0]
        else:
            found_socket = True
            self.log.debug("Compensated navigation with %s" % compensation_offset)

        move_to = [
            socket_xy[0] + compensation_offset[0] + move_offset[0],
            socket_xy[1] + compensation_offset[1] + move_offset[1],
        ]

        x_offset = move_to[0] - self.resolution[0] / 2
        y_offset = move_to[1] - self.resolution[1] / 2

        self.input_handler.click(
            *move_to, *move_to, button=None, raw=True, speed_factor=1
        )
        self.input_handler.drag(self.origin_pos[0], self.origin_pos[1], speed_factor=1)
        self.input_handler.rnd_sleep(min=200, mean=300, sigma=100)
        self.ingame_pos = [socket_tx + move_offset_tx, socket_ty + move_offset_ty]
        return found_socket

    def _refind_position(self, desired_tree_pos):
        # If the current location has been determined to be incorrect
        # we can go to the bottom right corner and find a cluster close
        # to socket 21, namely the Ambidexterity cluster
        # This is a known location, which can then be used to calculate
        # our way to a desired position
        self.log.debug("Centering screen position")

        # Correct our tree position to a known value
        self._locate_screen_using_ambidexterity()

        # Find our way to the desired position
        self._move_to_tree_pos_using_spaces(desired_tree_pos)


    def _move_to_tree_pos_using_spaces(self, desired_tree_pos, max_position_error=5):
        dx = desired_tree_pos[0] - self.ingame_pos[0]
        dy = desired_tree_pos[1] - self.ingame_pos[1]
        self.log.debug("Moving to tree pos using spaces. Deltas: ({}, {})".format(dx, dy))
        while (abs(dx) + abs(dy)) > max_position_error:
            # Choose quadrant to find spaces in based on dx, dy
            right, bottom = dx >= 0, dy >= 0
            if right and not bottom:
                quadrant = 0
            elif not right and not bottom:
                quadrant = 1
            elif not right and bottom:
                quadrant = 2
            elif right and bottom:
                quadrant = 3

            # Find empty spaces that we can drag from
            spaces = self._find_empty_space(quadrant)
            if spaces is None:
                raise ValueError("Could not find an empty space, quitting.")

            # Choose a random empty space for maximum drag
            chosen_space = spaces[np.random.randint(spaces.shape[0])]

            # How far to drag the window to end up in the optimal place
            screen_move_x, screen_move_y = self._tree_pos_to_xy([dx, dy],
                                                                offset=True)

            # Calculate where our drag should end up to perform the move
            drag_x = chosen_space[0] - screen_move_x
            drag_y = chosen_space[1] - screen_move_y

            # We should only drag within the screen's resolution
            # Additionally, we use 100px margin to not trigger tree scroll
            drag_x = np.clip(drag_x, 100, self.resolution[0] - 100)
            drag_y = np.clip(drag_y, 100, self.resolution[1] - 100)

            # Drag
            self.input_handler.click(
                *chosen_space, *chosen_space, button=None, raw=True, speed_factor=1
            )
            self.input_handler.drag(drag_x, drag_y, speed_factor=1)
            self.input_handler.rnd_sleep(min=200, mean=300, sigma=100)

            # Calculate how far we've actually moved
            effective_move_x = chosen_space[0] - drag_x
            effective_move_y = chosen_space[1] - drag_y

            # Update our internal tree position
            self.ingame_pos = self._add_xy_offset_to_tree_pos(
                [effective_move_x, effective_move_y]
            )

            # Figure out how much we have left to move
            dx = desired_tree_pos[0] - self.ingame_pos[0]
            dy = desired_tree_pos[1] - self.ingame_pos[1]

    def _locate_screen_using_ambidexterity(self):
        # Essentially, this is _move_to_tree_pos_using_spaces but
        # only used to find the tree position by navigating to a known point
        self.log.debug("Moving to ambidexterity")
        ambidexterity_position = None
        assumed_ambidexterity_position = (0.25234375, 0.20555556)
        while ambidexterity_position is None:
            # Find empty spaces that we can drag from
            spaces = self._find_empty_space(3)
            if spaces is None:
                raise ValueError("Could not find an empty space, quitting.")

            # Choose the farthest empty space for maximum drag
            chosen_space = spaces[np.argmax(spaces.sum(axis=1))]

            # An arbitrary position in the top left region
            drag_location = (200, 200)

            # Drag
            self.input_handler.click(
                *chosen_space, *chosen_space, button=None, raw=True, speed_factor=1
            )
            self.input_handler.drag(drag_location[0], drag_location[1], speed_factor=1)
            self.input_handler.rnd_sleep(min=200, mean=300, sigma=100)

            # Are we there yet?
            # i.e., have we reached Ambidexterity, which in that case is at
            # roughly (646, 296) in absolute 1440p screen px position
            ambidexterity_position = self._find_icon(
                assumed_ambidexterity_position, "AmbidexterityCluster.png"
            )
        # Ambidexterity is located (-560, 850) from socket 21
        # Thus, this plus any (scaled) offset found by the template matcher is
        # our tree position
        self.ingame_pos = [
            SOCKETS[21][0]
            - 560
            + ambidexterity_position[0] / (X_SCALE * self.px_multiplier),
            SOCKETS[21][1]
            + 850
            + ambidexterity_position[1] / (Y_SCALE * self.px_multiplier),
        ]

    def _find_empty_space(self, quadrant):
        # Finds empty spaces that can be used to drag the screen
        # Used to recenter the screen
        # The quadrant argument is an int in [0, 1, 2, 3], corresponding to
        # [top-right, top-left, bottom-left, bottom-right]
        quadrant_translation = {0: [0.5, 0], 1: [0, 0], 2: [0, 0.5], 3: [0.5, 0.5]}
        fractional_lt = quadrant_translation[quadrant]
        lt = [
            int(fractional_lt[0] * self.resolution[0]),
            int(fractional_lt[1] * self.resolution[1]),
        ]
        rb = [int(lt[0] + self.resolution[0] / 2),
              int(lt[1] + self.resolution[1] / 2)]
        searched_area = grab_screen(tuple(lt + rb))
        searched_area = cv2.cvtColor(searched_area, cv2.COLOR_BGR2GRAY)

        locations = np.zeros_like(searched_area)

        centered_coordinates = self._match_image(searched_area, "FreeSpace.png")
        locations[tuple(centered_coordinates)] = 1

        rel_space_pos_yx = np.argwhere(locations == 1)
        rel_space_pos = rel_space_pos_yx.T[::-1].T
        if len(rel_space_pos) == 0:
            self.log.warning("Could not find any free spaces in tree!")
            return None
        screen_space_pos = rel_space_pos + lt

        # remove positions that are close to edges as these trigger scroll
        screen_space_pos = screen_space_pos[(screen_space_pos[:, 0] > 100) &
                            (screen_space_pos[:, 1] > 100) &
                            (screen_space_pos[:, 0] < self.resolution[0] - 100) &
                            (screen_space_pos[:, 1] < self.resolution[1] - 100)]
        return screen_space_pos

    def _find_icon(self, assumed_position, icon_name):
        # Finds the ambidexerity cluster icon in the region it sits in
        # if we are at the bottom-right corner of the tree
        # The exact location is used to refine our knowledge of our position
        abs_assumed_position = (
            assumed_position[0] * self.resolution[0],
            assumed_position[1] * self.resolution[1],
        )
        margin_side = int(0.05 * self.resolution[0])
        lt = [
            int(abs_assumed_position[0] - margin_side / 2),
            int(abs_assumed_position[1] - margin_side / 2),
        ]
        rb = [
            int(abs_assumed_position[0] + margin_side / 2),
            int(abs_assumed_position[1] + margin_side / 2),
        ]
        searched_area = grab_screen(tuple(lt + rb))
        searched_area = cv2.cvtColor(searched_area, cv2.COLOR_BGR2GRAY)
        locations = np.zeros((margin_side, margin_side))
        centered_coordinates = self._match_image(searched_area, icon_name)
        locations[tuple(centered_coordinates)] = 1
        rel_icon_pos_yx = np.argwhere(locations == 1)
        rel_icon_pos = rel_icon_pos_yx.T[::-1].T
        if len(rel_icon_pos) == 0:
            return None
        icon_offset = [
            int(rel_icon_pos[0][0] - margin_side / 2 + abs_assumed_position[0]),
            int(rel_icon_pos[0][1] - margin_side / 2 + abs_assumed_position[1]),
        ]
        return icon_offset

    def _click_socket(self, socket_pos, insert=True):
        self.log.debug("Clicking socket")
        xy = socket_pos
        lt = [xy[0] - 5 * self.px_multiplier, xy[1] - 5 * self.px_multiplier]
        rb = [xy[0] + 5 * self.px_multiplier, xy[1] + 5 * self.px_multiplier]
        if insert:
            self.input_handler.click(*lt, *rb, button="left", raw=True)
        else:
            self.input_handler.click(*lt, *rb, button="right", raw=True)
        self.input_handler.rnd_sleep(min=200, mean=300)

    def _tree_pos_to_xy(self, pos, offset=False):
        if offset:
            return [
                pos[0] * X_SCALE * self.px_multiplier,
                pos[1] * Y_SCALE * self.px_multiplier,
            ]
        uncentered_xy = [
            (pos[0] - self.ingame_pos[0]) * X_SCALE * self.px_multiplier,
            (pos[1] - self.ingame_pos[1]) * Y_SCALE * self.px_multiplier,
        ]
        xy = [
            int(uncentered_xy[0] + self.origin_pos[0]),
            int(uncentered_xy[1] + self.origin_pos[1]),
        ]
        return xy

    def _add_xy_offset_to_tree_pos(self, offset):
        tree_pos = [
            self.ingame_pos[0] + offset[0] / (X_SCALE * self.px_multiplier),
            self.ingame_pos[1] + offset[1] / (Y_SCALE * self.px_multiplier),
        ]
        return tree_pos

    def _analyze_nodes(self, socket_id):
        self.log.info("Analyzing nodes for socket id %s" % socket_id)
        nodes = []
        node_locations, socket_pos = self._find_nodes(socket_id)
        self.log.debug(
            "Found %s nodes for socket id %s" % (len(node_locations), socket_id)
        )
        self._click_socket(socket_pos)
        for location in node_locations:
            if not self._run():
                return
            node_stats = self._get_node_data(location)
            node = {
                "location": self._socket_offset_pos(socket_pos, location),
                "stats": node_stats,
            }
            nodes.append(node)
        self._click_socket(socket_pos, insert=False)
        return nodes

    def _socket_offset_pos(self, socket_pos, node_location):
        circle_radius = CIRCLE_EFFECTIVE_RADIUS * self.px_multiplier
        return [
            (node_location[0] - socket_pos[0]) / circle_radius,
            (node_location[1] - socket_pos[1]) / circle_radius,
        ]

    def _filter_ocr_lines(self, nodes_lines, max_dist=4):
        filtered_nodes = []
        for node in nodes_lines:
            names = []
            mods = []
            for line in node["stats"]:
                filtered_line = self._filter_nonalpha(line)
                if len(filtered_line) < 4 or filtered_line == "Unallocated":
                    continue
                if filtered_line in self.passive_names:
                    names.append(self.passive_names[filtered_line])
                elif filtered_line in self.passive_mods:
                    filtered_mod, value = filter_mod(line, regex=self.nonalpha_re)
                    new_mod = re.sub(
                        self.find_mod_value_re,
                        str(value),
                        self.passive_mods[filtered_line],
                        count=1,
                    )
                    mods.append(new_mod)
                else:
                    # Sometimes the OCR might return strange results. If so,
                    # as a last resort, check levenshtein distance to closest
                    # node. This shouldn't happen often.
                    best_distance = 99999999999
                    best_match = None
                    for possible_mod in self.passive_nodes:
                        d = distance(filtered_line, possible_mod)
                        if d < best_distance:
                            best_distance = d
                            best_match = possible_mod
                    if best_distance > max_dist:
                        continue
                    if best_match in self.passive_names:
                        names.append(self.passive_names[best_match])
                    elif best_match in self.passive_mods:
                        filtered_mod, value = filter_mod(line, regex=self.nonalpha_re)
                        new_mod = re.sub(
                            self.find_mod_value_re,
                            str(value),
                            self.passive_mods[best_match],
                            count=1,
                        )
                        mods.append(new_mod)

            if mods:
                filtered_nodes.append(
                    {"location": node["location"], "name": names, "mods": mods}
                )

        return filtered_nodes

    def _find_nodes(self, socket_id):
        self.input_handler.click(0.5, 0.07, 0.51, 0.083, button=None)
        socket_pos = self._tree_pos_to_xy(SOCKETS[socket_id])
        socket_offset = self._find_socket(socket_pos)
        if socket_offset is None:
            found_socket = False
            socket_offset = [0, 0]
        else:
            found_socket = True
            self.log.debug("Jewel socket offset correction: %s" % socket_offset)

        socket_pos[0] += socket_offset[0]
        socket_pos[1] += socket_offset[1]

        # Add some margin so that we dont accidentally cut any nodes off
        margin = 20 * self.px_multiplier

        x1 = int(socket_pos[0] - CIRCLE_EFFECTIVE_RADIUS * self.px_multiplier - margin)
        y1 = int(socket_pos[1] - CIRCLE_EFFECTIVE_RADIUS * self.px_multiplier - margin)
        x2 = int(x1 + 2 * CIRCLE_EFFECTIVE_RADIUS * self.px_multiplier + 2 * margin)
        y2 = int(y1 + 2 * CIRCLE_EFFECTIVE_RADIUS * self.px_multiplier + 2 * margin)

        nodes = self._get_node_locations_from_screen((x1, y1, x2, y2))
        nodes = self._filter_nodes(nodes, socket_pos)
        return nodes, socket_pos

    def _find_socket(self, socket_pos, side_len=100):
        lt = [int(socket_pos[0] - side_len / 2), int(socket_pos[1] - side_len / 2)]
        rb = [lt[0] + side_len, lt[1] + side_len]
        socket_area = grab_screen(tuple(lt + rb))
        socket_area = cv2.cvtColor(socket_area, cv2.COLOR_BGR2GRAY)

        locations = np.zeros((side_len, side_len))

        for template_name in [
            "Jewel.png",
            "JewelSocketed.png",
            "LargeJewel.png",
            "LargeJewelSocketed.png",
        ]:
            centered_coordinates = self._match_image(socket_area, template_name)
            locations[tuple(centered_coordinates)] = 1

        rel_node_pos_yx = np.argwhere(locations == 1)
        rel_node_pos = rel_node_pos_yx.T[::-1].T
        if len(rel_node_pos) == 0:
            self.log.warning("Could not find any jewel socket for compensating offset!")
            return None
        socket_offset = [
            int(rel_node_pos[0][0] - side_len / 2),
            int(rel_node_pos[0][1] - side_len / 2),
        ]
        return socket_offset

    def _filter_nodes(self, nodes, socket_pos, duplicate_min_dist=10):
        # filter duplicate nodes
        kept_node_indices = [len(nodes) - 1]
        z = np.array([[complex(c[0], c[1]) for c in nodes]])
        dist_matrix = abs(z.T - z)
        for node_idx in range(len(nodes) - 1):
            if np.min(dist_matrix[node_idx + 1 :, node_idx]) >= duplicate_min_dist:
                kept_node_indices.append(node_idx)
        nodes = np.array(nodes)
        nodes = nodes[kept_node_indices, :]

        # filter nodes outside jewel socket radius
        distances_to_socket = np.sqrt(np.sum((nodes - socket_pos) ** 2, axis=1))
        nodes = nodes[
            distances_to_socket <= CIRCLE_EFFECTIVE_RADIUS * self.px_multiplier
        ]
        return nodes

    def _get_node_locations_from_screen(self, box):
        jewel_area_bgr = grab_screen(box)
        jewel_area_gray = cv2.cvtColor(jewel_area_bgr, cv2.COLOR_BGR2GRAY)

        locations = np.zeros((box[2] - box[0], box[3] - box[1]))

        for template_name in [
            "Notable.png",
            "NotableAllocated.png",
            "Skill.png",
            "SkillAllocated.png",
        ]:
            centered_coordinates = self._match_image(jewel_area_gray, template_name)
            locations[tuple(centered_coordinates)] = 1

        rel_node_pos_yx = np.argwhere(locations == 1)
        rel_node_pos = rel_node_pos_yx.T[::-1].T
        abs_node_pos = rel_node_pos + [box[0], box[1]]
        return abs_node_pos

    def _match_image(self, screen, template_name):
        template = self.templates_and_masks[template_name]["image"]
        mask = self.templates_and_masks[template_name]["mask"]
        res = cv2.matchTemplate(screen, template, cv2.TM_CCORR_NORMED, mask=mask)
        coordinates = np.where(
            res >= TEMPLATES[template_name][self.resolution_prefix + "threshold"]
        )
        icon_size = (
            int(TEMPLATES[template_name][self.resolution_prefix + "size"][0]),
            int(TEMPLATES[template_name][self.resolution_prefix + "size"][1]),
        )
        icon_center_offset = [int(icon_size[0] / 2), int(icon_size[1] / 2)]
        centered_coordinates = [
            coordinates[0] + icon_center_offset[0],
            coordinates[1] + icon_center_offset[1],
        ]

        return centered_coordinates

    def _get_node_data(self, location):
        self.log.debug("Getting node stats at location %s" % location)
        lt = [
            location[0] - 7 * self.px_multiplier,
            location[1] - 7 * self.px_multiplier,
        ]
        rb = [
            location[0] + 7 * self.px_multiplier,
            location[1] + 7 * self.px_multiplier,
        ]
        self.input_handler.click(
            *lt,
            *rb,
            button=None,
            raw=True,
            speed_factor=self.config["node_search_speed_factor"]
        )
        textbox_lt = location + [TXT_BOX["x"], TXT_BOX["y"]]
        textbox_rb = textbox_lt + [
            int(TXT_BOX["w"] * self.px_multiplier),
            int(TXT_BOX["h"] * self.px_multiplier),
        ]

        jewel_area_bgr = grab_screen(tuple(np.concatenate([textbox_lt, textbox_rb])))
        return jewel_area_bgr

    def _setup(self, item_location, copy=False):
        item_desc = None
        item_name = None
        self.input_handler.click_hotkey("p")
        self.input_handler.rnd_sleep(min=150, mean=200, sigma=100)
        self.input_handler.click_hotkey("i")
        if copy:
            self.input_handler.rnd_sleep(min=150, mean=200, sigma=100)
            item = self.input_handler.inventory_copy(
                *item_location, OWN_INVENTORY_ORIGIN, speed_factor=2
            )
            item_desc = item.split("\n")[9].strip()
            item_name = item.split("\n")[1].strip()
        self.input_handler.rnd_sleep(min=150, mean=200, sigma=100)
        self.input_handler.inventory_click(*item_location, OWN_INVENTORY_ORIGIN)
        self.input_handler.rnd_sleep(min=150, mean=200, sigma=100)
        self.input_handler.click_hotkey("i")
        self.input_handler.rnd_sleep(min=150, mean=200, sigma=100)
        return item_name, item_desc

    def generate_good_strings(self, files):
        mods = {}
        names = {}
        for name in files:
            path = files[name]
            with open(path) as f:
                data = json.load(f)
                if isinstance(data, dict):
                    names.update({self._filter_nonalpha(k): k for k in data.keys()})
                    for key in data.keys():
                        if isinstance(data[key]["passives"][0], list):
                            mods.update(
                                {
                                    self._filter_nonalpha(e): e
                                    for e in data[key]["passives"][0]
                                }
                            )
                        else:
                            mods.update(
                                {
                                    self._filter_nonalpha(e): e
                                    for e in data[key]["passives"]
                                }
                            )
                else:
                    mods.update({self._filter_nonalpha(e): e for e in data})
        mods.pop("", None)
        return mods, names

    def _filter_nonalpha(self, value):
        return re.sub(self.nonalpha_re, "", value)


# Adapted from https://github.com/klayveR/python-poe-timeless-jewel
class OCR:
    @staticmethod
    def clahe(img, clip_limit=2.0, grid_size=(8, 8)):
        clahe = cv2.createCLAHE(clipLimit=clip_limit, tileGridSize=grid_size)
        return clahe.apply(img)

    @staticmethod
    def getFilteredImage(src):
        srcH, srcW = src.shape[:2]
        src = cv2.resize(src, (int(srcW * 2), int(srcH * 2)))

        # HSV thresholding to get rid of as much background as possible
        src = cv2.cvtColor(src, cv2.COLOR_BGRA2BGR)
        hsv = cv2.cvtColor(src.copy(), cv2.COLOR_BGR2HSV)
        # Define 2 masks and combine them
        # mask1 for blue affix text
        # mask2 for yellow passive node name
        lower_blue = np.array([80, 10, 40])
        upper_blue = np.array([130, 180, 255])
        lower_yellow = np.array([10, 10, 190])
        upper_yellow = np.array([30, 200, 255])
        mask1 = cv2.inRange(hsv, lower_blue, upper_blue)
        mask2 = cv2.inRange(hsv, lower_yellow, upper_yellow)
        mask = cv2.bitwise_or(mask1, mask2)
        result = cv2.bitwise_and(src, src, mask=mask)
        b, g, r = cv2.split(result)
        b = OCR.clahe(b, 5, (5, 5))
        inverse = cv2.bitwise_not(b)
        return inverse

    @staticmethod
    def imageToStringArray(img):
        t = pytesseract.image_to_string(img, lang="eng", config="--oem 3 --psm 12 poe")
        t = t.replace("\n\n", "\n")
        lines = t.split("\n")
        return lines

    @staticmethod
    def node_to_strings(node):
        img = node["stats"]
        filt_img = OCR.getFilteredImage(img)
        text = OCR.imageToStringArray(filt_img)
        return {"location": node["location"], "stats": text}
