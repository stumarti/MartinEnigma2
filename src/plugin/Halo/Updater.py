# Halo updater: checks the GitHub releases of the Halo repository.
#
# - New Halo packages (.ipk) are downloaded, checked against the release's
#   SHA256 checksums and installed with opkg. Then the user is asked whether
#   to restart the GUI.
# - A new Halo image for this box is never flashed automatically. The user is
#   asked, and openATV's own FlashImage screen downloads it and lets them pick
#   the multiboot slot.

import json
import subprocess
from os import makedirs
from os.path import dirname, join
from shutil import rmtree
from time import time

from enigma import eTimer
from twisted.internet.threads import deferToThread

from Components.config import config
from Components.SystemInfo import BoxInfo
from Screens.MessageBox import MessageBox
from Tools.Notifications import AddNotificationWithCallback, AddPopup

from . import updatecore

PLUGIN_DIR = dirname(__file__)
VERSION_FILE = "/etc/halo-version"
IMAGE_VERSION_FILE = "/etc/halo-image-version"
DOWNLOAD_DIR = "/tmp/halo-update"
FIRST_CHECK_DELAY = 120  # seconds after the GUI starts
CHECK_INTERVAL = 24 * 3600  # seconds between automatic checks


def releaseRepo():
	"""The GitHub repo (owner/name) baked in at build time, unless overridden."""
	if config.plugins.halo.repo.value.strip():
		return config.plugins.halo.repo.value.strip()
	try:
		with open(join(PLUGIN_DIR, "release.json")) as f:
			return json.load(f).get("repo", "")
	except (OSError, ValueError):
		return ""


def installedVersion():
	return updatecore.readVersionFile(VERSION_FILE) or "0"


def installedImageVersion():
	return updatecore.readVersionFile(IMAGE_VERSION_FILE)


def machineNames():
	return [BoxInfo.getItem(key) for key in ("machinebuild", "BoxName", "model")]


class HaloUpdater:
	def __init__(self, session):
		self.session = session
		self.busy = False
		self.timer = eTimer()
		self.timer.callback.append(self.autoCheck)
		self.timer.startLongTimer(FIRST_CHECK_DELAY)

	def autoCheck(self):
		self.timer.startLongTimer(CHECK_INTERVAL)
		if config.plugins.halo.autoupdate.value == "off":
			return
		if time() - config.plugins.halo.lastcheck.value < CHECK_INTERVAL - 600:
			return
		self.check(manual=False)

	def check(self, manual=True):
		if self.busy:
			if manual:
				AddPopup(_("Halo is already checking for updates."), MessageBox.TYPE_INFO, 5)
			return
		repo = releaseRepo()
		if not repo or repo.startswith("OWNER/"):
			if manual:
				AddPopup(_("No Halo release repository is set. Set it in Halo settings."), MessageBox.TYPE_ERROR, 10)
			return
		self.busy = True
		install = manual or config.plugins.halo.autoupdate.value == "install"
		d = deferToThread(self.work, repo, install)
		d.addCallback(self.finished, manual)
		d.addErrback(self.failed, manual)

	# Runs in a worker thread: no GUI calls here.
	def work(self, repo, install):
		release = updatecore.fetchLatestRelease(repo)
		plan = updatecore.planUpdate(release, installedVersion(), installedImageVersion(), machineNames())
		result = {"version": plan["version"], "installed": [], "image": plan["image"], "error": None, "available": bool(plan["packages"])}
		if plan["packages"] and install:
			sums = updatecore.expectedChecksums(release)
			rmtree(DOWNLOAD_DIR, ignore_errors=True)
			makedirs(DOWNLOAD_DIR)
			files = []
			for asset in plan["packages"]:
				expected = sums.get(asset["name"])
				if not expected:
					result["error"] = _("Release %s has no checksum for %s, so it was not installed.") % (plan["version"], asset["name"])
					return result
				path = join(DOWNLOAD_DIR, asset["name"])
				updatecore.downloadFile(asset["browser_download_url"], path, expected)
				files.append(path)
			proc = subprocess.run(["opkg", "install", "--force-reinstall"] + files, capture_output=True, text=True, timeout=600)
			print("[Halo] opkg: %s %s" % (proc.stdout, proc.stderr))
			if proc.returncode != 0:
				result["error"] = _("Installing the update failed:\n%s") % (proc.stderr.strip() or proc.stdout.strip())[-400:]
				return result
			result["installed"] = [asset["name"] for asset in plan["packages"]]
		return result

	def finished(self, result, manual):
		self.busy = False
		config.plugins.halo.lastcheck.value = int(time())
		config.plugins.halo.lastcheck.save()
		if result["error"]:
			AddPopup(result["error"], MessageBox.TYPE_ERROR, 15)
		elif result["installed"]:
			AddNotificationWithCallback(self.restartAnswer, MessageBox, _("Halo was updated to %s.\nRestart the user interface now?") % result["version"], MessageBox.TYPE_YESNO)
		elif result["available"]:
			AddPopup(_("Halo %s is available. Open Halo settings to install it.") % result["version"], MessageBox.TYPE_INFO, 10)
		if result["image"] and (manual or config.plugins.halo.skipimage.value != result["version"]):
			image, version = result["image"], result["version"]
			AddNotificationWithCallback(lambda answer: self.flashAnswer(answer, image, version), MessageBox, _("A new Halo image (%s) is available for this box.\nDownload it and choose a slot to flash it to?") % result["version"], MessageBox.TYPE_YESNO, default=False)
		elif manual and not result["installed"] and not result["error"] and not result["available"]:
			AddPopup(_("Halo is up to date (%s).") % installedVersion(), MessageBox.TYPE_INFO, 5)

	def failed(self, failure, manual):
		self.busy = False
		print("[Halo] Update check failed: %s" % failure.getErrorMessage())
		if manual:
			AddPopup(_("Could not check for Halo updates:\n%s") % failure.getErrorMessage(), MessageBox.TYPE_ERROR, 10)

	def restartAnswer(self, answer):
		if answer:
			from Screens.Standby import QUIT_RESTART, TryQuitMainloop
			self.session.open(TryQuitMainloop, QUIT_RESTART)

	def flashAnswer(self, answer, image, version):
		if not answer:
			# Don't ask again for this version unless the user checks manually.
			config.plugins.halo.skipimage.value = version
			config.plugins.halo.skipimage.save()
			return
		from Screens.FlashManager import FlashImage
		self.session.open(FlashImage, image["name"], image["browser_download_url"])
