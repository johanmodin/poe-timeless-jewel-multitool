import logging
import cv2
import numpy as np
import pytesseract
import os
import time
import json
import re
import pickle

from PIL import Image

#two kinds of coordinates: 
#absolute tree coordinates, which match the json perfectly. these are prefixed by tree_ (origin center of scion)
#screen coordinates, which describe where on the screen things are (origin top left pixel on screen)

from multiprocessing import Pool
from Levenshtein import distance

from .input_handler import InputHandler
from .grabscreen import grab_screen
from .utils import get_config, filter_mod

# This is a position of the inventory as fraction of the resolution
OWN_INVENTORY_ORIGIN = (0.6769531, 0.567361)

# This is the ratio for 1080p. We have to generalize for others, and tie it to the resolution specification in config. For now though.
t2s_scale = 1080/10000.0

#passive tree bounds on where the center can move (in 1080p pixels)
#used to figure out where we are.
TREE_BOUND_Y = [-1003,1000]
TREE_BOUND_X = [-595,595]

#pull node information from the processed tree
f=open("data/processed_tree.pckl", 'rb')
node_coords=pickle.load(f)
neighbor_nodes=pickle.load(f)

SOCKET_IDS = [6230 , 48768 , 31683 , 
28475, 33631 , 36634 , 41263 , 33989 , 34483 , 
54127, 2491 , 26725 , 55190 , 26196 , 7960 , 61419 , 21984 , 61834 , 32763 , 60735 , 46882]

IMAGE_FOLDER = "data/images/"

# We're using a lot of template matching and all templates are defined here
# with matching thresholds (scores) and sizes per resolution
# the 1440p values can be all sorts of wrong.
TEMPLATES = {
    "FreeSpace.png": {
        "1440p_size": (41, 41),
        "1440p_threshold": 0.98,
        "1080p_size": (30, 30),
        "1080p_threshold": 0.98,
    },
}
for ID in SOCKET_IDS:
    TEMPLATES[str(ID)+".png"] = {
        "1440p_size": (34, 34),
        "1440p_threshold": 0.95,
        "1080p_size": (29, 29),
        "1080p_threshold": 0.95,
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
        self.camera_position = (0,0)
        self.px_multiplier = 1
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
        self.camera_position = (0,0)
        item_name, item_desc = self._setup(item_location, copy=True)

        pool = Pool(self.config["ocr_threads"])
        jobs = {}

#move all the way bottom right, establish where we are.
        self._locate_screen(3)
#analyse nodes
        for socket_id in SOCKET_IDS:
            self._move_screen_to_node(socket_id)
            socket_nodes = self._analyze_nodes(socket_id)
#            # Convert stats for the socket from image to lines in separate process
#            self.log.info("Performing asynchronous OCR")
            jobs[socket_id] = pool.map_async(OCR.node_to_strings, socket_nodes)
#            self.log.info("Analyzed socket %s" % socket_id)
            if not self._run():
                return None, None, None

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

    def _tree_to_screen(self, tree_coords):
        self.log.debug("screen_coords: ({}, {})".format( self.camera_position[0], self.camera_position[1] ) )
        screen_coords=(int(tree_coords[0]*t2s_scale),int(tree_coords[1]*t2s_scale))
        cam_relative_coords=(screen_coords[0]-self.camera_position[0],
                             screen_coords[1]-self.camera_position[1])
        cam_absolute_coords=(int(self.resolution[0]/2)+cam_relative_coords[0],int(self.resolution[1]/2)+cam_relative_coords[1])
        #don't return garbage coords. Maybe this is wrong?
        if cam_absolute_coords[0]<0 or cam_absolute_coords[0]>self.resolution[0] or cam_absolute_coords[1]<0 or cam_absolute_coords[1]>self.resolution[1]:
            self.log.info("Tried to get offscreen coords!")
            return None
        return cam_absolute_coords

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
                # mask = cv2.resize(mask, size)

            img = cv2.imread(template_path, 0)
            # img = cv2.resize(img, size)
            templates_and_masks[template_name] = {"image": img, "mask": mask}
        return templates_and_masks

    def _move_screen_to_node(self, node_id):

        self.log.debug("Moving to node %s" % node_id)

        self._move_to_tree_pos_using_spaces(node_coords[node_id])

        return True

    def _move_to_tree_pos_using_spaces(self, tree_desired_pos, max_position_error=2):

        target = (int(tree_desired_pos[0]*t2s_scale),int(tree_desired_pos[1]*t2s_scale))
#we only check the x bound, since all nodes are in bounds in the y direction
        if target[0]<TREE_BOUND_X[0]+50:
            target= (TREE_BOUND_X[0]+50, target[1])
        if target[0]>TREE_BOUND_X[1]-50:
            target= (TREE_BOUND_X[1]-50, target[1])

        dx = target[0] - self.camera_position[0]
        dy = target[1] - self.camera_position[1]
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

            # Choose an empty space for random drag
            chosen_space = spaces

            # How far to drag the window to end up in the optimal place
            screen_move_x, screen_move_y = [dx, dy]

            # Calculate where our drag should end up to perform the move
            drag_x = int(chosen_space[0]) - screen_move_x
            drag_y = int(chosen_space[1]) - screen_move_y

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
            self.camera_position = [self.camera_position[0]+effective_move_x, self.camera_position[1]+effective_move_y]

            # Update how much we have left to move
            dx = target[0] - self.camera_position[0]
            dy = target[1] - self.camera_position[1]

    def _locate_screen(self, quadrent):
        #Since the bounding box is nicely alligned for 1080, we use that if we go all the way one way, we get stuck
        self.log.info("Moving to corner %d" % quadrent)
        q_signs = {0: (1,-1), 1: (-1,-1) , 2: (-1,1) , 3: (1,1)}
        q_indicator = {0: (0,1), 1: (1,1) , 2: (1,0) , 3: (0,0)}
        for repetition_counter in range(3):
            # Find empty spaces that we can drag from
            spaces = self._find_empty_space(quadrent)
            if spaces is None:
                raise ValueError("Could not find an empty space, quitting.")

            # Choose the farthest empty space for maximum drag
            chosen_space = spaces

            # An arbitrary position in the opposite corner region
            drag_location = (self.resolution[0]*q_indicator[quadrent][0]+200*(q_signs[quadrent][0]),
                             self.resolution[1]*q_indicator[quadrent][1]+200*(q_signs[quadrent][1]),)

            # Drag
            self.input_handler.click(
                *chosen_space, *chosen_space, button=None, raw=True, speed_factor=1
            )
            self.input_handler.drag(drag_location[0], drag_location[1], speed_factor=1)
            self.input_handler.rnd_sleep(min=200, mean=300, sigma=100)

        # Having gotten all the way across the tree, we set our location to the bounded location
        # to allign with the _center_ of nodes, rather than the top left corner, make it off by 5 pixels
        self.camera_position=(TREE_BOUND_X[q_signs[quadrent][0]+q_indicator[quadrent][0]],
                              TREE_BOUND_Y[q_signs[quadrent][1]+q_indicator[quadrent][1]])

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

        # remove positions that are close to edges as these trigger scroll or are coverd by UI
        screen_space_pos = screen_space_pos[(screen_space_pos[:, 0] > 200) &
                            (screen_space_pos[:, 1] > 200) &
                            (screen_space_pos[:, 0] < self.resolution[0] - 200) &
                            (screen_space_pos[:, 1] < self.resolution[1] - 200)]
        # find the best choice based on quadrant
        quadrant_directions = {0 : [1,-1], 1: [-1,-1], 2: [-1,1], 3: [1,1]}
        best_value=-1000000
        saved_coords=[0,0]
        for coord in screen_space_pos:
            try_value=quadrant_directions[quadrant][0]*coord[0] + quadrant_directions[quadrant][1]*coord[1]
            if try_value>best_value:
                best_value=try_value
                saved_coords=coord
        return saved_coords


    def _click_socket(self, tree_socket_pos, offset, insert=True):
        self.log.debug("Clicking socket")
        xy = self._tree_to_screen(tree_socket_pos)
        lt = [xy[0]+offset[0] - 1, xy[1]+offset[1] - 1]
        rb = [xy[0]+offset[0] + 1, xy[1]+offset[1] + 1]
        if insert:
            self.input_handler.click(*lt, *rb, button="left", raw=True)
        else:
            self.input_handler.click(*lt, *rb, button="right", raw=True)
        self.input_handler.rnd_sleep(min=200, mean=300)


    def _analyze_nodes(self, socket_id, repeated=False):
        self.log.info("Analyzing nodes for socket id %s" % socket_id)
        node_ids = neighbor_nodes[socket_id]
        tree_socket_pos=node_coords[socket_id]

#check the zone around where the socket is
        thought_middle=self._tree_to_screen(tree_socket_pos)
        lt=[thought_middle[0]-30,thought_middle[1]-30]
        rb=[thought_middle[0]+30,thought_middle[1]+30]
        searched_area = grab_screen(tuple(lt + rb))
        searched_area = cv2.cvtColor(searched_area, cv2.COLOR_BGR2GRAY)
#match it to the saved image of that socket
        locations = np.zeros_like(searched_area)

        centered_coordinates=self._match_image(searched_area,str(socket_id)+".png")
        locations[tuple(centered_coordinates)] = 1

        rel_space_pos_yx = np.argwhere(locations == 1)
        rel_space_pos = rel_space_pos_yx.T[::-1].T
        if len(rel_space_pos) == 0:
            if repeated==True:
                self.log.warning("Could not find the socket! Giving up.")
                return []
            self.log.warning("Could not find the socket! Trying again.")
            self._locate_screen(3)
            self._move_screen_to_node(socket_id)
            return self._analyze_nodes(socket_id,repeated=True)
        first_rel_space_pos=rel_space_pos[0]
        offset= (first_rel_space_pos[0]-30, first_rel_space_pos[1]-30)
        self.log.info("offset: ({}, {})".format( offset[0], offset[1] ) )

        nodes =[]
        self._click_socket(tree_socket_pos,offset)

#        new_path=str(socket_id)+'/'
#        if not os.path.exists(os.path.join(IMAGE_FOLDER, new_path)):
#            os.makedirs(os.path.join(IMAGE_FOLDER, new_path))
        for node_id in node_ids:
            if not self._run():
                return
            node_stats = self._get_node_data(node_id,offset)
#REMOVE LATER
#            file_name=str(socket_id)+'/'+str(node_id)+'.png'
#            save_path = os.path.join(IMAGE_FOLDER, file_name)
#            img= Image.fromarray(node_stats)
#            img.save(save_path)
#REMOVE
            #self.log.info("node: %s" % node_id)
            node = {
                "id": node_id,
                "stats": node_stats,
            }
            nodes.append(node)
        self._click_socket(tree_socket_pos,offset, insert=False)
        return nodes


    def _match_image(self, screen, template_name):
        template = self.templates_and_masks[template_name]["image"]
        mask = self.templates_and_masks[template_name]["mask"]
        res = cv2.matchTemplate(screen, template, cv2.TM_CCORR_NORMED, mask=mask)
        coordinates = np.where(
            res >= TEMPLATES[template_name][self.resolution_prefix + "threshold"]
        )
        #self.log.info(coordinates)
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


    def _get_node_data(self, node_id,offset):
        self.log.debug("Getting node stats for node %s" % node_id)
        location = self._tree_to_screen(node_coords[node_id])
        location=(int(location[0])+offset[0],int(location[1])+offset[1])
        lt = [
            location[0] - 1,
            location[1] - 1,
        ]
        rb = [
            location[0] + 1,
            location[1] + 1,
        ]
        self.input_handler.click(
            *lt,
            *rb,
            button=None,
            raw=True,
            speed_factor=self.config["node_search_speed_factor"]
        )
        textbox_lt = [location[0] + TXT_BOX["x"], location[1] + TXT_BOX["y"]]
        textbox_rb = [textbox_lt[0] + int(TXT_BOX["w"]),
                      textbox_lt[1] + int(TXT_BOX["h"]),
        ]

        jewel_area_bgr = grab_screen(tuple(np.concatenate([textbox_lt, textbox_rb])))
        return jewel_area_bgr

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
                    {"id": node["id"], "name": names, "mods": mods}
                )

        return filtered_nodes


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
        return {"id": node["id"], "stats": text}
