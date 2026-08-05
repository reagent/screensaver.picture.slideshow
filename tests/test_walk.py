"""Characterization tests for lib.utils.walk().

These pin *current* behavior so the performance refactors (#3, #6) can be
verified as behavior-preserving. Order assertions are the point, not a detail:
the resume offset is a raw index into the cached list (lib/gui.py:441, :452),
so any order drift silently sends resume to the wrong image.

These pass against unmodified code by construction, so green proves nothing on
its own. tests/mutation_check.py perturbs lib/utils.py line by line and asserts
some test notices; run it after changing anything here.
"""

from urllib.parse import quote_plus

ROOT = 'smb://server/pics/'


def paths(images):
    return [img[0] for img in images]


def multipath(*folders):
    """Build a multipath:// url the way Kodi does.

    Each member is url-encoded so its own '/' separators survive the split
    walk() performs on the joined string.
    """
    return 'multipath://' + ''.join(quote_plus(f) + '/' for f in folders)


def folder_checks(tree):
    """exists() calls against the image tree only.

    get_excludes() also calls exists() on advancedsettings.xml, once per
    directory -- see test_advancedsettings_is_reparsed_for_every_directory.
    """
    return [c for c in tree.exists_calls if c.startswith('smb://')]


def test_flat_directory(utils, tree):
    tree.add(ROOT, files=['a.jpg', 'b.png'])

    images = utils.walk(ROOT)

    assert images == [
        ['smb://server/pics/a.jpg', 'a.jpg'],
        ['smb://server/pics/b.png', 'b.png'],
    ]


def test_non_image_files_ignored(utils, tree):
    tree.add(ROOT, files=['a.jpg', 'notes.txt', 'movie.mkv', 'b.JPEG'])

    assert paths(utils.walk(ROOT)) == [
        'smb://server/pics/a.jpg',
        'smb://server/pics/b.JPEG',
    ]


def test_files_are_natural_sorted(utils, tree):
    tree.add(ROOT, files=['img10.jpg', 'img2.jpg', 'img1.jpg'])

    assert [img[1] for img in utils.walk(ROOT)] == ['img1.jpg', 'img2.jpg', 'img10.jpg']


def test_nested_tree_is_dfs_preorder_in_backend_directory_order(utils, tree):
    """Subdirectories are visited in the order the VFS returned them.

    walk() sorts `files` (lib/utils.py:121-123) but never sorts `dirs`, so
    'zeta' before 'alpha' here is load-bearing: a parallel rewrite that sorts
    folder paths for output produces a different list and breaks resume.
    """
    tree.add(ROOT, dirs=['zeta', 'alpha'], files=['top.jpg'])
    tree.add(ROOT + 'zeta/', dirs=['inner'], files=['z.jpg'])
    tree.add(ROOT + 'zeta/inner/', files=['deep.jpg'])
    tree.add(ROOT + 'alpha/', files=['a.jpg'])

    assert paths(utils.walk(ROOT)) == [
        'smb://server/pics/top.jpg',
        'smb://server/pics/zeta/z.jpg',
        'smb://server/pics/zeta/inner/deep.jpg',
        'smb://server/pics/alpha/a.jpg',
    ]


def test_recursion_disabled_stops_at_top_level(utils, tree, settings):
    settings['recursive'] = False
    tree.add(ROOT, dirs=['sub'], files=['top.jpg'])
    tree.add(ROOT + 'sub/', files=['nested.jpg'])

    assert paths(utils.walk(ROOT)) == ['smb://server/pics/top.jpg']


def test_missing_folder_is_never_listed(utils, tree):
    """The exists() guard must short-circuit before listdir().

    Asserting only on the empty return would pass with the guard removed,
    since listing a nonexistent folder yields nothing either way.
    """
    assert utils.walk('smb://server/gone/') == []
    assert tree.listdir_calls == []


def test_exists_is_checked_for_every_folder_including_subdirectories(utils, tree):
    """Pins the redundant round trip that #3 removes.

    Each recursion re-checks exists() on a subdirectory whose existence the
    parent's listdir() already established -- a second SMB round trip per
    directory. This test is expected to change when #3 lands; that is the
    point, so the reduction shows up as a deliberate edit rather than silently.
    """
    tree.add(ROOT, dirs=['sub'])
    tree.add(ROOT + 'sub/', files=['a.jpg'])

    utils.walk(ROOT)

    assert folder_checks(tree) == ['smb://server/pics/', 'smb://server/pics/sub/']


def test_advancedsettings_is_reparsed_for_every_directory(utils, tree, excludes):
    """Pins the per-directory XML parse that #3 hoists out.

    get_excludes() runs at the top of every walk() call, so a 2000-directory
    tree reads and parses advancedsettings.xml 2000 times.
    """
    asfile = excludes('nothing-matches-this')
    tree.add(ROOT, dirs=['a', 'b'])
    tree.add(ROOT + 'a/', files=['x.jpg'])
    tree.add(ROOT + 'b/', files=['y.jpg'])

    utils.walk(ROOT)

    assert tree.exists_calls.count(asfile) == 3


class TestExcludes:
    def test_matching_files_are_skipped(self, utils, tree, excludes):
        excludes('private')
        tree.add(ROOT, files=['holiday.jpg', 'private-stuff.jpg'])

        assert paths(utils.walk(ROOT)) == ['smb://server/pics/holiday.jpg']

    def test_matching_directories_are_not_descended_into(self, utils, tree, excludes):
        excludes('^skipme$')
        tree.add(ROOT, dirs=['skipme', 'keep'])
        tree.add(ROOT + 'skipme/', files=['hidden.jpg'])
        tree.add(ROOT + 'keep/', files=['shown.jpg'])

        assert paths(utils.walk(ROOT)) == ['smb://server/pics/keep/shown.jpg']

    def test_several_regexes_all_apply(self, utils, tree, excludes):
        excludes('^tmp', r'\.thumb\.')
        tree.add(ROOT, files=['tmp-a.jpg', 'b.thumb.jpg', 'good.jpg'])

        assert paths(utils.walk(ROOT)) == ['smb://server/pics/good.jpg']

    def test_no_advancedsettings_file_means_no_excludes(self, utils, tree):
        tree.add(ROOT, files=['private-stuff.jpg'])

        assert paths(utils.walk(ROOT)) == ['smb://server/pics/private-stuff.jpg']


class TestMultipath:
    """A multipath:// source is several folders in one setting.

    Kodi url-encodes each member so that '/' inside a path becomes %2F and the
    members can be split on '/'.
    """

    def test_images_from_every_member_in_multipath_order(self, utils, tree):
        tree.add('smb://server/second/', files=['b.jpg'])
        tree.add('smb://server/first/', files=['a.jpg'])

        images = utils.walk(multipath('smb://server/second/', 'smb://server/first/'))

        assert paths(images) == [
            'smb://server/second/b.jpg',
            'smb://server/first/a.jpg',
        ]

    def test_encoded_spaces_are_decoded(self, utils, tree):
        tree.add('smb://server/my photos/', files=['a.jpg'])

        images = utils.walk(multipath('smb://server/my photos/'))

        assert paths(images) == ['smb://server/my photos/a.jpg']

    def test_members_are_recursed_into(self, utils, tree, settings):
        settings['recursive'] = True
        tree.add('smb://server/first/', dirs=['sub'], files=['a.jpg'])
        tree.add('smb://server/first/sub/', files=['deep.jpg'])

        images = utils.walk(multipath('smb://server/first/'))

        assert paths(images) == [
            'smb://server/first/a.jpg',
            'smb://server/first/sub/deep.jpg',
        ]

    def test_missing_member_is_skipped_without_killing_the_scan(self, utils, tree):
        tree.add('smb://server/present/', files=['a.jpg'])

        images = utils.walk(multipath('smb://server/gone/', 'smb://server/present/'))

        assert paths(images) == ['smb://server/present/a.jpg']


class TestExtensionFiltering:
    def test_heif_only_when_imagedecoder_present(self, utils, tree, conditions):
        tree.add(ROOT, files=['a.heic', 'b.jpg'])

        assert paths(utils.walk(ROOT)) == ['smb://server/pics/b.jpg']

        conditions.add('System.HasAddon(imagedecoder.heif)')
        assert paths(utils.walk(ROOT)) == [
            'smb://server/pics/a.heic',
            'smb://server/pics/b.jpg',
        ]

    def test_mpo_only_when_imagedecoder_present(self, utils, tree, conditions):
        tree.add(ROOT, files=['a.mpo'])

        assert utils.walk(ROOT) == []

        conditions.add('System.HasAddon(imagedecoder.mpo)')
        assert paths(utils.walk(ROOT)) == ['smb://server/pics/a.mpo']

    def test_raw_only_when_imagedecoder_present(self, utils, tree, conditions):
        tree.add(ROOT, files=['a.cr2'])

        assert utils.walk(ROOT) == []

        conditions.add('System.HasAddon(imagedecoder.raw)')
        assert paths(utils.walk(ROOT)) == ['smb://server/pics/a.cr2']

    def test_extension_match_is_case_insensitive(self, utils, tree):
        tree.add(ROOT, files=['a.JPG', 'b.TiFf'])

        assert len(utils.walk(ROOT)) == 2
