# Installing builds on a Kodi box

Tagged releases publish a Kodi repository to GitHub Pages. Install the
repository addon once and Kodi handles updates from then on.

**These are not the official addon.** They replace it, share its id, and are
not reviewed by Team Kodi.

## One-time setup

Nothing needs to be copied to the box — Kodi installs straight from the URL.

1. **Enable unknown sources** — Settings → System → Add-ons → Unknown sources,
   and accept the warning.

2. **Add the repository as a file source** — Settings → File manager →
   Add source → `<None>`, and enter:

   ```
   https://reagent.github.io/screensaver.picture.slideshow/
   ```

   Name it something recognisable, e.g. `slideshow-dev`. The trailing slash
   matters.

3. **Install the repository addon** — Add-ons → Install from zip file →
   `slideshow-dev` → `repository.reagent.slideshow` →
   `repository.reagent.slideshow-1.0.0.zip`.

4. **Install the screensaver** — Add-ons → Install from repository →
   *reagent slideshow dev builds* → Look and feel → Screensaver.

5. **Select it** — Settings → Interface → Screensaver.

Step 3 works because the build writes an `index.html` into every published
directory. Kodi browses an HTTP source by parsing `<a href>` links out of the
returned HTML, and GitHub Pages serves no directory listing of its own — a
directory without an `index.html` is simply a 404, so the folder would appear
empty.

## Getting a new build

Kodi checks its repositories periodically. To pull one immediately:
Add-ons → Check for updates, then Add-ons → My add-ons → Screensaver.

## The addon ships with Kodi

`screensaver.picture.slideshow` is bundled, so the box already has an official
build. Kodi resolves a duplicate addon id by version and will not replace the
bundled one with an equal or lower version — nothing errors, the update just
never appears.

Releases here must therefore stay **ahead of the upstream version**. Upstream is
at 7.0.6, so the first release from this fork is 7.1.0.

## Cutting a release

Nothing publishes automatically. Landing a PR on `development` builds and tests
it, but does not produce an installable version.

1. On `development`, add the release notes to the top of `changelog.txt`, then
   **commit and push them**. The script starts from a clean tree that matches
   the remote, so an uncommitted edit blocks it.

   ```
   v7.1.0
   - what changed
   ```

2. Run the release script:

   ```bash
   python tools/release.py 7.1.0             # checks only, changes nothing
   python tools/release.py 7.1.0 --execute   # bump, merge, tag, push
   ```

It refuses unless the tree is clean, you are on `development`, that branch
matches the remote, CI is green on the exact commit, `changelog.txt` has notes
for the version, and the version beats `addon.xml`, the last tag, and Team
Kodi's current version. Then it bumps `addon.xml`, merges to `master`, and
pushes the tag — which is what triggers the publish workflow.

Every check runs in both modes, so a passing dry run means `--execute` will not
stop halfway.

The workflow re-checks that the tag matches `addon.xml` and sits on `master`.
That is deliberate belt-and-braces: Kodi decides whether to offer an update from
the version *inside* the zip, so a mislabelled build fails silently — the update
simply never appears, with nothing to indicate why.

## Faster loop over SSH

The repository is the convenient path, not the fast one — a build takes a
minute or two to publish. When iterating hard (verifying threaded `listdir`
inside real Kodi, or the progressive-start list swap), copy the working tree
directly:

```bash
rsync -a --delete \
  --exclude .git --exclude .venv --exclude tests --exclude tools \
  --exclude docs --exclude __pycache__ \
  ./ root@<box>:/storage/.kodi/addons/screensaver.picture.slideshow/
ssh root@<box> systemctl restart kodi
```

Path differs by platform — LibreELEC/CoreELEC use `/storage/.kodi/addons/`,
most desktop Linux `~/.kodi/addons/`.

## Gotcha

After reinstalling, the old Python process can linger until the screensaver
deactivates. Safest cycle: install → restart Kodi → preview the screensaver
via Settings → Interface → Screensaver → Preview.

## Building locally

```bash
python tools/build_repo.py public --version 7.0.999
```

Writes the same tree the workflow publishes: `addons.xml`, `addons.xml.md5`,
and one zip per addon. Useful for checking what actually ships before pushing.
