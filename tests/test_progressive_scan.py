"""First launch must not block on a full scan.

onInit() scanned the whole tree before showing anything, and then the
img_update thread immediately scanned it again. On a real share that is two
full scans back to back -- measured at 2100+ directories and over 20 minutes
each on a Raspberry Pi 5 over SMB, with the user watching a splash screen.

The background thread is already doing the deep scan, so the foreground one
only has to produce something to show: the top folder, one listdir, immediate.
The deep scan replaces it when it finishes.
"""

import json

import pytest


ROOT = 'smb://server/pics/'


@pytest.fixture
def screensaver(utils, tree, settings):
    from lib import gui

    settings['type'] = 2
    settings['recursive'] = True
    tree.add(ROOT, dirs=['sub'], files=['top1.jpg', 'top2.jpg'])
    tree.add(ROOT + 'sub/', dirs=['deeper'], files=['nested.jpg'])
    tree.add(ROOT + 'sub/deeper/', files=['deep.jpg'])

    show = object.__new__(gui.Screensaver)
    show.slideshow_type = 2
    show.slideshow_random = False
    show.slideshow_recursive = True
    show.slideshow_resume = False
    show.slideshow_path = ROOT
    show.items = []
    return show


def listed(tree):
    return [c for c in tree.listdir_calls if c.startswith('smb://')]


def test_first_launch_scans_only_the_top_folder(screensaver, tree):
    screensaver._get_items()

    assert listed(tree) == [ROOT], 'first launch descended into the tree'
    assert [img[1] for img in screensaver.items] == ['top1.jpg', 'top2.jpg']


def test_first_launch_shows_something_immediately(screensaver):
    screensaver._get_items()

    assert screensaver.items, 'nothing to show, so onInit would still block'


def test_background_update_scans_the_whole_tree(screensaver, tree):
    screensaver._get_items()
    tree.listdir_calls.clear()

    screensaver._get_items(True)

    assert listed(tree) == [ROOT, ROOT + 'sub/', ROOT + 'sub/deeper/']
    assert [img[1] for img in screensaver.items] == ['top1.jpg', 'top2.jpg', 'nested.jpg', 'deep.jpg']


def test_the_deep_scan_replaces_the_partial_cache(utils, screensaver, tree):
    screensaver._get_items()
    screensaver._get_items(True)

    with open(utils.CACHEFILE % screensaver._hexfile()) as handle:
        cached = json.load(handle)

    assert cached == screensaver.items
    assert len(cached) == 4, 'cache still holds only the shallow result'


def test_a_later_launch_with_a_full_cache_does_not_scan(screensaver, tree):
    """Only the very first launch is shallow; after that the cache is read."""
    screensaver._get_items()
    screensaver._get_items(True)
    tree.listdir_calls.clear()

    screensaver._get_items()

    assert listed(tree) == [], 'a cached launch went back to the network'
    assert len(screensaver.items) == 4


def test_recursive_setting_off_is_not_a_partial_scan(screensaver, tree, settings):
    """With recursion disabled the top folder IS the whole scan.

    The background pass must still agree with the foreground one rather than
    treating the shallow result as something to replace.
    """
    settings['recursive'] = False

    screensaver._get_items()
    first = list(screensaver.items)
    screensaver._get_items(True)

    assert screensaver.items == first
