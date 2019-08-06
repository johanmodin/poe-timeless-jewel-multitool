import os, os.path
import random
import string
import time
from bson.json_util import dumps
import re
from Levenshtein import distance

from pymongo import MongoClient
from os import path, curdir

import cherrypy

class StringGenerator(object):
    db = MongoClient("localhost", 27017)["project_timeless_test4"]
    mod_files = {
        "passives":  "data/passives.json",
        "passivesAlt": "data/passivesAlternatives.json",
        "passivesAdd": "data/passivesAdditions.json",
        "passivesVaalAdd": "data/passivesVaalAdditions.json",
    }

    def generate_good_strings(self, files):
        mods = set()
        for name in files:
            path = files[name]
            with open(path) as f:
                data = json.load(f)
                if isinstance(data, dict):
                    names.update([self._filter_nonalpha(k) for k in data.keys()])
                    for key in data.keys():
                        if isinstance(data[key]['passives'][0], list):
                            mods.update([self._filter_nonalpha(e) for e in data[key]['passives'][0]])
                        else:
                            mods.update([self._filter_nonalpha(e) for e in data[key]['passives']])
                else:
                    mods.update([self._filter_nonalpha(e) for e in data])
        mods.remove('')
        return mods, names

    @cherrypy.expose
    def index(self):
        return open('index.html')

    @cherrypy.expose
    def search(self, search_term=None):
        coll = self.db["jewels"]
        jewel_socket_instances = self.db['jewels'].find(
            { "$text": { "$search": "\"" + search_term + "\""} },
            {"score": {"$meta": "textScore"} } ).limit(500).sort(
            [("score", {"$meta": "textScore"})])
        digit_re = re.compile('[0-9]+')
        nondigit_re = re.compile('[^0-9]')
        nonalpha_re = re.compile('[^a-zA-Z]')
        docs_to_return = []
        filtered_term = re.sub(nonalpha_re, '', search_term).lower()
        for jewel in jewel_socket_instances:
            potential_mods = {}
            for node in jewel['socket_nodes']:
                for mod in node['mods']:
                    filtered_mod = re.sub(nonalpha_re, '', mod).lower()
                    if filtered_term in filtered_mod:
                        mod_digits = re.sub(nondigit_re, '', mod)
                        if len(mod_digits) > 0:
                            mod_value = int(mod_digits)
                        else:
                            mod_value = 0
                        if filtered_mod in potential_mods:
                            potential_mods[filtered_mod]['sum'] += mod_value
                        else:
                            potential_mods[filtered_mod] = {'sum': mod_value,
                                                            'mod_name': mod}
            if len(potential_mods) > 0:
                sorted_mods = sorted(potential_mods.items(), key=lambda x:
                                     distance(x[1]['mod_name'], search_term))
                jewel['focused_mod'] = re.sub(digit_re, str(sorted_mods[0][1]['sum']),
                                              sorted_mods[0][1]['mod_name'])
            else:
                jewel['focused_mod'] = 'Unknown mod'
            jewel['edit_dist'] = distance(re.sub(nonalpha_re, '', jewel['focused_mod']).lower(),
                                          filtered_term)
            jewel['mod_score'] = sorted_mods[0][1]['sum']
            docs_to_return.append(jewel)
        docs_to_return.sort(key=lambda j: (j['edit_dist'], j['mod_score'] * -1))
        return [dumps(docs_to_return)]



cherrypy.quickstart(StringGenerator(), "/", { "/static": {
                        "tools.staticfile.on": True,
                        "tools.staticfile.filename" : path.join(path.abspath(curdir), "update.js")}})
