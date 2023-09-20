import os
from . import file

# CONFIGURATION
if file.exist(f"{os.path.realpath(os.path.dirname(__file__))}/../config.json"):
    CONFIG = file.json_read('config.json')
    SECRET_KEY = CONFIG['api']['key']
    API_IP = CONFIG['api']['ip']
else:
    SECRET_KEY = 0
    API_IP = "127.0.0.1"


class bcolors:
	end = '\033[0m'
	black = '\033[30m'
	white = '\033[37m'
	red = '\033[31m'
	green = '\033[32m'
	yellow = '\033[33m'
	blue = '\033[34m'
	purple = '\033[35m'
	lightblue = '\033[36m'
