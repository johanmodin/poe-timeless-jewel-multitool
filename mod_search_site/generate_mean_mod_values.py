from pymongo import MongoClient
from tqdm import tqdm
import json
import numpy as np

from .utils import get_config


def rebuild_json():
    config = get_config('mod_search_site')
    db = MongoClient(config['db_url'], 27017)[config['db_name']]
    all_mods = {}
    jewel_instances = db['jewels'].find({})

    for jewel in tqdm(jewel_instances):
        for mod in jewel['summed_mods']:
            if mod in all_mods:
                all_mods[mod].append(jewel['summed_mods'][mod])
            else:
                all_mods[mod] = [jewel['summed_mods'][mod]]

    mean_mods = {}
    for mod in all_mods:
        mean_mods[mod] = np.mean(all_mods[mod])

    json.dump(mean_mods, open('data/mean_mod_values.json', 'w'))
