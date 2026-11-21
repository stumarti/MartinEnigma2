#!/usr/bin/env python3
"""Build the Halo .ipk packages without a Yocto build.

The Halo plugin and skin are plain files (Python, XML), so they can be
packaged on any machine. GitHub Actions runs this for every release; you can
also run it locally:

    tools/build_ipk.py --repo you/halo --out out/

Writes:
    enigma2-plugin-extensions-halo_<version>_all.ipk
    enigma2-plugin-skins-halo_<version>_all.ipk
    SHA256SUMS
"""

import argparse
import hashlib
import io
import json
import os
import tarfile
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PLUGIN_DEST = "usr/lib/enigma2/python/Plugins/Extensions/Halo"
SKIN_DEST = "usr/share/enigma2/Halo"

SKIN_POSTINST = """#!/bin/sh
SETTINGS="$D/etc/enigma2/settings"
mkdir -p "$(dirname "$SETTINGS")"
touch "$SETTINGS"
grep -q "^config.skin.primary_skin=" "$SETTINGS" || echo "config.skin.primary_skin=Halo/skin.xml" >> "$SETTINGS"
exit 0
"""


def readVersion():
	with open(os.path.join(ROOT, "VERSION")) as f:
		return f.read().strip()


def _tarInfo(name, size, mode, mtime, isDir=False):
	info = tarfile.TarInfo(name)
	info.size = 0 if isDir else size
	info.mode = mode
	info.mtime = mtime
	info.uid = info.gid = 0
	info.uname = info.gname = "root"
	info.type = tarfile.DIRTYPE if isDir else tarfile.REGTYPE
	return info


def makeTarGz(entries, mtime):
	"""entries: list of (path, bytes_or_None_for_dir, mode). Deterministic output."""
	buf = io.BytesIO()
	with tarfile.open(fileobj=buf, mode="w:gz", format=tarfile.GNU_FORMAT) as tar:
		for path, data, mode in sorted(entries, key=lambda e: e[0]):
			if data is None:
				tar.addfile(_tarInfo("./" + path.rstrip("/") + "/", 0, mode, mtime, isDir=True))
			else:
				tar.addfile(_tarInfo("./" + path, len(data), mode, mtime), io.BytesIO(data))
	return buf.getvalue()


def makeAr(members, mtime):
	"""Minimal 'ar' archive writer (the outer format of .ipk and .deb)."""
	out = io.BytesIO()
	out.write(b"!<arch>\n")
	for name, data in members:
		header = "%-16s%-12d%-6d%-6d%-8s%-10d`\n" % (name, mtime, 0, 0, "100644", len(data))
		out.write(header.encode("ascii"))
		out.write(data)
		if len(data) % 2:
			out.write(b"\n")
	return out.getvalue()


def collectTree(sourceDir, destPrefix):
	entries = []
	dirs = set()
	for base, subdirs, files in os.walk(sourceDir):
		subdirs[:] = sorted(d for d in subdirs if d != "__pycache__")
		rel = os.path.relpath(base, sourceDir)
		for name in sorted(files):
			if name.endswith((".pyc", ".pyo")):
				continue
			path = os.path.normpath(os.path.join(destPrefix, rel, name))
			with open(os.path.join(base, name), "rb") as f:
				entries.append((path, f.read(), 0o644))
			parent = os.path.dirname(path)
			while parent and parent not in dirs:
				dirs.add(parent)
				parent = os.path.dirname(parent)
	entries.extend((d, None, 0o755) for d in dirs)
	return entries


def buildPackage(outDir, name, version, description, depends, dataEntries, mtime, postinst=None):
	fields = [
		("Package", name),
		("Version", version),
		("Architecture", "all"),
		("Section", "extra"),
		("Priority", "optional"),
		("Maintainer", "Halo"),
		("License", "GPL-2.0-only"),
		("Depends", depends),
		("Description", description),
	]
	control = "".join("%s: %s\n" % (key, value) for key, value in fields if value)
	controlEntries = [("control", control.encode(), 0o644)]
	if postinst:
		controlEntries.append(("postinst", postinst.encode(), 0o755))
	ipk = makeAr([
		("debian-binary", b"2.0\n"),
		("control.tar.gz", makeTarGz(controlEntries, mtime)),
		("data.tar.gz", makeTarGz(dataEntries, mtime)),
	], mtime)
	fileName = "%s_%s_all.ipk" % (name, version)
	with open(os.path.join(outDir, fileName), "wb") as f:
		f.write(ipk)
	return fileName


def main():
	parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
	parser.add_argument("--repo", default=os.environ.get("GITHUB_REPOSITORY", ""), help="GitHub repo owner/name that publishes releases")
	parser.add_argument("--out", default=os.path.join(ROOT, "out"), help="output folder")
	parser.add_argument("--version", default=None, help="override the version from VERSION")
	args = parser.parse_args()

	version = args.version or readVersion()
	mtime = int(os.environ.get("SOURCE_DATE_EPOCH", time.time()))
	os.makedirs(args.out, exist_ok=True)

	plugin = collectTree(os.path.join(ROOT, "src", "plugin", "Halo"), PLUGIN_DEST)
	plugin.append((PLUGIN_DEST + "/release.json", (json.dumps({"repo": args.repo, "version": version}, indent=1) + "\n").encode(), 0o644))
	plugin.append(("etc/halo-version", (version + "\n").encode(), 0o644))
	plugin.append(("etc", None, 0o755))
	skin = collectTree(os.path.join(ROOT, "src", "skin", "Halo"), SKIN_DEST)

	built = [
		buildPackage(args.out, "enigma2-plugin-extensions-halo", version, "Halo: live TV on one channel, animated top menu, GitHub updates", "enigma2, python3-json, python3-netclient", plugin, mtime),
		buildPackage(args.out, "enigma2-plugin-skins-halo", version, "Halo skin (1080p)", "enigma2", skin, mtime, postinst=SKIN_POSTINST),
	]

	with open(os.path.join(args.out, "SHA256SUMS"), "w") as sums:
		for name in built:
			with open(os.path.join(args.out, name), "rb") as f:
				sums.write("%s  %s\n" % (hashlib.sha256(f.read()).hexdigest(), name))
	for name in built:
		print(os.path.join(args.out, name))


if __name__ == "__main__":
	main()
