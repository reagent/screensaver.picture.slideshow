"""When the slideshow reaches the end of its list in random mode.

lib/gui.py used to call create_cache() inline at that point -- a full
synchronous rescan of the image folder, mid-slideshow, on the display thread.
Over SMB that is a visible freeze, and it is redundant: the img_update thread
already rescans hourly.

Reshuffling has to persist. The resume offset is a bare index into the cached
list (lib/gui.py _save_offset/_get_offset), so if the in-memory order diverges
from the cache file, resuming lands on an unrelated image.
"""

import json

import pytest


@pytest.fixture
def screensaver(utils):
    """A Screensaver with just enough state to reshuffle, and no UI.

    Built without __init__ on purpose: constructing the real window would drag
    in skin parsing and control creation, none of which this behaviour touches.
    """
    from lib import gui

    show = object.__new__(gui.Screensaver)
    show.slideshow_type = 2
    show.slideshow_random = True
    show.slideshow_recursive = True
    show.slideshow_resume = True
    show.slideshow_path = 'smb://server/pics/'
    show.stop = False
    show.items = [['smb://server/pics/%02d.jpg' % i, '%02d.jpg' % i] for i in range(12)]
    return show


def read_cache(utils, show):
    with open(utils.CACHEFILE % show._hexfile()) as handle:
        return json.load(handle)


def test_wrap_does_not_rescan(screensaver, monkeypatch):
    """The whole point: no walk() of the image folder on the display thread."""
    from lib import gui

    def explode(*args, **kwargs):
        raise AssertionError('create_cache called at cycle wrap')

    monkeypatch.setattr(gui, 'create_cache', explode)
    monkeypatch.setattr(gui, 'walk', explode)

    screensaver._reshuffle_for_next_cycle()


def test_wrap_reshuffles_the_existing_list(screensaver):
    before = list(screensaver.items)

    screensaver._reshuffle_for_next_cycle()

    assert sorted(screensaver.items) == sorted(before), 'images were added or lost'
    assert screensaver.items != before, 'order did not change'


def test_wrap_persists_the_new_order(utils, screensaver):
    """Otherwise the resume offset indexes into a different sequence."""
    screensaver._reshuffle_for_next_cycle()

    assert read_cache(utils, screensaver) == screensaver.items


def test_hexfile_matches_the_key_get_items_uses(screensaver):
    """Both sites must derive the same cache filename or they write past each other."""
    from lib.utils import checksum

    expected = checksum(screensaver.slideshow_path.encode('utf-8')) \
        + '_' + str(screensaver.slideshow_recursive) \
        + '_' + str(screensaver.slideshow_random)

    assert screensaver._hexfile() == expected


def test_save_cache_round_trips(utils):
    images = [['smb://server/pics/a.jpg', 'a.jpg'], ['smb://server/pics/b.jpg', 'b.jpg']]

    utils.save_cache(images, 'testkey')

    with open(utils.CACHEFILE % 'testkey') as handle:
        assert json.load(handle) == images
