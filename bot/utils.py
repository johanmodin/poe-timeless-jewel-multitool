# Mouse movement
import yaml
import os
import time


def get_config(module_name):
    config_path = os.path.abspath(os.path.join('..', 'config.yml'))
    config = yaml.load(config_path)
    return config[module_name]
