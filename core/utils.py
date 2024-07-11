import os
from . import file

# CONFIGURATION
path = f"{os.path.realpath(os.path.dirname(__file__))}/../config.json"
path_template = f"{os.path.realpath(os.path.dirname(__file__))}/../config.json.template"

if not file.exist(path):
	file.create(path)
	if file.exist(path_template):
		data = file.json_read(path_template)
	else:
		data = {}
	file.json_write(path, data)

if file.exist(f"{os.path.realpath(os.path.dirname(__file__))}/../config.json"):
	CONFIG = file.json_read('config.json')
	SECURITY = CONFIG['security']
	DATABASE = CONFIG['database']
	API_IP = CONFIG['api']['ip']
	DISCORD_ID = CONFIG['platform']['discord']['id']
	DISCORD_SECRET = CONFIG['platform']['discord']['secret']
	DISCORD_REDIRECT = CONFIG['platform']['discord']['redirect']
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
