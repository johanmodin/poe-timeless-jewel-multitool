import os, os.path
import random
import sqlite3
import string
import time
from bson.json_util import dumps
import re

from pymongo import MongoClient
from os import path, curdir

import cherrypy

class StringGenerator(object):
    db = MongoClient("localhost", 27017)["project_timeless_test4"]

    @cherrypy.expose
    def index(self):
        return open('index.html')

    @cherrypy.expose
    def search(self, search_term=None):
        coll = self.db["jewels"]
        jewel_socket_instances = self.db['jewels'].find( { "$text": { "$search": "\"" + search_term + "\""} }, {"score": {"$meta": "textScore"} } ).limit(50).sort([("score", {"$meta": "textScore"})])
        digit_re = re.compile('[0-9]+')
        nondigit_re = re.compile('[^0-9]')
        nonalpha_re = re.compile('[^a-zA-Z]')
        docs_to_return = []
        for jewel in jewel_socket_instances:
            chosen_mod = None
            stripped_mod = None
            sum = 0
            for node in jewel['socket_nodes']:
                for mod in node['mods']:
                    if chosen_mod:
                        if stripped_mod == re.sub(nonalpha_re,'', mod):
                            mod_value = int(re.sub(nondigit_re,'', mod))
                            sum += mod_value
                    elif re.sub(nonalpha_re, '', search_term).lower() in re.sub(nonalpha_re, '', mod).lower():
                        chosen_mod = mod
                        stripped_mod = re.sub(nonalpha_re, '', chosen_mod)
                        mod_value = int(re.sub(nondigit_re,'', mod))
                        sum += mod_value
            if chosen_mod:
                jewel['focused_mod'] = re.sub(digit_re, str(sum), chosen_mod)
            else:
                jewel['focused_mod'] = 'Unknown mod'
            jewel['mod_score'] = sum
            docs_to_return.append(jewel)
        docs_to_return.sort(key=lambda j: j['mod_score'] * -1)
        return [dumps(docs_to_return)]



cherrypy.quickstart(StringGenerator(), "/", { "/static": {
                        "tools.staticfile.on": True,
                        "tools.staticfile.filename" : path.join(path.abspath(curdir), "realtime.js")}})
