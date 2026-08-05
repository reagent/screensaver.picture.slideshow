import sys

import pytest

from tests import fakes

# lib.utils reads xbmcaddon and xbmcvfs at import time (ADDON, CACHEFOLDER,
# ASFILE), so the fakes must be in place before it is imported anywhere.
sys.modules['xbmc'] = fakes.xbmc
sys.modules['xbmcvfs'] = fakes.xbmcvfs
sys.modules['xbmcaddon'] = fakes.xbmcaddon
sys.modules['xbmcgui'] = fakes.xbmcgui

from lib import utils as _utils  # noqa: E402


@pytest.fixture(autouse=True)
def _reset_fakes():
    fakes.reset()
    yield


@pytest.fixture(autouse=True)
def _restore_image_types():
    """Undo walk()'s mutation of the module-level IMAGE_TYPES list.

    lib/utils.py:99-104 calls IMAGE_TYPES.extend() inside walk()'s per-folder
    loop, so any test that runs with an imagedecoder addon present leaks those
    extensions into every test that follows -- order-dependent failures in the
    extension-filter tests. Delete this fixture when the hoist lands (#3); at
    that point the mutation is gone and the fixture is pinning nothing.
    """
    original = list(_utils.IMAGE_TYPES)
    yield
    _utils.IMAGE_TYPES[:] = original


@pytest.fixture
def utils():
    return _utils


@pytest.fixture
def tree():
    """The in-memory directory tree behind the fake xbmcvfs."""
    return fakes.state.tree


@pytest.fixture
def settings():
    """Addon settings dict, e.g. settings['recursive'] = False."""
    return fakes.state.settings


@pytest.fixture
def conditions():
    """getCondVisibility() answers True for anything added to this set."""
    return fakes.state.conditions


@pytest.fixture
def excludes(tmp_path, monkeypatch):
    """Write <pictureexcludes> regexes into a real advancedsettings.xml.

    get_excludes() parses ASFILE with stdlib etree, which the VFS fakes cannot
    intercept, so this has to be a real file and ASFILE has to be repointed at
    it. ASFILE is a module constant bound at import, hence the monkeypatch.
    """
    def _write(*regexes):
        body = ''.join('<regexp>%s</regexp>' % r for r in regexes)
        path = tmp_path / 'advancedsettings.xml'
        path.write_text(
            '<advancedsettings><pictureexcludes>%s</pictureexcludes></advancedsettings>' % body
        )
        monkeypatch.setattr(_utils, 'ASFILE', str(path))
        return str(path)

    return _write
