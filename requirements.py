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

# API
install("fastapi[all]", "0.95.0")
install("uvicorn", "0.25.0")
install("jinja2", "3.1.2")

# Base de données
install("SQLAlchemy", "1.4.51")