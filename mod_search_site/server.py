import cherrypy
import json
import math
import os, os.path
import random
import re
import string
import time

from bson.json_util import dumps
from fuzzywuzzy import fuzz
from pymongo import MongoClient
from os import path, curdir

from .utils import get_config, rebuild_mean_mod_json

FILTERED_PASSIVE_LIST = 'data/filt_nonfilt_passives.json'
MEAN_MOD_LIST = 'data/mean_mod_values.json'


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
        self.find_mod_value_re = re.compile('(?:\-|\+)?((?:\(\d+-\d+\))|(?:[0-9]*\.?[0-9]))')
        self.all_mods = json.load(open(FILTERED_PASSIVE_LIST, 'r'))
        self.mean_mod_values = json.load(open(MEAN_MOD_LIST, 'r'))

        cherrypy.server.socket_host = 'localhost'


    @cherrypy.expose
    def index(self):
        return open('mod_search_site/index.html')


    @cherrypy.expose
    def search(self, search_terms):
        search_terms = json.loads(search_terms)
        coll = self.db["jewels"]
        filtered_mod_data = [self._filter_mod(mod_data) for mod_data in search_terms.items() if len(self._filter_mod(mod_data)) > 0]
        candidate_mod_data = self._get_candidates(filtered_mod_data)

        query_mods = [{'$multiply': ['$summed_mods.%s' % data[0], float(data[2])]} for data in candidate_mod_data]
        projection = {'name': 1, 'description': 1, 'reporter': 1, 'created': 1,
                      'socket_id': 1, 'socket_nodes': 1, 'socket_nodes': 1,
                      "sum": {"$sum": query_mods}}
        searched_mod_projection = {'searched_mods': {self._replace_value(mod[1]): '$summed_mods.%s' % mod[0]
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
                new_mod = re.sub('<VALUE>', str(value), mod, count=1)
                searched_mods.append(new_mod)
            jewel['searched_mods'] = searched_mods
            docs_to_return.append(jewel)

        return [dumps(docs_to_return)]


    @cherrypy.expose
    def show_latest_jewels(self):
        jewel_socket_instances = self.db['jewels'].find().sort([('created', -1)]).limit(self.config['jewels_per_search']);
        docs_to_return = []
        for jewel in jewel_socket_instances:
            summed_mods = jewel['summed_mods'].items()
            for mod in summed_mods:
                if mod[0] not in self.mean_mod_values:
                    self._rebuild_mean_mod_json()
                    break

            # Select mods that are deviating the most from the mean of that mod
            # which should be some form of metric for how interesting the jewel is
            notable_mods = sorted(jewel['summed_mods'].items(),
                                  key=lambda v: -1 * v[1] / self.mean_mod_values[v[0]])
            top_mods = notable_mods[:self.config['n_notable_mods_to_display']]
            mods_with_name = self._get_candidates([(m[0], 1) for m in top_mods])
            jewel['searched_mods'] = []
            jewel['sum'] = 0
            for mod_data in mods_with_name:
                actual_name = mod_data[1]
                actual_name = self._replace_value(actual_name)
                value = round(jewel['summed_mods'][mod_data[0]], 3)
                jewel['sum'] += value
                display_mod = re.sub('<VALUE>', str(value), actual_name, count=1)
                jewel['searched_mods'].append(display_mod)

            docs_to_return.append(jewel)

        return [dumps(docs_to_return)]


    def _rebuild_mean_mod_json(self):
        print('Unknown mod found in database, rebuilding mean mod json!')
        rebuild_mean_mod_json(self.db)
        self.mean_mod_values = json.load(open(MEAN_MOD_LIST, 'r'))


    def _replace_value(self, mod):
        # We replace the value of the mods that are used in the mongo
        # query as they may otherwise cause errors due to being interpreted
        # as commands
        return re.sub(self.find_mod_value_re, '<VALUE>', mod)


    def _filter_mod(self, term):
        filt_mod = re.sub(self.nonalpha_re, '', term[0]).lower()
        return (filt_mod, term[1])


    def _get_candidates(self, mods_data):
        candidates = []
        for mod_data in mods_data:
            mod_name, mod_weight = mod_data
            best_match = None
            best_score = -math.inf
            for stored_mod in self.all_mods.keys():
                score = self._mod_score(mod_name, stored_mod)
                if score > best_score:
                    best_score = score
                    best_match = stored_mod
            candidates.append((best_match, self.all_mods[best_match], mod_weight))
        return candidates

    def _mod_score(self, mod_name, stored_mod):
        if mod_name not in stored_mod:
            # If there is no exact match, we can probably get something
            # decent with fuzzy matching. As exact matches are preferred,
            # the raw ratio is returned as the score of this method
            # which is in the [0, 1] range
            return fuzz.WRatio(mod_name, stored_mod) / 100
        else:
            # The exact match is always preferred
            # so we place it in the [1, 2] score range
            # with fewer additional characters being promoted
            return 1 + len(mod_name) / (len(stored_mod) + 1)


cherrypy.quickstart(ModSearch(), "/", { "/static": {
                        "tools.staticfile.on": True,
                        "tools.staticfile.filename" : path.join(path.abspath(curdir),
                        "mod_search_site/update.js")}})
