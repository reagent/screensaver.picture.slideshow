"""Build a Kodi repository tree from this checkout.

Produces the layout Kodi expects behind a <datadir zip="true"> entry:

    <out>/addons.xml
    <out>/addons.xml.md5
    <out>/<addon.id>/<addon.id>-<version>.zip
    <out>/<addon.id>/addon.xml
    <out>/<addon.id>/icon.png

Usage:

    python tools/build_repo.py <out-dir> [--version X.Y.Z]

--version overrides the screensaver's version for this build only; addon.xml
in git is left alone. Kodi offers an update only when the version increases,
so published builds need a distinct, monotonically rising number.
"""

import argparse
import hashlib
import os
import pathlib
import shutil
import xml.etree.ElementTree as etree
import zipfile

REPO = pathlib.Path(__file__).resolve().parent.parent
ADDON_ID = 'screensaver.picture.slideshow'
REPOSITORY_ID = 'repository.reagent.slideshow'

# Everything that exists for development and must not ship inside the zip.
EXCLUDE_TOP_LEVEL = {
    '.git', '.github', '.gitignore', '.venv', 'tests', 'docs', 'tools',
    'pytest.ini', 'requirements-dev.txt', 'CLAUDE.md', REPOSITORY_ID,
}


def _stage_screensaver(staging, version, skip=()):
    """Copy the addon into staging/<id>/, optionally rewriting its version.

    `skip` holds resolved paths to leave alone -- the output and staging
    directories, which land inside the repo when given as relative paths and
    would otherwise be copied into themselves.
    """
    target = staging / ADDON_ID
    target.mkdir(parents=True)
    for item in REPO.iterdir():
        if item.name in EXCLUDE_TOP_LEVEL or item.name.startswith('.'):
            continue
        if item.resolve() in skip:
            continue
        if item.is_dir():
            shutil.copytree(item, target / item.name,
                            ignore=shutil.ignore_patterns('__pycache__'))
        else:
            shutil.copy2(item, target / item.name)

    if version:
        # A targeted text edit rather than an etree round trip: rewriting the
        # file would reorder attributes and drop the tab indentation, which
        # makes the published addon.xml pointlessly different from the source.
        path = target / 'addon.xml'
        text = path.read_text(encoding='utf-8')
        current = etree.fromstring(text).get('version')
        old = 'version="%s"' % current
        assert text.count(old) == 1, 'version attribute is not unique in addon.xml'
        path.write_text(text.replace(old, 'version="%s"' % version), encoding='utf-8')

    return target


def _stage_repository(staging):
    target = staging / REPOSITORY_ID
    shutil.copytree(REPO / REPOSITORY_ID, target)
    return target


def _zip(source, out_dir):
    """Zip source/ so the archive contains a single top-level <id>/ folder.

    Kodi requires that folder to be named exactly the addon id.
    """
    addon_id = source.name
    version = etree.parse(source / 'addon.xml').getroot().get('version')
    dest = out_dir / addon_id
    dest.mkdir(parents=True, exist_ok=True)
    archive = dest / ('%s-%s.zip' % (addon_id, version))

    with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(source.rglob('*')):
            if path.is_file():
                zf.write(path, os.path.join(addon_id, str(path.relative_to(source))))

    # Kodi reads these directly from the repository, without unpacking the zip.
    shutil.copy2(source / 'addon.xml', dest / 'addon.xml')
    icon = source / 'icon.png'
    if not icon.exists():
        icon = source / 'resources' / 'icon.png'
    if icon.exists():
        shutil.copy2(icon, dest / 'icon.png')

    return archive


def _write_index(staged, out_dir):
    """addons.xml is every addon.xml concatenated under one <addons> root."""
    lines = ['<?xml version="1.0" encoding="UTF-8" standalone="yes"?>', '<addons>']
    for source in staged:
        root = etree.parse(source / 'addon.xml').getroot()
        body = etree.tostring(root, encoding='unicode').strip()
        lines.extend('\t' + line for line in body.splitlines())
    lines.append('</addons>')
    index = '\n'.join(lines) + '\n'

    (out_dir / 'addons.xml').write_text(index, encoding='utf-8')
    digest = hashlib.md5(index.encode('utf-8')).hexdigest()
    (out_dir / 'addons.xml.md5').write_text(digest, encoding='utf-8')
    return digest


def _write_indexes(out_dir):
    """Emit an index.html per directory so Kodi can browse this over HTTP.

    Kodi lists an HTTP source by parsing <a href> out of the returned HTML.
    GitHub Pages serves no directory listing of its own -- a directory with no
    index.html is a 404 -- so without these the "add source, then install from
    zip" flow shows an empty folder. Only the one-time install needs this; once
    the repository addon is in place Kodi fetches addons.xml by URL directly.
    """
    for directory in [out_dir] + sorted(p for p in out_dir.iterdir() if p.is_dir()):
        entries = sorted(directory.iterdir(), key=lambda p: (p.is_file(), p.name))
        links = []
        if directory != out_dir:
            links.append('<a href="../">../</a>')
        for entry in entries:
            if entry.name == 'index.html':
                continue
            name = entry.name + ('/' if entry.is_dir() else '')
            links.append('<a href="%s">%s</a>' % (name, name))
        (directory / 'index.html').write_text(
            '<html><body>\n%s\n</body></html>\n' % '<br>\n'.join(links),
            encoding='utf-8')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('out')
    parser.add_argument('--version', help='version for the screensaver build')
    parser.add_argument('--staging', default=None,
                        help='where to assemble sources (default: <out>/../staging)')
    args = parser.parse_args()

    out_dir = pathlib.Path(args.out).resolve()
    staging = pathlib.Path(args.staging).resolve() if args.staging else out_dir.parent / 'staging'
    for path in (out_dir, staging):
        shutil.rmtree(path, ignore_errors=True)
        path.mkdir(parents=True)

    skip = {out_dir, staging}
    staged = [_stage_screensaver(staging, args.version, skip), _stage_repository(staging)]
    for source in staged:
        print('packaged %s' % _zip(source, out_dir).relative_to(out_dir))
    print('addons.xml.md5 %s' % _write_index(staged, out_dir))
    _write_indexes(out_dir)
    print('wrote directory indexes for HTTP browsing')


if __name__ == '__main__':
    main()
