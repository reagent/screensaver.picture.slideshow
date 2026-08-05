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
enforces the version floor that nothing else can: a release at or below what a
box already has installs nowhere and reports nothing.

`origin` is Team Kodi's GitLab and is not part of this flow.

## Tags

Upstream does not tag, so these were added retroactively:

| Tag | Meaning |
|---|---|
| `v7.0.3` | last version published to Kodi's official repo — the newest anyone can install |
| `v7.0.6` | last version *cut* in git (version bump + changelog entry), never submitted |
| `fork-point` | last upstream commit before this fork's work. Not a release. |

7.0.4 through 7.0.6 were minted but never submitted, and ~47 upstream commits
sit unreleased after them. So master is far ahead of anything installable.

## Release notes

Generate from **`v7.0.6..HEAD`** — `changelog.txt` is cumulative and already
documents 7.0.4 through 7.0.6, so an earlier base would restate them.

Exclude, matching every prior entry in the file: Weblate and translation
commits, merge commits, and development-only work (CI, tests, tooling, docs).
Collapse several commits for one feature into one bullet, and cancel any
add-then-revert pair to nothing.

`<news>` in `addon.xml` mirrors the new `changelog.txt` entry **verbatim** —
confirmed against history. It has been stale since ~7.0.1; update both together.

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
