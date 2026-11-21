#!/usr/bin/env python3
"""Turn an official openATV image into a Halo image, without a Yocto build.

    sudo tools/remaster.py --base openatv-8.0-...-zgemmah7_multi.zip \\
        --packages out/*.ipk --remove image/remove.txt \\
        --version 0.2.0 --out out/halo-image-0.2.0-zgemmah7.zip

Steps:
  1. unpack the image zip and its rootfs.tar.bz2,
  2. install the Halo packages into the rootfs and register them with opkg,
  3. remove the packages listed in --remove, skipping any that something
     still installed depends on,
  4. mark the rootfs as a Halo image (/etc/halo-image-version),
  5. pack it back into a zip with the same layout, so openATV's Flash Image
     screen and USB flashing treat it like any other image.

Run as root, so file owners and device nodes in the rootfs survive. The
openATV kernel and drivers are used unchanged.
"""

import argparse
import io
import os
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import time
import zipfile

OPKG_DIR = "var/lib/opkg"


# ------------------------------------------------------------ opkg database

def parseStanzas(text):
	"""Parse an opkg status/control file into a list of dicts (order kept)."""
	stanzas, current, lastKey = [], {}, None
	for line in text.splitlines():
		if not line.strip():
			if current:
				stanzas.append(current)
			current, lastKey = {}, None
		elif line[0] in " \t" and lastKey:
			current[lastKey] += "\n" + line
		elif ":" in line:
			key, value = line.split(":", 1)
			current[key.strip()] = value.strip()
			lastKey = key.strip()
	if current:
		stanzas.append(current)
	return stanzas


def formatStanza(stanza):
	return "".join("%s: %s\n" % (key, value) for key, value in stanza.items())


def dependencyNames(field):
	"""'a (>= 1), b | c, d' -> {'a', 'b', 'c', 'd'}"""
	names = set()
	for part in (field or "").split(","):
		for alternative in part.split("|"):
			name = re.sub(r"\(.*?\)", "", alternative).strip()
			if name:
				names.add(name)
	return names


class OpkgDatabase:
	def __init__(self, rootfs):
		self.rootfs = rootfs
		self.infoDir = os.path.join(rootfs, OPKG_DIR, "info")
		self.statusFile = os.path.join(rootfs, OPKG_DIR, "status")
		os.makedirs(self.infoDir, exist_ok=True)
		text = ""
		if os.path.exists(self.statusFile):
			with open(self.statusFile) as f:
				text = f.read()
		self.packages = {s["Package"]: s for s in parseStanzas(text) if "Package" in s}

	def save(self):
		with open(self.statusFile, "w") as f:
			f.write("\n".join(formatStanza(s) for s in self.packages.values()))

	def fileList(self, name):
		path = os.path.join(self.infoDir, name + ".list")
		if not os.path.exists(path):
			return []
		with open(path) as f:
			return [line.split("\t")[0].strip() for line in f if line.strip()]

	def provides(self, name):
		stanza = self.packages.get(name, {})
		return {name} | dependencyNames(stanza.get("Provides"))

	def dependents(self, names):
		"""Installed packages, outside `names`, that depend on anything in `names`."""
		offered = set()
		for name in names:
			offered |= self.provides(name)
		found = {}
		for other, stanza in self.packages.items():
			if other in names:
				continue
			wanted = dependencyNames(stanza.get("Depends")) | dependencyNames(stanza.get("Pre-Depends"))
			hit = wanted & offered
			if hit:
				found[other] = sorted(hit)
		return found

	def remove(self, requested, log=print):
		"""Remove what can be removed safely. Returns (removed, skipped)."""
		toRemove = {name for name in requested if name in self.packages}
		for name in sorted(set(requested) - toRemove):
			log("  not installed, skipped: %s" % name)
		skipped = {}
		while True:  # Drop anything still needed until the set is stable.
			needed = self.dependents(toRemove)
			blocked = set()
			for other, names in needed.items():
				for name in toRemove:
					if self.provides(name) & set(names):
						blocked.add(name)
						skipped.setdefault(name, set()).add(other)
			if not blocked:
				break
			toRemove -= blocked
		for name, users in sorted(skipped.items()):
			log("  kept %s (needed by %s)" % (name, ", ".join(sorted(users))))
		for name in sorted(toRemove):
			self._deleteFiles(name)
			for suffix in ("control", "list", "postinst", "preinst", "prerm", "postrm", "conffiles", "md5sums"):
				path = os.path.join(self.infoDir, "%s.%s" % (name, suffix))
				if os.path.exists(path):
					os.remove(path)
			del self.packages[name]
			log("  removed %s" % name)
		return sorted(toRemove), {k: sorted(v) for k, v in skipped.items()}

	def _deleteFiles(self, name):
		ownedElsewhere = set()
		for other in self.packages:
			if other != name:
				ownedElsewhere.update(self.fileList(other))
		dirs = []
		for path in self.fileList(name):
			if path in ownedElsewhere:
				continue
			full = os.path.join(self.rootfs, path.lstrip("/"))
			if os.path.islink(full) or os.path.isfile(full):
				os.remove(full)
			elif os.path.isdir(full):
				dirs.append(full)
		for full in sorted(dirs, key=len, reverse=True):
			try:
				os.rmdir(full)  # only if empty
			except OSError:
				pass

	def install(self, ipkPath, log=print):
		control, scripts, data = readIpk(ipkPath)
		stanza = parseStanzas(control)[0]
		name = stanza["Package"]
		if name in self.packages:
			self._deleteFiles(name)
		paths = []
		with tarfile.open(fileobj=io.BytesIO(data)) as tar:
			for member in tar.getmembers():
				memberName = member.name[2:] if member.name.startswith("./") else member.name
				target = os.path.normpath(memberName.lstrip("/"))
				if target in ("", ".") or target.startswith(".."):
					continue
				dest = os.path.join(self.rootfs, target)
				if member.isdir():
					os.makedirs(dest, exist_ok=True)
					os.chmod(dest, member.mode or 0o755)
				elif member.isfile():
					os.makedirs(os.path.dirname(dest), exist_ok=True)
					with tar.extractfile(member) as src, open(dest, "wb") as out:
						shutil.copyfileobj(src, out)
					os.chmod(dest, member.mode or 0o644)
				elif member.issym():
					os.makedirs(os.path.dirname(dest), exist_ok=True)
					if os.path.lexists(dest):
						os.remove(dest)
					os.symlink(member.linkname, dest)
				else:
					continue
				paths.append("/" + target)
		with open(os.path.join(self.infoDir, name + ".control"), "w") as f:
			f.write(control if control.endswith("\n") else control + "\n")
		with open(os.path.join(self.infoDir, name + ".list"), "w") as f:
			f.write("".join(p + "\n" for p in paths))
		for script, body in scripts.items():
			path = os.path.join(self.infoDir, "%s.%s" % (name, script))
			with open(path, "wb") as f:
				f.write(body)
			os.chmod(path, 0o755)
		if "postinst" in scripts:
			# Offline, like an image build: the script sees $D = the rootfs.
			env = dict(os.environ, D=self.rootfs)
			result = subprocess.run(["sh", os.path.join(self.infoDir, name + ".postinst"), "configure"], env=env, capture_output=True, text=True)
			if result.returncode != 0:
				raise RuntimeError("postinst of %s failed: %s" % (name, result.stderr))
		installed = dict(stanza)
		installed["Status"] = "install ok installed"
		installed["Installed-Time"] = str(int(time.time()))
		self.packages[name] = installed
		log("  installed %s %s" % (name, stanza.get("Version", "")))
		return name


def readIpk(path):
	"""Return (control text, {script: bytes}, data.tar bytes) from an .ipk (ar or tar.gz)."""
	with open(path, "rb") as f:
		blob = f.read()
	members = {}
	if blob.startswith(b"!<arch>\n"):
		pos = 8
		while pos + 60 <= len(blob):
			header = blob[pos:pos + 60]
			name = header[:16].decode().strip().rstrip("/")
			size = int(header[48:58].decode().strip())
			members[name] = blob[pos + 60:pos + 60 + size]
			pos += 60 + size + (size % 2)
	else:
		with tarfile.open(fileobj=io.BytesIO(blob)) as tar:
			for member in tar.getmembers():
				if member.isfile():
					members[os.path.basename(member.name)] = tar.extractfile(member).read()
	controlName = next(n for n in members if n.startswith("control.tar"))
	dataName = next(n for n in members if n.startswith("data.tar"))
	control, scripts = "", {}
	with tarfile.open(fileobj=io.BytesIO(members[controlName])) as tar:
		for member in tar.getmembers():
			if not member.isfile():
				continue
			base = os.path.basename(member.name)
			body = tar.extractfile(member).read()
			if base == "control":
				control = body.decode()
			elif base in ("preinst", "postinst", "prerm", "postrm", "conffiles"):
				scripts[base] = body
	return control, scripts, members[dataName]


def readList(path):
	names = []
	with open(path) as f:
		for line in f:
			line = line.split("#", 1)[0].strip()
			if line:
				names.append(line)
	return names


# ------------------------------------------------------------ image files

def run(cmd, **kwargs):
	print("+ " + " ".join(cmd))
	subprocess.run(cmd, check=True, **kwargs)


def bzip2Command():
	for tool in ("lbzip2", "pbzip2"):
		if shutil.which(tool):
			return tool
	return "bzip2"


def unpackRootfs(archive, dest):
	os.makedirs(dest, exist_ok=True)
	flags = ["--numeric-owner", "-p"] + (["--same-owner"] if os.geteuid() == 0 else [])
	run(["tar", "-I", bzip2Command(), "-xf", archive, "-C", dest] + flags)


def packRootfs(source, archive):
	# Same shape as the OE build: entries relative to "." in a bzip2 tar.
	run(["tar", "-I", bzip2Command(), "--numeric-owner", "-cf", archive, "-C", source, "."])


def main():
	parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
	parser.add_argument("--base", required=True, help="official image zip (the *_multi.zip)")
	parser.add_argument("--packages", nargs="*", default=[], help=".ipk files to install")
	parser.add_argument("--remove", help="file listing packages to remove, one per line")
	parser.add_argument("--version", required=True, help="Halo version written into the image")
	parser.add_argument("--out", required=True, help="output zip")
	parser.add_argument("--workdir", help="working folder (default: a temporary one)")
	args = parser.parse_args()

	work = args.workdir or tempfile.mkdtemp(prefix="halo-remaster-")
	unpacked = os.path.join(work, "zip")
	rootfs = os.path.join(work, "rootfs")
	try:
		with zipfile.ZipFile(args.base) as base:
			names = base.namelist()
			base.extractall(unpacked)
		rootfsArchives = [n for n in names if n.endswith("rootfs.tar.bz2")]
		if len(rootfsArchives) != 1:
			sys.exit("Expected exactly one rootfs.tar.bz2 in %s, found %d" % (args.base, len(rootfsArchives)))
		rootfsArchive = os.path.join(unpacked, rootfsArchives[0])
		print("Unpacking %s" % rootfsArchives[0])
		unpackRootfs(rootfsArchive, rootfs)

		db = OpkgDatabase(rootfs)
		print("Base image has %d packages" % len(db.packages))
		if args.remove:
			print("Removing extras")
			db.remove(readList(args.remove))
		print("Installing Halo")
		for ipk in args.packages:
			db.install(ipk)
		db.save()

		with open(os.path.join(rootfs, "etc", "halo-image-version"), "w") as f:
			f.write(args.version + "\n")
		print("Image now has %d packages" % len(db.packages))

		os.remove(rootfsArchive)
		packRootfs(rootfs, rootfsArchive)
		os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
		with zipfile.ZipFile(args.out, "w") as out:
			for name in names:
				path = os.path.join(unpacked, name)
				if name.endswith("/"):
					continue
				method = zipfile.ZIP_STORED if name.endswith((".bz2", ".bin", ".img")) else zipfile.ZIP_DEFLATED
				out.write(path, name, compress_type=method)
		print("Wrote %s" % args.out)
	finally:
		if not args.workdir:
			shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
	main()
