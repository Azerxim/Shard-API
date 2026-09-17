import json
import os

# La version vient du champ "version" de package.json (api/core/version.py -> ../..)
_PACKAGE_JSON = os.path.join(os.path.dirname(__file__), "..", "..", "package.json")

try:
    with open(_PACKAGE_JSON, encoding="utf-8") as file:
        _PACKAGE_VERSION = str(json.load(file).get("version") or "0.0.0")
except (OSError, ValueError):
    _PACKAGE_VERSION = "0.0.0"

_MAJOR, _MINOR = (_PACKAGE_VERSION.split("-")[0].split(".") + ["0", "0"])[:2]
# This is mainly for nightly builds which have the suffix ".dev$DATE". See
# https://semver.org/#is-v123-a-semantic-version for the semantics.
_SUFFIX = ""

__version__ = _PACKAGE_VERSION
__version_dev__ = f'{__version__}{_SUFFIX}'
__version_short__ = f'{_MAJOR}.{_MINOR}'
