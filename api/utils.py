import os, socket
from topazdevsdk import file
from .version import __version__, __version_dev__, __version_short__

# CONFIGURATION
path = f"{os.path.realpath(os.path.dirname(__file__))}/../config.json"
path_template = f"{os.path.realpath(os.path.dirname(__file__))}/../config.json.template"

HOSTNAME = socket.gethostname()
VERSION = __version__
VERSION_DEV = __version_dev__
VERSION_SHORT = __version_short__

if not file.exist(path):
	file.create(path)
	if file.exist(path_template):
		data = file.json_read(path_template)
	else:
		data = {}
	file.json_write(path, data)

if file.exist(path):
	CONFIG = file.json_read(path)
	SECURITY = CONFIG['security']
	DATABASE = CONFIG['database']
	API_IP = CONFIG['api']['ip']
	API_PORT = CONFIG['api']['port']
	OAUTH2 = CONFIG.get('oauth2', {})
	CLIENT_ID = OAUTH2.get('client_id', '')
	CLIENT_SECRET = OAUTH2.get('client_secret', '')
	PLATFORMS = CONFIG.get('platforms', {"local": {"name": "local", "key": "local"}})
else:
	DATABASE = {"name": "database", "debug": True}
	PLATFORMS = {}
	API_IP = "127.0.0.1"
	API_PORT = 8000
	SECURITY = {}
	CONFIG = {}
	OAUTH2 = {}
	CLIENT_ID = ''
	CLIENT_SECRET = ''
