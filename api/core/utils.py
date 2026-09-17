import os, socket
from topazdevsdk import file
from .version import __version__, __version_dev__, __version_short__

# CONFIGURATION
# Racine du projet Shard-API (api/core/utils.py -> ../..)
ROOT_DIR = os.path.realpath(os.path.join(os.path.dirname(__file__), "..", ".."))
path = f"{ROOT_DIR}/config.json"
path_template = f"{ROOT_DIR}/config.json.template"
# Surcharge chargée par-dessus config.json quand API_ENV=development (npm run dev / verbose)
path_development = f"{ROOT_DIR}/config.development.json"

HOSTNAME = socket.gethostname()
VERSION = __version__
VERSION_DEV = __version_dev__
VERSION_SHORT = __version_short__
ENVIRONMENT = "development" if os.environ.get("API_ENV", "").strip().lower() == "development" else "production"

def deep_merge(base, override):
	# Les objets sont fusionnés récursivement, les autres valeurs de la surcharge remplacent celles de base
	merged = dict(base)
	for key, value in override.items():
		if isinstance(value, dict) and isinstance(merged.get(key), dict):
			merged[key] = deep_merge(merged[key], value)
		else:
			merged[key] = value
	return merged

if not file.exist(path):
	file.create(path)
	if file.exist(path_template):
		data = file.json_read(path_template)
	else:
		data = {}
	file.json_write(path, data)

CONFIG_FILES = []
if file.exist(path):
	CONFIG = file.json_read(path)
	CONFIG_FILES.append("config.json")
	if ENVIRONMENT == "development" and file.exist(path_development):
		CONFIG = deep_merge(CONFIG, file.json_read(path_development))
		CONFIG_FILES.append("config.development.json")
	SECURITY = CONFIG['security']
	DATABASE = CONFIG['database']
	# En développement, l'IP et le port viennent toujours de api.development
	API_MODE = "development" if ENVIRONMENT == "development" else CONFIG['api']['mode']
	API_IP = CONFIG['api'][API_MODE]['ip']
	API_PORT = CONFIG['api'][API_MODE]['port']
	OAUTH2 = CONFIG.get('oauth2', {})
	CLIENT_ID = OAUTH2.get('client_id', '')
	CLIENT_SECRET = OAUTH2.get('client_secret', '')
	PLATFORMS = CONFIG.get('platforms', {"local": {"name": "local", "key": "local"}})
else:
	DATABASE = {"name": "database", "debug": True}
	PLATFORMS = {}
	API_MODE = ENVIRONMENT
	API_IP = "127.0.0.1"
	API_PORT = 8000
	SECURITY = {}
	CONFIG = {}
	OAUTH2 = {}
	CLIENT_ID = ''
	CLIENT_SECRET = ''
