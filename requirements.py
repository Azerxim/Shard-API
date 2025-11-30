import subprocess
import sys


def install(package, version = None):
    if version == None or version == "":
        pv = package
    else:
        pv = "{p}=={v}".format(p=package, v=version)
    subprocess.call([sys.executable, "-m", "pip", "install", "-U", pv])


# Base
install("pip")
install("requests")
install("topazdevsdk")

# API
install("fastapi[all]", "0.111.0")
install("uvicorn", "0.29.0")
install("jinja2", "3.1.3")
install("pyjwt", "2.8.0")

# Base de données
install("SQLAlchemy", "1.4.52")

# OAuth2
install("starlette-discord", "0.2.1")

# Discord
install("discord.py", "2.3.2")