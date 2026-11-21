"""Smoke tests for the Halo plugin against stand-ins for Enigma2's Python API.

They can't prove the plugin works on a box, but they run every code path
(menu animation, focus movement, menu actions, the updater's decisions) and
catch typos and logic slips before anything is flashed.
"""

import builtins
import os
import sys
import types
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PLUGINS = os.path.join(ROOT, "src", "plugin")

# ---------------------------------------------------------------- stand-ins

builtins._ = lambda text: text
CLOCK = [0.0]
TIMERS = []


def module(name, **attrs):
	mod = types.ModuleType(name)
	mod.__dict__.update(attrs)
	sys.modules[name] = mod
	parent, _, child = name.rpartition(".")
	if parent:
		if parent not in sys.modules:
			module(parent)
		setattr(sys.modules[parent], child, mod)
	return mod


class ePoint:
	def __init__(self, x, y):
		self._x, self._y = x, y

	def x(self):
		return self._x

	def y(self):
		return self._y


class eTimer:
	def __init__(self):
		self.callback = []
		self.active = False

	def start(self, ms, singleShot=False):
		self.ms, self.singleShot, self.active = ms, singleShot, True
		self.due = CLOCK[0] + ms / 1000.0
		if self not in TIMERS:
			TIMERS.append(self)

	def startLongTimer(self, seconds):
		self.start(seconds * 1000, True)

	def stop(self):
		self.active = False


def advance(seconds, step=0.016):
	"""Move the fake clock forward, firing timers as they fall due."""
	end = CLOCK[0] + seconds
	while CLOCK[0] < end:
		CLOCK[0] = min(end, CLOCK[0] + step)
		for timer in list(TIMERS):
			if timer.active and timer.due <= CLOCK[0] + 1e-9:
				if timer.singleShot:
					timer.active = False
				else:
					timer.due += timer.ms / 1000.0
				for fn in list(timer.callback):
					fn()


class FakeWidget:
	"""A widget with move()/position() but no native animation (stock openATV)."""

	def __init__(self, x=0, y=0):
		self.pos = (x, y)
		self.moves = 0

	def move(self, point):
		self.pos = (point.x(), point.y())
		self.moves += 1

	def position(self):
		return ePoint(*self.pos)

	def setForegroundColor(self, colour):
		self.colour = colour

	def invalidate(self):
		pass


class NativeWidget(FakeWidget):
	"""A widget from a Halo image: the C++ engine provides animateMove()."""

	def animateMove(self, start, end, ms, curve):
		self.native = (start.x(), start.y(), end.x(), end.y(), ms, curve)
		self.pos = (end.x(), end.y())

	def stopAnimation(self, jumpToEnd):
		self.stopped = jumpToEnd


module("enigma", ePoint=ePoint, eTimer=eTimer, gRGB=lambda v: v, eServiceReference=lambda ref: types.SimpleNamespace(ref=ref, toString=lambda: ref))


class Label:
	def __init__(self, text=""):
		self.text = text
		self.instance = None


class ActionMap:
	def __init__(self, contexts, actions, prio=0):
		self.actions = actions


class Screen(dict):
	def __init__(self, session, enableHelp=False):
		dict.__init__(self)
		self.session = session
		self.onLayoutFinish, self.onClose = [], []
		self.instance = None
		self.closed = "not closed"

	def close(self, *result):
		self.closed = result[0] if result else None
		for fn in self.onClose:
			fn()

	def layout(self, widgetClass=FakeWidget):
		"""What Enigma2 does when it applies the skin: create the instances."""
		self.instance = widgetClass(0, 0)
		positions = {"focus": (360, 52), "brand": (136, 32)}
		for i in range(6):
			positions["item%d" % i] = (360 + i * 216, 52)
		for name, pos in positions.items():
			self[name].instance = widgetClass(*pos)
		for fn in self.onLayoutFinish:
			fn()


class ConfigItem:
	def __init__(self, default=None, **kwargs):
		self.value = default
		self.saved = 0

	def save(self):
		self.saved += 1


class ConfigSubsection:
	pass


config = types.SimpleNamespace(plugins=types.SimpleNamespace(), tv=types.SimpleNamespace(lastservice=ConfigItem("")))
NOTIFICATIONS = []
module("Components.ActionMap", ActionMap=ActionMap)
module("Components.Label", Label=Label)
module("Components.config", config=config, ConfigSubsection=ConfigSubsection, ConfigText=ConfigItem, ConfigInteger=ConfigItem, ConfigSelection=ConfigItem, getConfigListEntry=lambda *a: a)
module("Components.SystemInfo", BoxInfo=types.SimpleNamespace(getItem=lambda key: {"machinebuild": "zgemmah7", "BoxName": "zgemmah7", "model": "h7"}.get(key)))
module("Components.ConfigList", ConfigListScreen=object)
module("Components.Sources.StaticText", StaticText=Label)
module("Screens.Screen", Screen=Screen)
module("Screens.MessageBox", MessageBox=types.SimpleNamespace(TYPE_INFO=0, TYPE_ERROR=1, TYPE_YESNO=2))
module("Screens.PluginBrowser", PluginBrowser="PluginBrowser")
module("Screens.FlashManager", FlashImage="FlashImage")
module("Screens.Standby", QUIT_RESTART=3, TryQuitMainloop="TryQuitMainloop")
module("ServiceReference", ServiceReference=None)
module("Tools.Notifications",
	AddPopup=lambda text, *a, **k: NOTIFICATIONS.append(("popup", text)),
	AddNotificationWithCallback=lambda fn, screen, text, *a, **k: NOTIFICATIONS.append(("ask", text, fn)))


class Plugin:
	WHERE_SESSIONSTART, WHERE_PLUGINMENU = 8, 3

	def __init__(self, **kwargs):
		self.kwargs = kwargs


module("Plugins.Plugin", PluginDescriptor=Plugin)


class InfoBarMenu:
	def showMainMenu(self):
		self.openedMainMenu = True


module("Screens.InfoBarGenerics", InfoBarMenu=InfoBarMenu)


class Deferred:
	def __init__(self, fn, *args):
		try:
			self.result, self.ok = fn(*args), True
		except Exception as err:
			self.result, self.ok = err, False

	def addCallback(self, fn, *args):
		if self.ok:
			fn(self.result, *args)
		return self

	def addErrback(self, fn, *args):
		if not self.ok:
			fn(types.SimpleNamespace(getErrorMessage=lambda: str(self.result)), *args)
		return self


module("twisted.internet.threads", deferToThread=lambda fn, *a: Deferred(fn, *a))

sys.path.insert(0, PLUGINS)
from Halo import Animator, plugin, updatecore  # noqa: E402
from Halo import TopMenu, Updater  # noqa: E402

Animator.monotonic = lambda: CLOCK[0]


class Session:
	def __init__(self):
		self.opened = []
		self.nav = types.SimpleNamespace(getCurrentlyPlayingServiceReference=lambda: None, playService=lambda ref: self.opened.append(("play", ref.ref)))

	def open(self, screen, *args):
		self.opened.append((screen,) + args)

	def openWithCallback(self, callback, screen, *args):
		self.opened.append((screen,) + args)
		self.lastCallback = callback


# ---------------------------------------------------------------- tests

class AnimatorTests(unittest.TestCase):
	def test_python_fallback_reaches_target_on_time(self):
		widget, done = FakeWidget(0, -180), []
		anim = Animator.Animator()
		anim.move(widget, (0, -180), (0, 0), 300, Animator.EASE_OUT_CUBIC, onDone=lambda: done.append(CLOCK[0]))
		advance(0.15)
		self.assertTrue(-180 < widget.pos[1] < 0, widget.pos)
		advance(0.2)
		self.assertEqual(widget.pos, (0, 0))
		self.assertEqual(len(done), 1)
		self.assertGreater(widget.moves, 10)

	def test_cancel_jumps_to_end_without_callback(self):
		widget, done = FakeWidget(), []
		anim = Animator.Animator()
		anim.move(widget, (0, 0), (100, 0), 500, onDone=lambda: done.append(1))
		advance(0.1)
		anim.cancel(widget)
		advance(1.0)
		self.assertEqual(widget.pos, (100, 0))
		self.assertEqual(done, [])

	def test_native_engine_is_used_on_halo_images(self):
		widget, done = NativeWidget(), []
		Animator.Animator().move(widget, (0, -180), (0, 0), 320, Animator.EASE_OUT_BACK, onDone=lambda: done.append(1))
		self.assertEqual(widget.native, (0, -180, 0, 0, 320, Animator.EASE_OUT_BACK))
		advance(0.4)
		self.assertEqual(done, [1])

	def test_ease_curves_start_and_end_in_place(self):
		for curve in range(4):
			self.assertEqual(Animator.ease(curve, 0.0), 0.0)
			self.assertEqual(Animator.ease(curve, 1.0), 1.0)
		self.assertGreater(max(Animator.ease(Animator.EASE_OUT_BACK, t / 100) for t in range(100)), 1.0)


class TopMenuTests(unittest.TestCase):
	def openMenu(self, widgetClass=FakeWidget):
		menu = TopMenu.HaloTopMenu(Session())
		menu.layout(widgetClass)
		return menu

	def test_slides_in_moves_focus_and_returns_choice(self):
		menu = self.openMenu()
		self.assertEqual(menu.instance.pos, (0, -180))
		advance(0.4)
		self.assertEqual(menu.instance.pos, (0, 0))
		menu["actions"].actions["right"]()
		menu["actions"].actions["right"]()
		advance(0.3)
		self.assertEqual(menu["focus"].instance.pos, (360 + 2 * 216, 52))
		self.assertEqual(menu["item2"].instance.colour, TopMenu.INK_ON_FOCUS)
		self.assertEqual(menu["item0"].instance.colour, TopMenu.INK)
		menu["actions"].actions["ok"]()
		self.assertEqual(menu.closed, "not closed")  # waits for the slide out
		advance(0.3)
		self.assertEqual(menu.instance.pos, (0, -180))
		self.assertEqual(menu.closed, "recordings")

	def test_left_wraps_and_back_closes_with_no_choice(self):
		menu = self.openMenu()
		menu["actions"].actions["left"]()
		advance(0.3)
		self.assertEqual(menu.index, 5)
		menu["actions"].actions["cancel"]()
		menu["actions"].actions["ok"]()  # ignored while closing
		advance(0.3)
		self.assertIsNone(menu.closed)

	def test_works_with_the_native_engine(self):
		menu = self.openMenu(NativeWidget)
		menu["actions"].actions["right"]()
		self.assertEqual(menu["focus"].instance.native[2], 360 + 216)
		menu["actions"].actions["ok"]()
		advance(0.3)
		self.assertEqual(menu.closed, "guide")


class PluginTests(unittest.TestCase):
	def test_session_start_hooks_menu_and_tunes_channel(self):
		config.plugins.halo.service.value = "1:0:19:2BC:2:2174:EEEE0000:0:0:0:"
		session = Session()
		plugin.sessionstart(0, session=session)
		self.assertEqual(config.tv.lastservice.value, config.plugins.halo.service.value)
		self.assertIs(InfoBarMenu.showMainMenu, plugin.openTopMenu)
		advance(3.1)
		self.assertIn(("play", config.plugins.halo.service.value), session.opened)
		infobar = InfoBarMenu()
		infobar.session = session
		infobar.showMainMenu()
		self.assertIs(session.opened[-1][0], TopMenu.HaloTopMenu)
		session.lastCallback("settings")
		self.assertTrue(infobar.openedMainMenu)
		session.lastCallback("apps")
		self.assertEqual(session.opened[-1], ("PluginBrowser",))
		config.plugins.halo.service.value = ""


class UpdaterTests(unittest.TestCase):
	def setUp(self):
		NOTIFICATIONS.clear()
		config.plugins.halo.repo.value = "me/halo"
		config.plugins.halo.autoupdate.value = "install"
		config.plugins.halo.skipimage.value = ""
		self.release = {"tag_name": "v9.0.0", "assets": [
			{"name": "enigma2-plugin-extensions-halo_9.0.0_all.ipk", "browser_download_url": "u1"},
			{"name": "SHA256SUMS", "browser_download_url": "u2"},
			{"name": "halo-image-9.0.0-zgemmah7.zip", "browser_download_url": "u3"},
		]}
		self.downloads, self.installs = [], []
		self.saved = (updatecore.fetchLatestRelease, updatecore.downloadText, updatecore.downloadFile, Updater.subprocess.run, Updater.installedVersion, Updater.installedImageVersion)
		updatecore.fetchLatestRelease = lambda repo: self.release
		updatecore.downloadText = lambda url: "%s  enigma2-plugin-extensions-halo_9.0.0_all.ipk\n" % ("c" * 64)
		updatecore.downloadFile = lambda url, path, sha: self.downloads.append((url, sha))
		Updater.subprocess.run = lambda cmd, **k: (self.installs.append(cmd), types.SimpleNamespace(returncode=0, stdout="", stderr=""))[1]
		Updater.installedVersion = lambda: "0.1.0"
		Updater.installedImageVersion = lambda: "0.1.0"

	def tearDown(self):
		(updatecore.fetchLatestRelease, updatecore.downloadText, updatecore.downloadFile, Updater.subprocess.run, Updater.installedVersion, Updater.installedImageVersion) = self.saved

	def test_installs_packages_then_offers_restart_and_image(self):
		updater = Updater.HaloUpdater(Session())
		updater.check(manual=False)
		self.assertEqual(self.downloads, [("u1", "c" * 64)])
		self.assertEqual(self.installs[0][:3], ["opkg", "install", "--force-reinstall"])
		asks = [n for n in NOTIFICATIONS if n[0] == "ask"]
		self.assertEqual(len(asks), 2)
		self.assertIn("updated to 9.0.0", asks[0][1])
		asks[1][2](False)  # say no to the image
		self.assertEqual(config.plugins.halo.skipimage.value, "9.0.0")
		NOTIFICATIONS.clear()
		updater.check(manual=False)
		self.assertFalse(any("image" in n[1] for n in NOTIFICATIONS if n[0] == "ask"))

	def test_refuses_packages_without_checksums(self):
		updatecore.downloadText = lambda url: ""
		Updater.HaloUpdater(Session()).check(manual=False)
		self.assertEqual(self.installs, [])
		self.assertTrue(any("no checksum" in n[1] for n in NOTIFICATIONS if n[0] == "popup"))

	def test_notify_mode_does_not_install(self):
		config.plugins.halo.autoupdate.value = "notify"
		Updater.HaloUpdater(Session()).check(manual=False)
		self.assertEqual(self.installs, [])
		self.assertTrue(any("is available" in n[1] for n in NOTIFICATIONS if n[0] == "popup"))

	def test_accepting_the_image_opens_flash_image(self):
		session = Session()
		Updater.HaloUpdater(session).check(manual=True)
		image = [n for n in NOTIFICATIONS if n[0] == "ask" and "image" in n[1]][0]
		image[2](True)
		self.assertEqual(session.opened[-1], ("FlashImage", "halo-image-9.0.0-zgemmah7.zip", "u3"))

	def test_unset_repo_is_reported(self):
		config.plugins.halo.repo.value = "OWNER/halo"
		Updater.HaloUpdater(Session()).check(manual=True)
		self.assertTrue(any("No Halo release repository" in n[1] for n in NOTIFICATIONS))


if __name__ == "__main__":
	unittest.main()
