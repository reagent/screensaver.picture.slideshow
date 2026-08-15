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
    # _list_folder is shared by the serial and threaded walks, so these hit
    # whichever one walk() chooses
    ("drop natural sort of files",
     "    files.sort(key=_natural_key)",
     "    pass  # MUTANT"),
    ("sort subfolders before descending",
     "    subfolders = [os.path.join(folder,item,'') for item in dirs if not _excluded(item, excludes)]",
     "    subfolders = sorted(os.path.join(folder,item,'') for item in dirs if not _excluded(item, excludes))  # MUTANT"),
    ("never skip excluded files",
     "        if os.path.splitext(item)[1].lower() in extensions and not _excluded(item, excludes):",
     "        if os.path.splitext(item)[1].lower() in extensions:  # MUTANT"),
    ("never skip excluded dirs",
     "    subfolders = [os.path.join(folder,item,'') for item in dirs if not _excluded(item, excludes)]",
     "    subfolders = [os.path.join(folder,item,'') for item in dirs]  # MUTANT"),
    ("threaded walk ignores the recursive setting",
     "                if recursive:\n                    for subfolder in subfolders:",
     "                if True:  # MUTANT\n                    for subfolder in subfolders:"),
    ("serial walk ignores the recursive setting",
     "    subfolders, images = _list_folder(folder, excludes, extensions)\n    if recursive:",
     "    subfolders, images = _list_folder(folder, excludes, extensions)\n    if True:  # MUTANT"),
    ("threaded walk emits directories in completion order",
     "            stack.extend(reversed(subfolders))",
     "            stack.extend(subfolders)  # MUTANT"),
    ("extension match becomes case sensitive",
     "        if os.path.splitext(item)[1].lower() in extensions and not _excluded(item, excludes):",
     "        if os.path.splitext(item)[1] in extensions and not _excluded(item, excludes):  # MUTANT"),
    ("heif always enabled",
     "    if xbmc.getCondVisibility('System.HasAddon(imagedecoder.heif)'):",
     "    if True:  # MUTANT"),
    ("raw always enabled",
     "    if xbmc.getCondVisibility('System.HasAddon(imagedecoder.raw)'):",
     "    if True:  # MUTANT"),
    ("drop folder prefix from stored path",
     "            images.append([os.path.join(folder,item), item])",
     "            images.append([item, item])  # MUTANT"),
    ("multipath members left url-encoded",
     "        return [urllib.parse.unquote_plus(item) for item in path[12:-1].split('/')]",
     "        return [item for item in path[12:-1].split('/')]  # MUTANT"),
    ("multipath members visited in reverse",
     "        return [urllib.parse.unquote_plus(item) for item in path[12:-1].split('/')]",
     "        return [urllib.parse.unquote_plus(item) for item in reversed(path[12:-1].split('/'))]  # MUTANT"),
    ("skip the folder-exists guard",
     "        if xbmcvfs.exists(xbmcvfs.translatePath(folder)):",
     "        if True:  # MUTANT"),
    # The three below guard what #3 removed. Without them the suite would go
    # green again if the per-directory work crept back in.
    ("extension set built on the module-level list again",
     "    extensions = list(IMAGE_TYPES)",
     "    extensions = IMAGE_TYPES  # MUTANT -- += then mutates the global in place"),
    ("exists() re-checked for every subdirectory",
     "    subfolders = [os.path.join(folder,item,'') for item in dirs if not _excluded(item, excludes)]",
     "    subfolders = [os.path.join(folder,item,'') for item in dirs\n"
     "                  if not _excluded(item, excludes)\n"
     "                  and xbmcvfs.exists(xbmcvfs.translatePath(os.path.join(folder,item,'')))]  # MUTANT"),
    ("advancedsettings reparsed per scan step",
     "    excludes = [re.compile(expr) for expr in get_excludes()]",
     "    excludes = [re.compile(expr) for expr in get_excludes() + get_excludes()]  # MUTANT"),
]

# A test that is red on unmutated code "kills" every mutant. Prove green first.
base = subprocess.run(['.venv/bin/pytest', '-q', '--tb=no'], capture_output=True, text=True)
if 'failed' in base.stdout:
    sys.exit('baseline is not green, mutation results would be meaningless:\n' + base.stdout)
print('baseline green\n')

fails = 0
for name, old, new in MUTATIONS:
    assert ORIG.count(old) == 1, \
        "anchor for %r matched %d times, expected 1 -- the source moved" % (name, ORIG.count(old))
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
