#!/usr/bin/env bash
# Build the Halo image with the OE-Alliance build environment.
#
# Usage:  scripts/build-image.sh            (defaults: MACHINE=zgemmah7)
#         MACHINE=zgemmah7 HALO_GITHUB_REPO=you/halo scripts/build-image.sh
#
# Needs a Linux build PC (Ubuntu 24.04 or similar) with the packages OE-Alliance
# lists in its README, roughly 150 GB free disk and several hours for the first
# build. Later builds reuse the shared state cache and are much faster.
set -euo pipefail

HALO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
WORK="${HALO_WORK:-$HOME/halo-build}"
MACHINE="${MACHINE:-zgemmah7}"
OEA_BRANCH="${OEA_BRANCH:-6.0}"
HALO_GITHUB_REPO="${HALO_GITHUB_REPO:-$(git -C "$HALO_ROOT" config --get remote.origin.url 2>/dev/null | sed -E 's#(git@github.com:|https://github.com/)##; s#\.git$##' || true)}"
HALO_GITHUB_REPO="${HALO_GITHUB_REPO:-OWNER/halo}"
VERSION="$(tr -d '[:space:]' < "$HALO_ROOT/VERSION")"

echo "Halo $VERSION for $MACHINE (releases from $HALO_GITHUB_REPO)"
mkdir -p "$WORK"
cd "$WORK"

if [ ! -d build-enviroment ]; then
	git clone -b "$OEA_BRANCH" https://github.com/oe-alliance/build-enviroment.git
fi
cd build-enviroment
make update

# The stock layer list, plus meta-halo.
LAYERS="$(make --no-print-directory --eval='halo-print-layers: ; @echo $(BBLAYERS)' halo-print-layers MACHINE="$MACHINE" DISTRO=halo)"
LAYERS="$LAYERS $HALO_ROOT/meta-halo"

# Site settings Halo needs (site.conf is created by the first make run).
make init MACHINE="$MACHINE" DISTRO=halo DISTRO_TYPE=release BBLAYERS="$LAYERS"
sed -i '/^HALO_GITHUB_REPO = /d' site.conf
echo "HALO_GITHUB_REPO = \"$HALO_GITHUB_REPO\"" >> site.conf

# MACHINE=zgemmah7 is a "machine build" name; the Makefile maps it to the
# real machine (h7), so ask it where the build directory is.
BUILD_DIR="$(make --no-print-directory --eval='halo-print-topdir: ; @echo $(TOPDIR)' halo-print-topdir MACHINE="$MACHINE" DISTRO=halo DISTRO_TYPE=release)"
# shellcheck disable=SC1091
. "$BUILD_DIR/env.source"
cd "$BUILD_DIR"
bitbake halo-image

DEPLOY="$BUILD_DIR/tmp/deploy/glibc/images"
# The flashable zip is the "_multi" one (kernel.bin + rootfs.tar.bz2).
IMAGE_ZIP="$(find "$DEPLOY" -name "halo-*_multi.zip" -printf '%T@ %p\n' | sort -n | tail -1 | cut -d' ' -f2-)"
[ -n "$IMAGE_ZIP" ] || { echo "No *_multi.zip found under $DEPLOY" >&2; exit 1; }
OUT="$HALO_ROOT/out/halo-image-$VERSION-$MACHINE.zip"
mkdir -p "$HALO_ROOT/out"
cp "$IMAGE_ZIP" "$OUT"
echo
echo "Image ready: $OUT"
echo "Publish it with: scripts/release-image.sh"
