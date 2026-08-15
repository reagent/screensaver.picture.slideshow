import glob
import os
import sys

import pytest

from tests import fakes

# lib.utils reads xbmcaddon and xbmcvfs at import time (ADDON, CACHEFOLDER,
# ASFILE), so the fakes must be in place before it is imported anywhere.
sys.modules['xbmc'] = fakes.xbmc
sys.modules['xbmcvfs'] = fakes.xbmcvfs
sys.modules['xbmcaddon'] = fakes.xbmcaddon
sys.modules['xbmcgui'] = fakes.xbmcgui
sys.modules['exifread'] = fakes.exifread
sys.modules['iptcinfo3'] = fakes.iptcinfo3

from lib import utils as _utils  # noqa: E402


@pytest.fixture(autouse=True)
def _reset_fakes():
    fakes.reset()
    # The fake profile directory is created once per session, so cache files
    # written by one test are still on disk for the next -- which silently turns
    # "first launch, nothing cached" tests into "cache already exists" ones.
    for stale in glob.glob(os.path.join(fakes.PROFILE_DIR, '**', '*'), recursive=True):
        if os.path.isfile(stale):
            os.remove(stale)
    yield


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
