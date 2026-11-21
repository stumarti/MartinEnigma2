# Halo

A minimal Enigma2 image for the Zgemma H7S, built on openATV 8.0. It does very
little on purpose:

- plays one channel,
- slides an animated top menu down over live TV when you press **MENU**,
- updates itself from this repository's GitHub releases.

> **Status: v0.1, not yet tested on a box.** The code is checked on a PC (unit
> tests, a compile check of the engine, the patch applying to openATV 8.0), but
> nothing here has run on real hardware yet. Test it in a spare multiboot slot,
> never the slot you watch TV from.

## What's in the repo

| Path | What it is |
| --- | --- |
| `meta-halo/` | Yocto layer for the OE-Alliance build: the `halo` distro, the `halo-image` recipe, the Enigma2 patch |
| `meta-halo/recipes-halo/enigma2/files/0001-…patch` | The animation engine for Enigma2 (C++) |
| `src/plugin/Halo/` | The Halo plugin (Python): top menu, channel, updater |
| `src/skin/Halo/skin.xml` | The Halo skin: top menu and a slim infobar |
| `tools/build_ipk.py` | Builds the plugin and skin packages on any PC |
| `scripts/build-image.sh` | Builds the full image with OE-Alliance |
| `scripts/release-image.sh` | Uploads a built image to the GitHub release |
| `.github/workflows/release.yml` | Tests, and publishes packages when you push a version tag |
| `tests/` | PC tests: update logic, packaging, menu behaviour against Enigma2 stand-ins |

## Try it first on stock openATV (no image build)

The plugin and skin work on stock openATV too. Without the Halo engine the menu
animates from Python instead of C++, which is a little less smooth but looks
the same.

```sh
python3 tools/build_ipk.py --repo YOUR-NAME/halo
scp out/*.ipk root@BOX-IP:/tmp/
ssh root@BOX-IP 'opkg install /tmp/enigma2-plugin-*-halo_*.ipk && init 4 && init 3'
```

Then on the box:

1. Open the skin selection screen (in the main menu's setup section) and choose
   **Halo**. On stock openATV the skin is installed but not switched on
   automatically; on a Halo image it is.
2. Tune to the channel you want, open **Plugins → Halo** and press **yellow**
   ("Use this channel").
3. Press **MENU** on live TV. Left and right move the white focus pill; OK opens
   the item; BACK slides the menu away. **Settings** opens the normal Enigma2
   main menu, so nothing is out of reach.

## Build the image

On a Linux build PC (Ubuntu 24.04 or similar, with the packages listed in the
[OE-Alliance build environment README](https://github.com/oe-alliance/build-enviroment),
about 150 GB free and several hours for the first build):

```sh
HALO_GITHUB_REPO=YOUR-NAME/halo scripts/build-image.sh
```

This clones the OE-Alliance build environment into `~/halo-build`, adds
`meta-halo`, and runs `bitbake halo-image` for `MACHINE=zgemmah7`. The image
lands in `out/halo-image-<version>-zgemmah7.zip`. Flash it into a free slot with
openATV's Flash Manager (copy the zip to `/media/hdd/images/` first) or by USB.

The image contains only what's needed to boot, tune and show TV, plus the Halo
plugin and skin, `ofgwrite` for flashing updates, FTP and telnet. The MetrixHD
skin is kept as a fallback for now. To add something back, add its package to
`IMAGE_INSTALL` in `meta-halo/recipes-halo/images/halo-image.bb`.

## Releases and auto-update

**Publishing a release**

1. Bump `VERSION` (for example `0.2.0`), commit, then tag and push:
   `git tag v0.2.0 && git push origin main v0.2.0`.
2. GitHub Actions runs the tests, builds the two `.ipk` packages and
   `SHA256SUMS`, and creates the release `v0.2.0` with them attached.
3. Optional, for a new image: build it (above), then run
   `scripts/release-image.sh`. It uploads
   `halo-image-0.2.0-zgemmah7.zip` and its `.sha256` to the same release (needs
   the GitHub CLI, logged in).

**What the box does**

- Two minutes after start, then once a day, it reads this repository's latest
  release from the GitHub API.
- **New packages** are downloaded, checked against `SHA256SUMS`, installed with
  `opkg`, and you're asked whether to restart the GUI. Packages without a
  checksum are never installed. In **Plugins → Halo** you can switch updates to
  "Tell me only" or "Off", and press **blue** to check now.
- **A new image** for this box is never flashed automatically. You're asked; if
  you say yes, openATV's own Flash Image screen downloads it and lets you pick
  the slot. If you say no, you won't be asked again about that version.
- Drafts and pre-releases are ignored, so you can test a release before the
  boxes see it.

The repository the box checks is baked into the packages at build time
(`--repo`, or `HALO_GITHUB_REPO` for images, or the repo name in GitHub
Actions). It can be changed in **Plugins → Halo**.

## The animation engine

The patch replaces Enigma2's old frame-stepped `eWidgetAnimation` (move only,
and only ticking in the buffered compositor that openATV leaves switched off)
with a timer-driven engine:

- moves a widget over a set time in milliseconds, with an easing curve
  (linear, ease-out cubic, ease-in-out cubic, ease-out back),
- computes each frame from the monotonic clock, so a slow frame skips ahead
  instead of stretching the animation,
- works with the compositor on or off.

From Python:

```python
from enigma import ePoint
widget.instance.animateMove(ePoint(0, -180), ePoint(0, 0), 320, 3)  # 3 = ease-out back
widget.instance.isAnimating()
widget.instance.stopAnimation(1)  # 1 = jump to the end
```

`src/plugin/Halo/Animator.py` wraps this and falls back to Python on stock
openATV.

**Buffered compositor (experimental, Phase 3 of the plan).** Create
`/etc/enigma2/halo-buffered` and restart the GUI to switch on openATV's
buffered compositor. Each window is then drawn into its own buffer, so moving a
whole window doesn't redraw its contents. It was disabled upstream for reasons
not yet known: watch memory and the `[gFBDC]` frame timing in the log, and
delete the file if anything misbehaves.

## Tests

```sh
python3 -m unittest discover -s tests -v
```

## Licence

GPL-2.0, like Enigma2. See `LICENSE`.
