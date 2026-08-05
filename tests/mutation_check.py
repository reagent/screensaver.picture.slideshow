"""Verify the characterization suite actually pins walk()'s behavior.

Characterization tests are green by construction -- they assert what the code
already does -- so a passing run proves nothing on its own. This perturbs
lib/utils.py one line at a time and checks that some test notices.

Run it before trusting the suite to catch a regression in #3 or #6:

    .venv/bin/python tests/mutation_check.py

Exits non-zero if any mutant survives. lib/utils.py is restored either way.
"""

import os, shutil, subprocess, sys, pathlib

SRC = pathlib.Path('lib/utils.py')
ORIG = SRC.read_text()

MUTATIONS = [
    ("drop natural sort of files",
     "                files.sort(key=alphanum_key)",
     "                pass  # MUTANT"),
    ("sort dirs before recursing",
     "                for item in dirs:",
     "                for item in sorted(dirs):  # MUTANT"),
    ("never skip excluded files",
     "                            fileskip = True",
     "                            fileskip = False  # MUTANT"),
    ("never skip excluded dirs",
     "                                dirskip = True",
     "                                dirskip = False  # MUTANT"),
    ("ignore the recursive setting",
     "            if xbmcaddon.Addon().getSettingBool('recursive'):",
     "            if True:  # MUTANT"),
    ("extension match becomes case sensitive",
     "                    if os.path.splitext(item)[1].lower() in IMAGE_TYPES and not fileskip:",
     "                    if os.path.splitext(item)[1] in IMAGE_TYPES and not fileskip:  # MUTANT"),
    ("heif always enabled",
     "            if xbmc.getCondVisibility('System.HasAddon(imagedecoder.heif)'):",
     "            if True:  # MUTANT"),
    ("raw always enabled",
     "            if xbmc.getCondVisibility('System.HasAddon(imagedecoder.raw)'):",
     "            if True:  # MUTANT"),
    ("drop folder prefix from stored path",
     "                        images.append([os.path.join(folder,item), item])",
     "                        images.append([item, item])  # MUTANT"),
    ("multipath members left url-encoded",
     "            folders.append(urllib.parse.unquote_plus(item))",
     "            folders.append(item)  # MUTANT"),
    ("multipath members visited in reverse",
     "        for item in paths:",
     "        for item in reversed(paths):  # MUTANT"),
    ("skip the folder-exists guard",
     "        if xbmcvfs.exists(xbmcvfs.translatePath(folder)):",
     "        if True:  # MUTANT"),
]

# A test that is red on unmutated code "kills" every mutant. Prove green first.
base = subprocess.run(['.venv/bin/pytest', '-q', '--tb=no'], capture_output=True, text=True)
if 'failed' in base.stdout:
    sys.exit('baseline is not green, mutation results would be meaningless:\n' + base.stdout)
print('baseline green\n')

fails = 0
for name, old, new in MUTATIONS:
    assert ORIG.count(old) == 1, "anchor not unique: %s" % name
    SRC.write_text(ORIG.replace(old, new))
    # .pyc validation keys on (mtime seconds, size). Mutants of equal size
    # written within the same second reuse the previous mutant's bytecode.
    shutil.rmtree('lib/__pycache__', ignore_errors=True)
    p = subprocess.run(['.venv/bin/pytest', '-q', '--tb=no'],
                       capture_output=True, text=True,
                       env={**os.environ, 'PYTHONDONTWRITEBYTECODE': '1'})
    SRC.write_text(ORIG)
    killed = [l.split(' ')[1] for l in p.stdout.splitlines() if l.startswith('FAILED')]
    if killed:
        print("KILLED  %-42s by %s" % (name, ', '.join(t.split('::')[-1] for t in killed)))
    else:
        print("SURVIVED %-42s <-- no test caught this" % name)
        fails += 1

assert SRC.read_text() == ORIG, "failed to restore lib/utils.py"
print("\n%d/%d mutants killed" % (len(MUTATIONS) - fails, len(MUTATIONS)))
sys.exit(1 if fails else 0)
