# Halo update logic with no Enigma2 dependencies, so it can be tested on a PC.
#
# Releases live on GitHub. Each release tag is the Halo version ("v0.2.0").
# A release can carry:
#   *.ipk                                 Halo packages (plugin, skin), arch "all"
#   halo-image-<version>-<machine>.zip    a full image for one box
#   <asset>.sha256 or SHA256SUMS          checksums (strongly recommended)
#
# Packages install automatically (if the user allows). Images are only
# offered: flashing always needs the user to confirm and pick a slot.

import hashlib
import json
import re
from urllib.request import Request, urlopen

USER_AGENT = "Halo-Updater/1.0 (Enigma2)"
API_LATEST = "https://api.github.com/repos/%s/releases/latest"
TIMEOUT = 20


def parseVersion(text):
	"""'v0.2.10' -> (0, 2, 10). Unknown parts sort as 0. Returns None if no digits."""
	if not text:
		return None
	numbers = re.findall(r"\d+", text.strip().lstrip("vV").split("-")[0].split("+")[0])
	if not numbers:
		return None
	parts = [int(n) for n in numbers[:4]]
	while len(parts) < 3:
		parts.append(0)
	return tuple(parts)


def isNewer(candidate, installed):
	a, b = parseVersion(candidate), parseVersion(installed)
	if a is None:
		return False
	if b is None:
		return True
	return a > b


def readVersionFile(path):
	try:
		with open(path) as f:
			return f.read().strip()
	except OSError:
		return None


def _request(url, accept="application/vnd.github+json"):
	return Request(url, headers={"User-Agent": USER_AGENT, "Accept": accept})


def fetchLatestRelease(repo, timeout=TIMEOUT):
	"""Return the latest (non-draft, non-prerelease) release as a dict."""
	with urlopen(_request(API_LATEST % repo), timeout=timeout) as response:
		return json.load(response)


def _assets(release):
	return [asset for asset in release.get("assets", []) if asset.get("name") and asset.get("browser_download_url")]


def packageAssets(release):
	return [asset for asset in _assets(release) if asset["name"].endswith(".ipk")]


def imageAsset(release, machineNames):
	"""The image zip for this box, matching any of its names (e.g. zgemmah7, h7)."""
	for name in machineNames:
		if not name:
			continue
		pattern = re.compile(r"^halo-image-.+-%s\.zip$" % re.escape(name))
		for asset in _assets(release):
			if pattern.match(asset["name"]):
				return asset
	return None


def parseChecksums(text):
	"""Parse 'sha256  filename' lines (sha256sum format) into {filename: sha256}."""
	sums = {}
	for line in text.splitlines():
		parts = line.strip().split()
		if len(parts) >= 2 and re.fullmatch(r"[0-9a-fA-F]{64}", parts[0]):
			sums[parts[-1].lstrip("*")] = parts[0].lower()
	return sums


def downloadText(url, timeout=TIMEOUT):
	with urlopen(_request(url, "application/octet-stream"), timeout=timeout) as response:
		return response.read(1024 * 1024).decode("utf-8", "replace")


def expectedChecksums(release):
	"""Collect checksums from SHA256SUMS and per-file *.sha256 assets."""
	sums = {}
	for asset in _assets(release):
		name = asset["name"]
		if name == "SHA256SUMS" or name.endswith(".sha256"):
			try:
				sums.update(parseChecksums(downloadText(asset["browser_download_url"])))
			except Exception as err:  # A missing checksum file is reported by the caller.
				print("[Halo] Could not read checksums from %s: %s" % (name, err))
	return sums


def downloadFile(url, destination, expectedSha256=None, timeout=60, progress=None):
	"""Download url to destination. Raises ValueError on a checksum mismatch."""
	digest = hashlib.sha256()
	done = 0
	with urlopen(_request(url, "application/octet-stream"), timeout=timeout) as response, open(destination, "wb") as out:
		total = int(response.headers.get("Content-Length") or 0)
		while True:
			chunk = response.read(64 * 1024)
			if not chunk:
				break
			out.write(chunk)
			digest.update(chunk)
			done += len(chunk)
			if progress:
				progress(done, total)
	actual = digest.hexdigest()
	if expectedSha256 and actual != expectedSha256.lower():
		raise ValueError("Checksum mismatch for %s" % destination)
	return actual


def planUpdate(release, installedVersion, installedImageVersion, machineNames):
	"""Decide what a release offers this box.

	Returns a dict:
	  version   the release version string
	  packages  list of ipk assets to install (empty if not newer)
	  image     the image asset to offer, or None
	"""
	tag = release.get("tag_name") or release.get("name") or ""
	plan = {"version": tag.lstrip("vV"), "packages": [], "image": None}
	if release.get("draft") or release.get("prerelease"):
		return plan
	if isNewer(tag, installedVersion):
		plan["packages"] = packageAssets(release)
	if isNewer(tag, installedImageVersion):
		plan["image"] = imageAsset(release, machineNames)
	return plan
