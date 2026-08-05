# Installing builds on a Kodi box

Tagged releases publish a Kodi repository to GitHub Pages. Install the
repository addon once and Kodi handles updates from then on.

**These are not the official addon.** They replace it, share its id, and are
not reviewed by Team Kodi.

## One-time setup

1. **Enable unknown sources** — Settings → System → Add-ons → Unknown sources.

2. **Get the repository zip onto the box.** It lives at a stable URL:

   ```
   https://reagent.github.io/screensaver.picture.slideshow/repository.reagent.slideshow/repository.reagent.slideshow-1.0.0.zip
   ```

   LibreELEC / CoreELEC:

   ```bash
   ssh root@<box> 'wget -P /storage/downloads/ https://reagent.github.io/screensaver.picture.slideshow/repository.reagent.slideshow/repository.reagent.slideshow-1.0.0.zip'
   ```

   Android or Fire TV: download it in a browser on the device.

3. **Install it** — Add-ons → Install from zip file → pick the zip.

4. **Install the screensaver** — Add-ons → Install from repository →
   *reagent slideshow dev builds* → Look and feel → Screensaver.

## Getting a new build

Kodi checks its repositories periodically. To pull one immediately:
Add-ons → Check for updates, then Add-ons → My add-ons → Screensaver.

## Cutting a release

Nothing publishes automatically. Landing a PR on `development` builds and tests
it, but does not produce an installable version.

1. Bump `version` in `addon.xml` on `development`, and add a `changelog.txt`
   entry.
2. Merge `development` into `master`.
3. Tag it and push:

   ```bash
   git checkout master && git pull
   git tag v7.1.0 && git push origin v7.1.0
   ```

The tag must match the version in `addon.xml`, and must sit on `master` — the
publish workflow fails loudly on either mismatch rather than shipping something
mislabelled. Kodi decides whether to offer an update from the version *inside*
the zip, so a zip whose declared version disagrees with its tag fails silently:
the update simply never appears.

Kodi offers an update only when the version increases, so releases must rise
monotonically.

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
