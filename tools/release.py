"""Cut a release.

Bumps addon.xml on development, merges to master, tags, and pushes. The tag
push is what triggers .github/workflows/publish.yml.

    python tools/release.py 7.1.0             # check everything, change nothing
    python tools/release.py 7.1.0 --execute   # do it

Dry run by default. Every check runs in both modes, so a dry run that passes
means --execute will not stop halfway.

The check worth having is the version floor. This addon ships with Kodi, and
Kodi resolves a duplicate addon id by picking the highest version -- so a
release at or below the version already on the box is accepted everywhere,
publishes cleanly, and then simply never installs. Nothing reports it.
"""

import argparse
import json
import re
import subprocess
import sys
import xml.etree.ElementTree as etree
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
RELEASE_REMOTE = 'reagent'      # our GitHub fork; `origin` is Team Kodi's GitLab
UPSTREAM_REMOTE = 'origin'
MAINLINE = 'development'
RELEASE_BRANCH = 'master'


class Failed(Exception):
    pass


def git(*args, check=True):
    result = subprocess.run(('git',) + args, cwd=REPO, capture_output=True, text=True)
    if check and result.returncode:
        raise Failed('git %s: %s' % (' '.join(args), result.stderr.strip()))
    return result.stdout.strip()


def parse_version(text):
    if not re.fullmatch(r'\d+\.\d+\.\d+', text):
        raise Failed('version must look like X.Y.Z, got %r' % text)
    return tuple(int(part) for part in text.split('.'))


def declared_version(ref=None):
    """Version in addon.xml, from the working tree or from a git ref."""
    text = git('show', '%s:addon.xml' % ref) if ref else (REPO / 'addon.xml').read_text()
    return etree.fromstring(text).get('version')


def check_clean_tree():
    if git('status', '--porcelain'):
        raise Failed('working tree is dirty; commit or stash first')


def check_on_mainline():
    branch = git('rev-parse', '--abbrev-ref', 'HEAD')
    if branch != MAINLINE:
        raise Failed('releases are cut from %s, currently on %s' % (MAINLINE, branch))


def check_synced():
    git('fetch', '--quiet', RELEASE_REMOTE)
    local = git('rev-parse', 'HEAD')
    remote = git('rev-parse', '%s/%s' % (RELEASE_REMOTE, MAINLINE))
    if local != remote:
        raise Failed('%s differs from %s/%s; push or pull first'
                     % (MAINLINE, RELEASE_REMOTE, MAINLINE))
    return local


def check_ci_green(sha):
    slug = re.sub(r'^.*github\.com[:/]|\.git$', '', git('remote', 'get-url', RELEASE_REMOTE))
    result = subprocess.run(
        ['gh', 'api', 'repos/%s/commits/%s/check-runs' % (slug, sha)],
        capture_output=True, text=True)
    if result.returncode:
        raise Failed('could not read CI status (%s); pass --skip-ci-check to override'
                     % result.stderr.strip().splitlines()[-1:])

    runs = json.loads(result.stdout)['check_runs']
    if not runs:
        raise Failed('no CI runs for %s; pass --skip-ci-check to override' % sha[:8])
    bad = ['%s=%s' % (r['name'], r['conclusion'] or r['status'])
           for r in runs if r['conclusion'] != 'success']
    if bad:
        raise Failed('CI is not green: %s' % ', '.join(bad))
    return len(runs)


def check_version_floor(new):
    """New version must beat everything that could already be on a box."""
    floors = [('addon.xml', declared_version())]

    tags = [t[1:] for t in git('tag', '--list', 'v*').split() if t]
    if tags:
        floors.append(('last release', max(tags, key=parse_version)))

    # Team Kodi's copy is what Kodi bundles. If they have moved past us, a
    # release below their version loses the duplicate-id comparison on any box
    # running a Kodi new enough to bundle it.
    if UPSTREAM_REMOTE in git('remote').split():
        try:
            git('fetch', '--quiet', UPSTREAM_REMOTE, RELEASE_BRANCH)
            floors.append(('upstream', declared_version('FETCH_HEAD')))
        except Failed:
            print('  ! could not reach %s, skipping the upstream floor' % UPSTREAM_REMOTE)

    for label, floor in floors:
        if parse_version(new) <= parse_version(floor):
            raise Failed('%s is not above %s (%s). Kodi would keep the copy it has.'
                         % (new, floor, label))
    return floors


def check_changelog(new):
    """The entry is content, so a human writes it; this only checks it exists."""
    head = (REPO / 'changelog.txt').read_text().splitlines()
    if not head or head[0].strip() != 'v%s' % new:
        raise Failed('changelog.txt must start with "v%s" and its notes' % new)
    if len(head) < 2 or not head[1].strip():
        raise Failed('changelog.txt has a v%s heading but no notes under it' % new)


def bump_addon_xml(new):
    path = REPO / 'addon.xml'
    text = path.read_text(encoding='utf-8')
    old = 'version="%s"' % declared_version()
    if text.count(old) != 1:
        raise Failed('version attribute is not unique in addon.xml')
    path.write_text(text.replace(old, 'version="%s"' % new), encoding='utf-8')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('version', help='new version, X.Y.Z')
    parser.add_argument('--execute', action='store_true',
                        help='actually bump, merge, tag and push')
    parser.add_argument('--skip-ci-check', action='store_true')
    args = parser.parse_args()

    tag = 'v%s' % args.version

    try:
        parse_version(args.version)
        check_clean_tree()
        check_on_mainline()
        sha = check_synced()
        print('  %s at %s, in sync with %s' % (MAINLINE, sha[:8], RELEASE_REMOTE))

        if args.skip_ci_check:
            print('  ! CI check skipped')
        else:
            print('  CI green (%d checks)' % check_ci_green(sha))

        for label, floor in check_version_floor(args.version):
            print('  %s > %s (%s)' % (args.version, floor, label))

        check_changelog(args.version)
        print('  changelog.txt has notes for %s' % tag)

        if git('tag', '--list', tag):
            raise Failed('tag %s already exists' % tag)
    except Failed as exc:
        sys.exit('release blocked: %s' % exc)

    if not args.execute:
        print('\nall checks pass. re-run with --execute to:')
        print('  bump addon.xml to %s and commit on %s' % (args.version, MAINLINE))
        print('  merge %s into %s' % (MAINLINE, RELEASE_BRANCH))
        print('  push %s and tag %s -> triggers publish' % (RELEASE_BRANCH, tag))
        return

    try:
        bump_addon_xml(args.version)
        git('commit', '--quiet', '-am', 'Release %s' % args.version)
        git('push', '--quiet', RELEASE_REMOTE, MAINLINE)

        git('checkout', '--quiet', RELEASE_BRANCH)
        git('merge', '--quiet', '--ff-only', MAINLINE)
        git('push', '--quiet', RELEASE_REMOTE, RELEASE_BRANCH)

        # last, and separately: this is the irreversible step that publishes
        git('tag', tag)
        git('push', '--quiet', RELEASE_REMOTE, tag)
    except Failed as exc:
        sys.exit('release failed partway: %s\nrepo is on %s'
                 % (exc, git('rev-parse', '--abbrev-ref', 'HEAD')))

    print('\nreleased %s. publish workflow triggered by the tag push.' % tag)


if __name__ == '__main__':
    main()
