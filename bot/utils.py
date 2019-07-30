# Mouse movement
import yaml
import os
import time


def get_config(module_name):
    config_path = os.path.abspath('config.yml')
    config = yaml.load(open(config_path, 'r'))
    return config[module_name]
