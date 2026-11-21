# Halo

A minimal Enigma2 image for the Zgemma H7S, built on openATV 8.0. It does very
little on purpose:

- plays one channel,
- slides an animated top menu down over live TV when you press **MENU**,
- updates itself from this repository's GitHub releases.

> **Status: v0.1, not yet tested on a box.** The code is checked on a PC (unit
> tests, remastering a stand-in openATV image, a compile check of the engine,
> the patch applying to openATV 8.0), but nothing here has run on real hardware
> or against a real openATV image yet. Test it in a spare multiboot slot, never
> the slot you watch TV from.

## What's in the repo

| Path | What it is |
| --- | --- |
| `meta-halo/` | Yocto layer for the OE-Alliance build: the `halo` distro, the `halo-image` recipe, the Enigma2 patch |
| `meta-halo/recipes-halo/enigma2/files/0001-…patch` | The animation engine for Enigma2 (C++) |
| `src/plugin/Halo/` | The Halo plugin (Python): top menu, channel, updater |
| `src/skin/Halo/skin.xml` | The Halo skin: top menu and a slim infobar |
| `tools/build_ipk.py` | Builds the plugin and skin packages on any PC |
| `tools/fetch_base_image.py` | Downloads the newest official openATV image for the box |
| `tools/remaster.py` | Turns that image into a Halo image (adds Halo, removes extras) |
| `image/remove.txt` | The extras removed from the openATV image |
| `scripts/build-image.sh` | Builds the full image from source with OE-Alliance (needed for the C++ engine) |
| `scripts/release-image.sh` | Uploads a built image to the GitHub release |
| `.github/workflows/release.yml` | Tests, then on a version tag publishes the packages and the image |
| `tests/` | PC tests: update logic, packaging, menu behaviour against Enigma2 stand-ins |

## Try it first on stock openATV (no image build)

The plugin and skin work on stock openATV too. Without the Halo engine the menu
animates from Python instead of C++, which is a little less smooth but looks
the same.

```sh
python3 tools/build_ipk.py --repo stumarti/MartinEnigma2
scp out/*.ipk root@BOX-IP:/tmp/
ssh root@BOX-IP 'opkg install /tmp/enigma2-plugin-*-halo_*.ipk && init 4 && init 3'
```

Then on the box:

1. Open the skin selection screen (in the main menu's setup section) and choose
   **Halo**. On stock openATV the skin is installed but not switched on
   automatically; on a Halo image it is.
2. Tune to the channel you want, open **Plugins → Halo** and press **yellow**
   ("Use this channel").
3. Press **MENU** on live TV to open **Halo Home**: the menu bar at the top,
   what's on in the middle and a row of channel tiles (with picons, if you have
   a picon set installed) along the bottom. Left and right slide the white ring
   between channels, OK watches, up moves to the menu bar. **Settings** opens
   the normal Enigma2 main menu, so nothing is out of reach.
4. **TV Guide** (in the menu, or the remote's **EPG** button) opens the Halo
   guide: left/right move between programmes, up/down between channels,
   CH+/CH− a page of channels, OK watches, green records. To get openATV's own
   guide back on the EPG button, switch it off in **Plugins → Halo**.

## Build the image on GitHub

A full Yocto build needs about 150 GB and many hours, more than GitHub's free
build machines allow. So the GitHub build starts from openATV's official image
for the H7S and changes only what Halo needs:

1. download the newest openATV 8.0 "multi" image for `zgemmah7`,
2. install the Halo plugin and skin into it,
3. remove the extras in `image/remove.txt` (anything another package still
   needs is kept, and the build log says why),
4. pack it back up as `halo-image-<version>-zgemmah7.zip`, with the same
   layout as the original, so USB flashing and Flash Image accept it.

This takes a few minutes. It runs on every version tag, and you can run it by
hand from the **Actions** tab ("Halo packages" → Run workflow), optionally with
the URL of a specific openATV image to start from. The image is attached to the
release, and a copy is kept as a workflow artifact.

What's different from a full build: the kernel, drivers and Enigma2 are
openATV's own, unchanged. That means **no C++ animation engine** in this image:
the Halo menu animates from Python instead (same look, a bit less smooth). The
engine needs the full build below.

Before you make the repository public, note that the image contains openATV's
binaries, including the box vendor's closed drivers, which you'd be
redistributing. openATV publishes these images freely, but check you're happy
with that; the updater needs the repository to be public to read its releases.

## Build the image from source (for the C++ engine)

On a Linux build PC (Ubuntu 24.04 or similar, with the packages listed in the
[OE-Alliance build environment README](https://github.com/oe-alliance/build-enviroment),
about 150 GB free and several hours for the first build):

```sh
HALO_GITHUB_REPO=stumarti/MartinEnigma2 scripts/build-image.sh
scripts/release-image.sh   # upload it to the GitHub release
```

This clones the OE-Alliance build environment into `~/halo-build`, adds
`meta-halo`, and runs `bitbake halo-image` for `MACHINE=zgemmah7`, with the
animation engine patched into Enigma2. The image lands in
`out/halo-image-<version>-zgemmah7.zip`. Upload it after the GitHub build so it
replaces the remastered one on the release.

The source-built image contains only what's needed to boot, tune and show TV,
plus the Halo plugin and skin, `ofgwrite` for flashing updates, FTP and telnet.
The MetrixHD skin is kept as a fallback for now. To add something back, add its
package to `IMAGE_INSTALL` in `meta-halo/recipes-halo/images/halo-image.bb`.

## Releases and auto-update

**Publishing a release**

1. Bump `VERSION` (for example `0.2.0`), commit, then tag and push:
   `git tag v0.2.0 && git push origin main v0.2.0`.
2. GitHub Actions runs the tests, builds the two `.ipk` packages and
   `SHA256SUMS`, and creates the release `v0.2.0` with them attached.
3. The same workflow then builds `halo-image-0.2.0-zgemmah7.zip` from the
   openATV image and attaches it, with its `.sha256`, to the release.
4. Optional: to ship the C++ engine instead, build from source (above) and run
   `scripts/release-image.sh`, which replaces the image on the release.

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

## Previews

```sh
pip install pillow
python3 tools/preview.py      # writes out/preview/home.png, guide.png, ...
```

This runs the real Home and TV Guide code against Enigma2 stand-ins with
made-up Irish channels, presses a few keys, and draws each screen where the
code left every widget. It's close to, not identical with, what the box draws,
and it's good for catching layout, overlap and colour mistakes. GitHub builds
the same previews on every push (the **halo-previews** artifact).

## Tests

```sh
python3 -m unittest discover -s tests -v
```

## Licence

GPL-2.0, like Enigma2. See `LICENSE`.
