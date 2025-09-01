import os
from topazdevsdk import file

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
