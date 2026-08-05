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

## Agent skills

### Issue tracker

GitHub Issues on the `reagent` remote, via the `gh` CLI. See `docs/agents/issue-tracker.md`.

### Domain docs

Single-context: `CONTEXT.md` + `docs/adr/` at the repo root. See `docs/agents/domain.md`.
