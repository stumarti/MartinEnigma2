"""Tests for the GitHub image path: picking a base image and remastering it."""

import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
import unittest
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))

import fetch_base_image  # noqa: E402
import remaster  # noqa: E402

STATUS = """Package: enigma2
Version: 8.0+git1
Depends: enigma2-plugin-skins-metrix-atv, python3-core
Status: install ok installed
Architecture: cortexa15hf-neon-vfpv4

Package: enigma2-plugin-skins-metrix-atv
Version: 1.0
Status: install ok installed
Architecture: all

Package: packagegroup-oea-distro-openatv
Version: 1.0
Depends: enigma2-plugin-extensions-filecommander, chrony, enigma2-plugin-extensions-imdb
Status: install ok installed
Architecture: h7

Package: enigma2-plugin-extensions-filecommander
Version: 2.0
Depends: enigma2
Status: install ok installed
Architecture: all

Package: enigma2-plugin-extensions-imdb
Version: 3.0
Provides: imdb-api
Status: install ok installed
Architecture: all

Package: someones-plugin
Version: 1.0
Depends: enigma2, imdb-api (>= 1.0)
Status: install ok installed
Architecture: all

Package: chrony
Version: 4.0
Status: install ok installed
Architecture: cortexa15hf-neon-vfpv4
"""

FILES = {
	"enigma2-plugin-extensions-filecommander": ["/usr/lib/enigma2/python/Plugins/Extensions/FileCommander/plugin.py"],
	"enigma2-plugin-extensions-imdb": ["/usr/lib/enigma2/python/Plugins/Extensions/IMDb/plugin.py"],
	"chrony": ["/usr/sbin/chronyd"],
}


def makeBaseImage(folder):
	rootfs = os.path.join(folder, "rootfs")
	info = os.path.join(rootfs, "var/lib/opkg/info")
	os.makedirs(info)
	os.makedirs(os.path.join(rootfs, "etc"))
	with open(os.path.join(rootfs, "var/lib/opkg/status"), "w") as f:
		f.write(STATUS)
	for package, paths in FILES.items():
		for path in paths:
			full = os.path.join(rootfs, path.lstrip("/"))
			os.makedirs(os.path.dirname(full), exist_ok=True)
			with open(full, "w") as f:
				f.write(package)
		with open(os.path.join(info, package + ".list"), "w") as f:
			f.write("".join(p + "\n" for p in paths))
	tarPath = os.path.join(folder, "rootfs.tar.bz2")
	with tarfile.open(tarPath, "w:bz2") as tar:
		tar.add(rootfs, arcname=".")
	zipPath = os.path.join(folder, "openatv-8.0-zgemmah7-20261120_multi.zip")
	with zipfile.ZipFile(zipPath, "w") as z:
		z.writestr("zgemma/h7/imageversion", "openatv-8.0.001\n")
		z.writestr("zgemma/h7/kernel.bin", b"\x00kernel")
		z.write(tarPath, "zgemma/h7/rootfs.tar.bz2")
	return zipPath


def readVersion():
	with open(os.path.join(ROOT, "VERSION")) as f:
		return f.read().strip()


class RemasterTests(unittest.TestCase):
	def setUp(self):
		self.tmp = tempfile.mkdtemp()
		self.packages = os.path.join(self.tmp, "packages")
		subprocess.run([sys.executable, os.path.join(ROOT, "tools", "build_ipk.py"), "--repo", "me/halo", "--out", self.packages], check=True, capture_output=True)

	def tearDown(self):
		shutil.rmtree(self.tmp, ignore_errors=True)

	def remasterImage(self):
		base = makeBaseImage(self.tmp)
		out = os.path.join(self.tmp, "halo-image-0.2.0-zgemmah7.zip")
		ipks = [os.path.join(self.packages, n) for n in os.listdir(self.packages) if n.endswith(".ipk")]
		result = subprocess.run([sys.executable, os.path.join(ROOT, "tools", "remaster.py"), "--base", base, "--packages"] + ipks + [
			"--remove", os.path.join(ROOT, "image", "remove.txt"), "--version", "0.2.0", "--out", out], capture_output=True, text=True)
		self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
		unpacked = os.path.join(self.tmp, "check")
		with zipfile.ZipFile(out) as z:
			self.assertEqual(sorted(z.namelist()), ["zgemma/h7/imageversion", "zgemma/h7/kernel.bin", "zgemma/h7/rootfs.tar.bz2"])
			self.assertEqual(z.read("zgemma/h7/kernel.bin"), b"\x00kernel")
			z.extract("zgemma/h7/rootfs.tar.bz2", self.tmp)
		with tarfile.open(os.path.join(self.tmp, "zgemma/h7/rootfs.tar.bz2")) as tar:
			names = tar.getnames()
			self.assertTrue(all(n == "." or n.startswith("./") for n in names), names[:5])
			tar.extractall(unpacked)
		return unpacked, result.stdout

	def test_removes_extras_but_keeps_what_is_still_needed(self):
		rootfs, log = self.remasterImage()
		db = remaster.OpkgDatabase(rootfs)
		self.assertNotIn("packagegroup-oea-distro-openatv", db.packages)
		self.assertNotIn("enigma2-plugin-extensions-filecommander", db.packages)
		self.assertFalse(os.path.exists(os.path.join(rootfs, "usr/lib/enigma2/python/Plugins/Extensions/FileCommander/plugin.py")))
		# imdb is in remove.txt, but someones-plugin needs it (through Provides).
		self.assertIn("enigma2-plugin-extensions-imdb", db.packages)
		self.assertTrue(os.path.exists(os.path.join(rootfs, "usr/lib/enigma2/python/Plugins/Extensions/IMDb/plugin.py")))
		self.assertIn("kept enigma2-plugin-extensions-imdb (needed by someones-plugin)", log)
		# Not in the list: untouched.
		self.assertIn("chrony", db.packages)
		self.assertIn("enigma2", db.packages)

	def test_installs_halo_and_marks_the_image(self):
		rootfs, log = self.remasterImage()
		db = remaster.OpkgDatabase(rootfs)
		self.assertEqual(db.packages["enigma2-plugin-extensions-halo"]["Status"], "install ok installed")
		self.assertIn("/usr/lib/enigma2/python/Plugins/Extensions/Halo/plugin.py", db.fileList("enigma2-plugin-extensions-halo"))
		self.assertTrue(os.path.exists(os.path.join(rootfs, "usr/share/enigma2/Halo/skin.xml")))
		with open(os.path.join(rootfs, "etc/enigma2/settings")) as f:
			self.assertIn("config.skin.primary_skin=Halo/skin.xml", f.read())
		with open(os.path.join(rootfs, "etc/halo-image-version")) as f:
			self.assertEqual(f.read().strip(), "0.2.0")
		with open(os.path.join(rootfs, "etc/halo-version")) as f:
			self.assertEqual(f.read().strip(), readVersion())

	def test_status_file_round_trips(self):
		stanzas = remaster.parseStanzas(STATUS)
		self.assertEqual(len(stanzas), 7)
		again = remaster.parseStanzas("\n".join(remaster.formatStanza(s) for s in stanzas))
		self.assertEqual(stanzas, again)

	def test_dependency_names(self):
		self.assertEqual(remaster.dependencyNames("a (>= 1), b | c,d"), {"a", "b", "c", "d"})


class PickImageTests(unittest.TestCase):
	def test_picks_newest_multi_zip_of_the_series(self):
		images = [
			{"category": "8.0", "name": "openatv-8.0-zgemmah7-20261101_multi.zip", "link": "https://x/a_multi.zip"},
			{"category": "8.0", "name": "openatv-8.0-zgemmah7-20261120_multi.zip", "link": "https://x/b_multi.zip"},
			{"category": "8.0", "name": "openatv-8.0-zgemmah7-20261120_recovery_emmc.zip", "link": "https://x/c.zip"},
			{"category": "7.6", "name": "openatv-7.6-zgemmah7-20261201_multi.zip", "link": "https://x/d_multi.zip"},
		]
		self.assertEqual(fetch_base_image.pickImage(images, "8.0")["link"], "https://x/b_multi.zip")
		self.assertEqual(fetch_base_image.pickImage(images, "7.6")["link"], "https://x/d_multi.zip")
		self.assertIsNone(fetch_base_image.pickImage(images, "9.0"))


if __name__ == "__main__":
	unittest.main()
