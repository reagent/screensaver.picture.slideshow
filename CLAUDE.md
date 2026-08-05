# screensaver.picture.slideshow

Official Team Kodi picture slideshow screensaver addon. Python 3, Kodi Matrix+.

Upstream is `origin` → gitlab.com/ronie/screensaver.picture.slideshow (Team Kodi).
`reagent` → github.com/reagent/screensaver.picture.slideshow is this fork.

## Commit style

Plain imperative subject line. No Conventional Commits prefix (`feat:`, `fix:`,
`chore:`) — match the existing log. Explain *why* in the body when the diff
doesn't make it obvious; long bodies are fine and common here.

## Testing

```
python3 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt
.venv/bin/pytest
```

`tests/mutation_check.py` is not run by pytest. It breaks `lib/utils.py` one
line at a time and asserts some test notices — the red phase the `walk()`
characterization tests never had. Run it after changing anything in `tests/`.
Slated for removal once the performance work lands (#11).

## Branches

`development` is the mainline — branch from it, PR into it. Every PR and every
push there runs the full CI suite.

`master` is the release branch. Only a tag publishes; landing a PR does not.
Cut a release with `python tools/release.py X.Y.Z` — dry run by default, and it
enforces the version floor that nothing else can (this addon ships with Kodi, so
a release at or below the bundled version installs nowhere and reports nothing).

`origin` is Team Kodi's GitLab and is not part of this flow.

## Installing on a Kodi box

Tagged releases publish a Kodi repository to GitHub Pages, so builds install and
update through the Kodi UI. See `docs/dev-install.md` — it also covers the
faster rsync-over-SSH loop for heavy iteration.

`tools/build_repo.py` defines what ships. Both CI jobs and the publish workflow
call it, so there is one definition of the addon's fileset.

## Agent skills

### Issue tracker

GitHub Issues on the `reagent` remote, via the `gh` CLI. See `docs/agents/issue-tracker.md`.

### Domain docs

Single-context: `CONTEXT.md` + `docs/adr/` at the repo root. See `docs/agents/domain.md`.
