import os, os.path
import random
import string
import time
import cherrypy
import re
import json

from Levenshtein import distance
from bson.json_util import dumps
from pymongo import MongoClient
from os import path, curdir

from .utils import get_config

FILTERED_PASSIVE_LIST = 'data/filt_nonfilt_passives.json'


class ModSearch(object):
    def __init__(self):
        self.config = get_config('mod_search_site')
        self.db = MongoClient(self.config['db_url'], 27017)[self.config['db_name']]
        self.mod_files = {
            "passives":  "data/passives.json",
            "passivesAlt": "data/passivesAlternatives.json",
            "passivesAdd": "data/passivesAdditions.json",
            "passivesVaalAdd": "data/passivesVaalAdditions.json",
        }
        self.digit_re = re.compile('[0-9]+')
        self.nondigit_re = re.compile('[^0-9]')
        self.nonalpha_re = re.compile('[^a-zA-Z]')
        self.find_mod_value_re = re.compile('[\-\d+\))|(\d+)]+')
        self.all_mods = json.load(open(FILTERED_PASSIVE_LIST, 'r'))

        cherrypy.server.socket_host = '0.0.0.0'


    @cherrypy.expose
    def index(self):
        return open('mod_search_site/index.html')

    @cherrypy.expose
    def search(self, search_terms):
        search_terms = json.loads(search_terms)
        print(search_terms)
        coll = self.db["jewels"]
        filtered_mod_data = [self._filter_mod(mod_data) for mod_data in search_terms.items()]
        candidate_mod_data = self._get_candidates(filtered_mod_data)

        query_mods = [{'$multiply': ['$summed_mods.%s' % data[0], float(data[2])]} for data in candidate_mod_data]
        projection = {'name': 1, 'description': 1, 'reported': 1, 'created': 1,
                      'socket_id': 1, 'socket_nodes': 1, 'socket_nodes': 1,
                      "sum": {"$sum": query_mods}}
        searched_mod_projection = {'searched_mods': {mod[1]: '$summed_mods.%s' % mod[0]
                                                     for mod in candidate_mod_data}}
        projection.update(searched_mod_projection)

        jewel_socket_instances = self.db['jewels'].aggregate(
            [{"$project": projection},
            {"$sort": {"sum":-1}}, {"$limit": self.config['jewels_per_search']}]
        )

        docs_to_return = []
        for jewel in jewel_socket_instances:
            searched_mods = []
            for mod in jewel['searched_mods'].keys():
                value = jewel['searched_mods'][mod]
                new_mod = re.sub(self.find_mod_value_re, str(value), mod)
                searched_mods.append(new_mod)
            jewel['searched_mods'] = searched_mods
            docs_to_return.append(jewel)

        return [dumps(docs_to_return)]

    def _filter_mod(self, term):
        filt_mod = re.sub(self.nonalpha_re, '', term[0]).lower()
        return (filt_mod, term[1])

    def _get_candidates(self, mods_data):
        candidates = []

        for mod_data in mods_data:
            mod_name, mod_weight = mod_data
            best_match = None
            best_distance = 99999999999
            for stored_mod in self.all_mods.keys():
                d = distance(mod_name, stored_mod)
                if d < best_distance:
                    best_distance = d
                    best_match = stored_mod
            candidates.append((best_match, self.all_mods[best_match], mod_weight))

        return candidates

cherrypy.quickstart(ModSearch(), "/", { "/static": {
                        "tools.staticfile.on": True,
                        "tools.staticfile.filename" : path.join(path.abspath(curdir), "mod_search_site/update.js")}})
