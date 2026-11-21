"""Tests that run on a PC: update logic, packaging, and that the plugin parses."""

import ast
import hashlib
import io
import os
import subprocess
import sys
import tarfile
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PLUGIN = os.path.join(ROOT, "src", "plugin", "Halo")
sys.path.insert(0, PLUGIN)

import updatecore  # noqa: E402


def readText(path):
	with open(path) as f:
		return f.read()


def asset(name):
	return {"name": name, "browser_download_url": "https://example.invalid/" + name}


RELEASE = {
	"tag_name": "v0.2.0",
	"draft": False,
	"prerelease": False,
	"assets": [
		asset("enigma2-plugin-extensions-halo_0.2.0_all.ipk"),
		asset("enigma2-plugin-skins-halo_0.2.0_all.ipk"),
		asset("SHA256SUMS"),
		asset("halo-image-0.2.0-zgemmah7.zip"),
		asset("halo-image-0.2.0-zgemmah7.zip.sha256"),
		asset("halo-image-0.2.0-sf8008.zip"),
	],
}


class VersionTests(unittest.TestCase):
	def test_parse(self):
		self.assertEqual(updatecore.parseVersion("v0.2.10"), (0, 2, 10))
		self.assertEqual(updatecore.parseVersion("1.0"), (1, 0, 0))
		self.assertEqual(updatecore.parseVersion("0.3.0-beta1"), (0, 3, 0))
		self.assertIsNone(updatecore.parseVersion(""))
		self.assertIsNone(updatecore.parseVersion("latest"))

	def test_newer(self):
		self.assertTrue(updatecore.isNewer("v0.2.0", "0.1.9"))
		self.assertTrue(updatecore.isNewer("v0.10.0", "0.9.0"))
		self.assertFalse(updatecore.isNewer("v0.2.0", "0.2.0"))
		self.assertFalse(updatecore.isNewer("v0.1.0", "0.2.0"))
		self.assertTrue(updatecore.isNewer("v0.1.0", None))
		self.assertFalse(updatecore.isNewer("nightly", "0.1.0"))


class PlanTests(unittest.TestCase):
	def test_newer_release_offers_packages_and_this_boxs_image(self):
		plan = updatecore.planUpdate(RELEASE, "0.1.0", "0.1.0", ["zgemmah7", "h7"])
		self.assertEqual(plan["version"], "0.2.0")
		self.assertEqual(len(plan["packages"]), 2)
		self.assertEqual(plan["image"]["name"], "halo-image-0.2.0-zgemmah7.zip")

	def test_same_version_offers_nothing(self):
		plan = updatecore.planUpdate(RELEASE, "0.2.0", "0.2.0", ["zgemmah7"])
		self.assertEqual(plan["packages"], [])
		self.assertIsNone(plan["image"])

	def test_stock_image_gets_packages_and_an_image_offer(self):
		plan = updatecore.planUpdate(RELEASE, "0.1.0", None, ["zgemmah7"])
		self.assertEqual(len(plan["packages"]), 2)
		self.assertIsNotNone(plan["image"])

	def test_other_box_gets_no_image(self):
		plan = updatecore.planUpdate(RELEASE, "0.1.0", "0.1.0", ["vuduo4k"])
		self.assertIsNone(plan["image"])

	def test_machine_name_must_match_exactly(self):
		release = dict(RELEASE, assets=[asset("halo-image-0.2.0-zgemmah7s.zip")])
		self.assertIsNone(updatecore.imageAsset(release, ["zgemmah7"]))

	def test_prerelease_is_ignored(self):
		plan = updatecore.planUpdate(dict(RELEASE, prerelease=True), "0.1.0", "0.1.0", ["zgemmah7"])
		self.assertEqual(plan["packages"], [])
		self.assertIsNone(plan["image"])


class ChecksumTests(unittest.TestCase):
	def test_parse_sha256sum_format(self):
		digest = "a" * 64
		text = "%s  file one.ipk\n%s *other.zip\nnot a line\n" % (digest, "B" * 64)
		sums = updatecore.parseChecksums(text)
		self.assertEqual(sums["one.ipk"], digest)
		self.assertEqual(sums["other.zip"], "b" * 64)

	def test_download_checks_sha256(self):
		data = b"halo" * 1000
		with tempfile.TemporaryDirectory() as tmp:
			src = os.path.join(tmp, "src.bin")
			with open(src, "wb") as f:
				f.write(data)
			url = "file://" + src
			good = hashlib.sha256(data).hexdigest()
			self.assertEqual(updatecore.downloadFile(url, os.path.join(tmp, "a"), good), good)
			with self.assertRaises(ValueError):
				updatecore.downloadFile(url, os.path.join(tmp, "b"), "0" * 64)


class PackagingTests(unittest.TestCase):
	def test_build_ipk(self):
		with tempfile.TemporaryDirectory() as out:
			subprocess.run([sys.executable, os.path.join(ROOT, "tools", "build_ipk.py"), "--repo", "me/halo", "--out", out], check=True, capture_output=True)
			names = sorted(os.listdir(out))
			version = readText(os.path.join(ROOT, "VERSION")).strip()
			self.assertIn("enigma2-plugin-extensions-halo_%s_all.ipk" % version, names)
			self.assertIn("SHA256SUMS", names)
			sums = updatecore.parseChecksums(readText(os.path.join(out, "SHA256SUMS")))
			for name, digest in sums.items():
				with open(os.path.join(out, name), "rb") as f:
					self.assertEqual(hashlib.sha256(f.read()).hexdigest(), digest)
			members = self.readAr(os.path.join(out, "enigma2-plugin-extensions-halo_%s_all.ipk" % version))
			self.assertEqual([m[0] for m in members], ["debian-binary", "control.tar.gz", "data.tar.gz"])
			with tarfile.open(fileobj=io.BytesIO(members[2][1])) as tar:
				files = tar.getnames()
				self.assertIn("./usr/lib/enigma2/python/Plugins/Extensions/Halo/plugin.py", files)
				release = tar.extractfile("./usr/lib/enigma2/python/Plugins/Extensions/Halo/release.json").read()
				self.assertIn(b"me/halo", release)

	@staticmethod
	def readAr(path):
		with open(path, "rb") as f:
			data = f.read()
		assert data.startswith(b"!<arch>\n")
		pos, members = 8, []
		while pos < len(data):
			header = data[pos:pos + 60]
			name = header[:16].decode().strip()
			size = int(header[48:58].decode().strip())
			members.append((name, data[pos + 60:pos + 60 + size]))
			pos += 60 + size + (size % 2)
		return members


class SourceTests(unittest.TestCase):
	def test_plugin_files_parse(self):
		for name in os.listdir(PLUGIN):
			if name.endswith(".py"):
				with open(os.path.join(PLUGIN, name)) as f:
					ast.parse(f.read(), name)

	def test_skin_is_well_formed(self):
		import xml.etree.ElementTree as ET
		skin = ET.parse(os.path.join(ROOT, "src", "skin", "Halo", "skin.xml")).getroot()
		self.assertEqual(skin.find("output/resolution").get("xres"), "1920")

	def test_epg_skin_uses_only_widgets_openatv_provides(self):
		import xml.etree.ElementTree as ET
		skin = ET.parse(os.path.join(ROOT, "src", "skin", "Halo", "skin.xml")).getroot()
		epg = skin.find("screen[@name='GraphicalEPG']")
		self.assertIsNotNone(epg)
		# Names created by openATV 8.0's EPGSelectionGrid (and its base classes).
		provided = {"list", "timeline_text", "bouquetlist", "timeline_now", "lab1", "primetime", "change_bouquet", "jump", "page", "number"}
		provided |= {"timeline%d" % i for i in range(6)}
		sources = {"Event", "Service", "Title", "key_red", "key_green", "key_yellow", "key_blue", "key_info", "key_menu", "key_text", "key_epg", "key_play", "global.CurrentTime"}
		for widget in epg.findall("widget"):
			if widget.get("name"):
				self.assertIn(widget.get("name"), provided)
			else:
				self.assertIn(widget.get("source"), sources)
		self.assertEqual(skin.find("parameters/parameter[@name='EPGNativeControls']").get("value"), "1")

if __name__ == "__main__":
	unittest.main()
