"""Fake Kodi modules.

The ``xbmc*`` modules only exist inside a running Kodi. ``tests/conftest.py``
injects the module objects built here into ``sys.modules`` *before* importing
``lib.utils``, which reads several of them at import time.

Two deliberate design choices:

* ``listdir`` returns names in the order they were registered, never sorted.
  ``walk()``'s output order depends on the order the VFS backend hands back
  subdirectories, so sorting here would hide ordering regressions.
* The addon profile directory is a real temp directory, so ``xbmcvfs.File``,
  ``mkdir`` and ``delete`` operate on real files. ``create_cache()`` writes
  actual JSON, which keeps the cache tests honest.
"""

import json
import os
import random
import tempfile
import time
import types

# Real directory backing 'special://profile/'. Created once per test session;
# lib.utils resolves CACHEFOLDER and ASFILE from it at import time.
PROFILE_DIR = tempfile.mkdtemp(prefix='kodi-profile-')


def _as_folder(path):
    """Folder keys always carry a trailing slash.

    walk() recurses with os.path.join(folder, item, '') but the caller's
    top-level path may or may not end in one.
    """
    return path if path.endswith('/') else path + '/'


class Tree:
    """In-memory directory tree behind the fake xbmcvfs."""

    def __init__(self):
        self.folders = {}
        self.listdir_calls = []
        self.exists_calls = []

    def add(self, path, dirs=(), files=()):
        """Register a folder. Order of `dirs` and `files` is preserved."""
        self.folders[_as_folder(path)] = (list(dirs), list(files))
        return self

    def has(self, path):
        return _as_folder(path) in self.folders

    def listdir(self, path):
        dirs, files = self.folders[_as_folder(path)]
        return list(dirs), list(files)


class State:
    """Everything a test may want to vary, reset between tests."""

    def __init__(self):
        self.tree = Tree()
        self.settings = {'recursive': True}
        # conditions that getCondVisibility() should answer True for
        self.conditions = set()
        # JSON-RPC method name -> response dict
        self.jsonrpc = {}
        self.log_lines = []
        # seconds; when set, listdir sleeps a jittered amount up to this
        self.listdir_delay = 0
        self.addon_info = {'id': 'screensaver.picture.slideshow',
                           'profile': 'special://profile/addon_data/screensaver.picture.slideshow/',
                           'path': '/fake/addon/path',
                           'version': '7.0.6'}


state = State()


def reset():
    global state
    state = State()


# --------------------------------------------------------------------------
# xbmcvfs
# --------------------------------------------------------------------------

def _translate_path(path):
    if path.startswith('special://profile/'):
        return os.path.join(PROFILE_DIR, path[len('special://profile/'):])
    if path.startswith('special://'):
        return os.path.join(PROFILE_DIR, path[len('special://'):])
    return path


def _exists(path):
    state.tree.exists_calls.append(path)
    if state.tree.has(path):
        return True
    # Paths outside the fake tree (advancedsettings.xml, the cache dir) are
    # real files on disk -- get_excludes() parses ASFILE with stdlib etree,
    # which the VFS fakes cannot intercept.
    return os.path.exists(path)


def _listdir(path):
    if state.listdir_delay:
        # jittered, so a threaded walk finishes directories out of order --
        # the only way an order-preservation bug shows up in a test
        time.sleep(random.uniform(0, state.listdir_delay))
    state.tree.listdir_calls.append(path)
    if state.tree.has(path):
        return state.tree.listdir(path)
    if os.path.isdir(path):
        dirs, files = [], []
        for name in sorted(os.listdir(path)):
            (dirs if os.path.isdir(os.path.join(path, name)) else files).append(name)
        return dirs, files
    return [], []


class _File:
    def __init__(self, path, mode='r'):
        self._path = path
        if 'w' in mode:
            os.makedirs(os.path.dirname(path), exist_ok=True)
        self._fh = open(path, 'wb' if 'w' in mode else 'rb')

    def read(self):
        return self._fh.read().decode('utf-8')

    def readBytes(self):
        return self._fh.read()

    def write(self, data):
        if isinstance(data, str):
            data = data.encode('utf-8')
        return self._fh.write(data)

    def close(self):
        self._fh.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()


def _mkdir(path):
    os.makedirs(path, exist_ok=True)
    return True


def _delete(path):
    try:
        os.remove(path)
        return True
    except OSError:
        return False


xbmcvfs = types.ModuleType('xbmcvfs')
xbmcvfs.translatePath = _translate_path
xbmcvfs.exists = _exists
xbmcvfs.listdir = _listdir
xbmcvfs.File = _File
xbmcvfs.mkdir = _mkdir
xbmcvfs.mkdirs = _mkdir
xbmcvfs.delete = _delete


# --------------------------------------------------------------------------
# xbmc
# --------------------------------------------------------------------------

def _log(msg='', level=0):
    state.log_lines.append(msg)


def _get_cond_visibility(condition):
    return condition in state.conditions


def _execute_jsonrpc(request):
    method = json.loads(request)['method']
    response = state.jsonrpc.get(method, {})
    return json.dumps({'jsonrpc': '2.0', 'id': 1, **response})


xbmc = types.ModuleType('xbmc')
xbmc.LOGDEBUG = 0
xbmc.LOGINFO = 1
xbmc.LOGWARNING = 2
xbmc.LOGERROR = 3
xbmc.log = _log
xbmc.getCondVisibility = _get_cond_visibility
xbmc.executeJSONRPC = _execute_jsonrpc
xbmc.sleep = lambda ms: None
xbmc.getSkinDir = lambda: 'skin.estuary'
xbmc.getRegion = lambda region: {'dateshort': 'DD/MM/YYYY'}.get(region, '')


class _Monitor:
    def abortRequested(self):
        return False

    def waitForAbort(self, timeout=0):
        return False


xbmc.Monitor = _Monitor


# --------------------------------------------------------------------------
# xbmcaddon
# --------------------------------------------------------------------------

class _Addon:
    def getAddonInfo(self, key):
        return state.addon_info[key]

    def getLocalizedString(self, sid):
        return 'string-%s' % sid

    def getSetting(self, key):
        return str(state.settings.get(key, ''))

    def getSettingBool(self, key):
        return bool(state.settings.get(key, False))

    def getSettingInt(self, key):
        return int(state.settings.get(key, 0))

    def setSetting(self, key, value):
        state.settings[key] = value


xbmcaddon = types.ModuleType('xbmcaddon')
xbmcaddon.Addon = _Addon


# --------------------------------------------------------------------------
# exifread / iptcinfo3
#
# Kodi ships these as addons (declared in addon.xml), so they are not pip
# dependencies and do not exist in a test venv. lib.gui imports both at module
# level, which is enough to stop it importing at all.
# --------------------------------------------------------------------------

exifread = types.ModuleType('exifread')
exifread.process_file = lambda fh, **kwargs: {}

iptcinfo3 = types.ModuleType('iptcinfo3')


class _IPTCInfo(dict):
    def __init__(self, path, force=False):
        dict.__init__(self)


iptcinfo3.IPTCInfo = _IPTCInfo


# --------------------------------------------------------------------------
# xbmcgui -- lib.gui needs it; lib.utils does not. Minimal on purpose.
# --------------------------------------------------------------------------

xbmcgui = types.ModuleType('xbmcgui')
xbmcgui.getCurrentWindowDialogId = lambda: 12345


class _Window:
    def __init__(self, *args):
        self.props = {}

    def setProperty(self, key, value):
        self.props[key] = value

    def clearProperty(self, key):
        self.props.pop(key, None)


xbmcgui.Window = _Window
xbmcgui.WindowXMLDialog = _Window
xbmcgui.ControlImage = object
