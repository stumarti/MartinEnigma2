#!/usr/bin/env bash
# Upload built images to the GitHub release for the current VERSION.
#
# Usage:  scripts/release-image.sh [image.zip ...]
# With no arguments it uploads every out/halo-image-<VERSION>-*.zip.
#
# Needs the GitHub CLI (gh), logged in with write access to the repo. The
# release itself (v<VERSION>) is normally created by the GitHub Actions
# workflow when you push the tag; this script creates it if it is missing.
set -euo pipefail

HALO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
VERSION="$(tr -d '[:space:]' < "$HALO_ROOT/VERSION")"
TAG="v$VERSION"

if [ "$#" -eq 0 ]; then
	set -- "$HALO_ROOT"/out/halo-image-"$VERSION"-*.zip
fi
for f in "$@"; do
	[ -f "$f" ] || { echo "No image found: $f" >&2; exit 1; }
done

gh release view "$TAG" >/dev/null 2>&1 || gh release create "$TAG" --title "Halo $VERSION" --notes "Halo $VERSION"

for f in "$@"; do
	( cd "$(dirname "$f")" && sha256sum "$(basename "$f")" > "$(basename "$f").sha256" )
	gh release upload "$TAG" "$f" "$f.sha256" --clobber
	echo "Uploaded $(basename "$f")"
done
