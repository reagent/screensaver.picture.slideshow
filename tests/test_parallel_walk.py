"""walk() lists directories through a thread pool.

xbmcvfs.listdir is one SMB round trip per directory, issued serially, so a deep
tree costs directory-count x latency. Overlapping them hides the latency.

The risk is ordering. The serial implementation is DFS preorder with
subdirectories in whatever order the VFS returned them -- never sorted -- and
the resume offset is a bare index into the resulting list. So a parallel walk
that returns the same *set* in a different order silently breaks resume.

These tests pin that by comparing against the serial implementation directly,
with jittered delays in the fake listdir so directories complete out of order.
"""

import pytest


ROOT = 'smb://server/pics/'


def build_tree(tree, breadth=4, depth=3):
    """A tree with deliberately non-alphabetical directory names.

    'z' before 'a' at every level, so anything that sorts folder paths for
    output produces a different list and the comparison catches it.
    """
    def add(path, level):
        names = ['z%d' % i for i in range(breadth)] + ['a%d' % i for i in range(breadth)]
        subdirs = names if level < depth else []
        tree.add(path, dirs=subdirs,
                 files=['img10.jpg', 'img2.jpg', 'img1.jpg', 'notes.txt'])
        for name in subdirs:
            add(path + name + '/', level + 1)

    add(ROOT, 0)
    return tree


def walk_serially(utils, path=ROOT):
    """Reference implementation: the recursive scan, one directory at a time."""
    workers = utils.WALK_WORKERS
    utils.WALK_WORKERS = 1
    try:
        return utils.walk(path)
    finally:
        utils.WALK_WORKERS = workers


def test_parallel_output_is_identical_to_serial(utils, tree):
    build_tree(tree)

    expected = walk_serially(utils)
    actual = utils.walk(ROOT)

    assert actual == expected


def test_parallel_holds_order_when_directories_finish_out_of_order(utils, tree):
    """The race detector. Without jitter the pool may finish in submit order."""
    import tests.fakes as fakes

    build_tree(tree, breadth=3, depth=3)
    expected = walk_serially(utils)

    fakes.state.listdir_delay = 0.002
    actual = utils.walk(ROOT)

    assert actual == expected


def test_every_directory_is_listed_exactly_once(utils, tree):
    build_tree(tree, breadth=3, depth=2)

    utils.walk(ROOT)

    calls = [c for c in tree.listdir_calls if c.startswith('smb://')]
    assert len(calls) == len(set(calls)), 'a directory was listed more than once'
    assert set(calls) == set(tree.folders), 'not every directory was listed'


def test_parallel_respects_recursion_disabled(utils, tree, settings):
    settings['recursive'] = False
    build_tree(tree, breadth=2, depth=2)

    assert utils.walk(ROOT) == walk_serially(utils)


def test_recursion_disabled_lists_only_the_entry_folder(utils, tree, settings):
    """Asserting on the returned images alone is not enough.

    The threaded walk decides twice whether to recurse: once when queueing
    subdirectories, once when rebuilding the output. If only the first is
    broken, every subdirectory is listed over the network and the result is
    still correct -- the exact wasted round trips this whole change exists to
    remove, invisible from the return value.
    """
    settings['recursive'] = False
    build_tree(tree, breadth=3, depth=2)

    utils.walk(ROOT)

    assert [c for c in tree.listdir_calls if c.startswith('smb://')] == [ROOT]


def test_parallel_respects_excludes(utils, tree, excludes):
    excludes('^z0$', r'img2\.jpg')
    build_tree(tree, breadth=3, depth=2)

    assert utils.walk(ROOT) == walk_serially(utils)


def test_multipath_members_stay_in_order(utils, tree):
    from tests.test_walk import multipath

    for name in ('second', 'first'):
        tree.add('smb://server/%s/' % name, dirs=['sub'], files=['a.jpg'])
        tree.add('smb://server/%s/sub/' % name, files=['b.jpg'])

    path = multipath('smb://server/second/', 'smb://server/first/')

    assert utils.walk(path) == walk_serially(utils, path)


def test_plugin_paths_are_not_threaded(utils, monkeypatch):
    """JSON-RPC directories are low fan-out; threading them adds risk, not speed."""
    calls = []
    real = utils._scan
    monkeypatch.setattr(utils, '_scan', lambda *a, **k: calls.append(a[0]) or real(*a, **k))
    monkeypatch.setattr(utils, '_scan_parallel',
                        lambda *a, **k: pytest.fail('plugin:// path was threaded'))
    monkeypatch.setattr(utils.xbmcvfs, 'exists', lambda p: True)

    utils.walk('plugin://plugin.image.test/')

    assert calls == ['plugin://plugin.image.test/']
