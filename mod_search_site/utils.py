import yaml
import os
import time


def get_config(module_name):
    config_path = os.path.abspath('config.yml')
    config = yaml.safe_load(open(config_path, 'r'))
    return config[module_name]
