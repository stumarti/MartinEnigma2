#!/usr/bin/env python3
"""Download the newest official openATV image for a box.

    tools/fetch_base_image.py --machine zgemmah7 --series 8.0 --out base.zip

Reads the same image list openATV's Flash Manager uses, picks the newest
"multi" (flash online) zip of the requested release series, and downloads it.
Prints the chosen file name. Use --url to skip the list and download a
specific image instead.
"""

import argparse
import json
import os
import sys
from urllib.request import Request, urlopen

FEED = "https://images.mynonpublic.com/openatv/json/%s"
USER_AGENT = "Halo-Builder/1.0"


def listImages(machine):
	with urlopen(Request(FEED % machine, headers={"User-Agent": USER_AGENT}), timeout=30) as response:
		feed = json.load(response)
	images = []
	for category, entries in feed.items():
		for key, entry in entries.items():
			link = entry.get("link", "")
			name = os.path.basename(link) or entry.get("name", key)
			images.append({"category": category, "name": name, "link": link})
	return images


def pickImage(images, series):
	"""Newest multiboot zip of a series. The list is already for one box.
	openATV names carry the build date, so sorting names descending matches
	what Flash Manager shows first."""
	candidates = [
		image for image in images
		if image["link"].endswith(".zip")
		and "_multi" in image["name"]
		and ("-%s-" % series in image["name"] or image["category"].startswith(series))
	]
	if not candidates:
		return None
	return sorted(candidates, key=lambda image: image["name"], reverse=True)[0]


def download(url, path):
	with urlopen(Request(url, headers={"User-Agent": USER_AGENT}), timeout=120) as response, open(path, "wb") as out:
		while True:
			chunk = response.read(1024 * 1024)
			if not chunk:
				break
			out.write(chunk)


def main():
	parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
	parser.add_argument("--machine", default="zgemmah7")
	parser.add_argument("--series", default="8.0", help="openATV release series")
	parser.add_argument("--url", help="download this image instead of the newest one")
	parser.add_argument("--out", default="base.zip")
	args = parser.parse_args()

	if args.url:
		url, name = args.url, os.path.basename(args.url)
	else:
		images = listImages(args.machine)
		image = pickImage(images, args.series)
		if image is None:
			print("No openATV %s multiboot image found for %s. Available:" % (args.series, args.machine), file=sys.stderr)
			for item in images:
				print("  [%s] %s" % (item["category"], item["name"]), file=sys.stderr)
			sys.exit(1)
		url, name = image["link"], image["name"]
	print("Downloading %s" % name, file=sys.stderr)
	download(url, args.out)
	print(name)


if __name__ == "__main__":
	main()
