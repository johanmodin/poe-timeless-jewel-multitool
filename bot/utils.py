import yaml
import os
import time
import re

def get_config(module_name):
    config_path = os.path.abspath('config.yml')
    config = yaml.load(open(config_path, 'r'))
    return config[module_name]

def filter_mod(m, regex):
    value = 1
    filt_mod = regex.sub('', str(m)).lower()
    potential_value = re.findall('\d+|$', m)[0]
    if len(potential_value) > 0:
        value = float(potential_value)
    return filt_mod, value
