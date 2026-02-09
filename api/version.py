_MAJOR = "2"
_MINOR = "0"
# On main and in a nightly release the patch should be one ahead of the last
# released build.
_PATCH = "1"
# This is mainly for nightly builds which have the suffix ".dev$DATE". See
# https://semver.org/#is-v123-a-semantic-version for the semantics.
_SUFFIX = ".20260209.1"

__version__ = f'{_MAJOR}.{_MINOR}.{_PATCH}'
__version_dev__ = f'{__version__}{_SUFFIX}'
__version_short__ = f'{_MAJOR}.{_MINOR}'