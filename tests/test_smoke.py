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

	def setBackgroundColor(self, colour):
		self.background = colour

	def resize(self, size):
		self.size = (size.width(), size.height())

	def setPixmapFromFile(self, path):
		self.pixmap = path

	def invalidate(self):
		pass


class NativeWidget(FakeWidget):
	"""A widget from a Halo image: the C++ engine provides animateMove()."""

	def animateMove(self, start, end, ms, curve):
		self.native = (start.x(), start.y(), end.x(), end.y(), ms, curve)
		self.pos = (end.x(), end.y())

	def stopAnimation(self, jumpToEnd):
		self.stopped = jumpToEnd


class eSize:
	def __init__(self, w, h):
		self._w, self._h = w, h

	def width(self):
		return self._w

	def height(self):
		return self._h


class FakeRef:
	isDirectory, isMarker = 1, 2

	def __init__(self, ref, flags=0):
		self.ref, self.flags = ref, flags

	def toString(self):
		return self.ref

	def valid(self):
		return bool(self.ref)


EPG = {}  # service ref string -> list of (id, begin, duration, title, short, extended)


class FakeEPGCache:
	@staticmethod
	def getInstance():
		return FakeEPGCache

	@staticmethod
	def lookupEvent(query):
		ref, begin, minutes = query[1][0], query[1][2], query[1][3]
		end = begin + minutes * 60
		return [e for e in EPG.get(ref, []) if e[1] < end and e[1] + e[2] > begin]


def eServiceReference(ref):
	return FakeRef(ref)


eServiceReference.isDirectory, eServiceReference.isMarker = 1, 2

module("enigma", ePoint=ePoint, eSize=eSize, eTimer=eTimer, gRGB=lambda v: v, eServiceReference=eServiceReference, eEPGCache=FakeEPGCache, eServiceCenter=None)


class Label:
	def __init__(self, text=""):
		self.text = text
		self.instance = None
		self.visible = True

	def setText(self, text):
		self.text = text

	def show(self):
		self.visible = True

	def hide(self):
		self.visible = False


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
		for name, component in self.items():
			if isinstance(component, Label) and component.instance is None:  # Pixmap is a Label here
				component.instance = widgetClass(*positions.get(name, (0, 0)))
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
class Pixmap(Label):
	pass


PICONS = {}  # ref string -> picon path
module("Components.Label", Label=Label)
module("Components.Pixmap", Pixmap=Pixmap)
module("Components.Renderer.Picon", getPiconName=lambda ref: PICONS.get(ref, ""))
module("Components.config", config=config, ConfigSubsection=ConfigSubsection, ConfigText=ConfigItem, ConfigInteger=ConfigItem, ConfigSelection=ConfigItem, ConfigYesNo=ConfigItem, getConfigListEntry=lambda *a: a)
module("Components.SystemInfo", BoxInfo=types.SimpleNamespace(getItem=lambda key: {"machinebuild": "zgemmah7", "BoxName": "zgemmah7", "model": "h7"}.get(key)))
module("Components.ConfigList", ConfigListScreen=object)
module("Components.Sources.StaticText", StaticText=Label)
module("Screens.Screen", Screen=Screen)
module("Screens.MessageBox", MessageBox=types.SimpleNamespace(TYPE_INFO=0, TYPE_ERROR=1, TYPE_YESNO=2))
module("Screens.PluginBrowser", PluginBrowser="PluginBrowser")
module("Screens.FlashManager", FlashImage="FlashImage")
module("Screens.Standby", QUIT_RESTART=3, TryQuitMainloop="TryQuitMainloop")
class ServiceReference:
	def __init__(self, ref):
		self.ref = ref


class FakeTimer:
	def __init__(self, serviceRef, begin, end, name, description, eit, **kwargs):
		self.service_ref, self.begin, self.end, self.name, self.eit = serviceRef, begin, end, name, eit


class FakeRecordTimers:
	def __init__(self):
		self.timer_list = []

	def record(self, entry):
		self.timer_list.append(entry)

	def removeEntry(self, entry):
		self.timer_list.remove(entry)


module("ServiceReference", ServiceReference=ServiceReference)
module("RecordTimer", RecordTimerEntry=FakeTimer)
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


class InfoBarEPG:
	def openGraphEPG(self):
		self.openedStockGuide = True


module("Screens.InfoBarGenerics", InfoBarMenu=InfoBarMenu, InfoBarEPG=InfoBarEPG)
module("Screens.InfoBar", InfoBar=types.SimpleNamespace(instance=None))


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
from Halo import Chrome, Guide, Home, Updater  # noqa: E402

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


def makeServices(count, extraNames=()):
	"""Fake channels with programmes every 30 or 45 minutes around now."""
	import time as _time
	now = _time.time()
	half = now - now % 1800
	EPG.clear()
	services = []
	names = ["Channel %d" % (i + 1) for i in range(count)] + list(extraNames)
	for i, name in enumerate(names):
		ref = "1:0:1:%X:0:0:0:0:0:0:" % (i + 1)
		services.append((FakeRef(ref), name))
		length = 1800 if i % 2 == 0 else 2700
		events, begin, n = [], half - 3 * 3600, 0
		while begin < half + 6 * 3600:
			events.append((1000 * i + n, begin, length, "Show %d-%d" % (i, n), "short %d" % n, "long text %d" % n))
			begin += length
			n += 1
		EPG[ref] = events
	return services, now


class HomeTests(unittest.TestCase):
	def setUp(self):
		self.services, self.now = makeServices(10)
		PICONS.clear()

	def openHome(self, start=3, widgetClass=FakeWidget):
		home = Home.HaloHome(Session(), self.services, start, self.services[start][0].toString())
		home.layout(widgetClass)
		advance(0.4)
		return home

	def ringSlot(self, home):
		x = home["ring"].instance.pos[0] + Home.RING
		return (x - Home.TILE_X0) / float(Home.TILE_STEP)

	def test_opens_on_the_channel_being_watched(self):
		home = self.openHome(start=3)
		self.assertEqual(home.instance.pos, (0, 0))
		self.assertEqual(home.focus, 3)
		self.assertEqual(home.first, 2)
		self.assertEqual(self.ringSlot(home), 1)
		self.assertIn("Channel 4", home["meta"].text)
		self.assertTrue(home["title"].text.startswith("Show 3-"))
		self.assertIn("min left", home["left"].text)
		self.assertTrue(home["next"].text)

	def test_tiles_show_picons_or_names(self):
		import tempfile
		with tempfile.NamedTemporaryFile(suffix=".png") as picon:
			PICONS[self.services[3][0].toString()] = picon.name
			home = self.openHome(start=3)
			self.assertTrue(home["picon1"].visible)
			self.assertEqual(home["picon1"].instance.pixmap, picon.name)
			self.assertFalse(home["name1"].visible)
		self.assertFalse(home["picon0"].visible)
		self.assertEqual(home["name0"].text, "Channel 3")
		self.assertEqual(home["number0"].text, "3")
		self.assertTrue(home["show0"].text.startswith("Show 2-"))

	def test_ring_slides_then_the_row_scrolls(self):
		home = self.openHome(start=3)
		for _ in range(3):
			home["actions"].actions["right"]()
		advance(0.3)
		self.assertEqual(home.focus, 6)
		self.assertEqual(self.ringSlot(home), 4)
		home["actions"].actions["right"]()
		home["actions"].actions["right"]()  # past the last tile: the row moves
		advance(0.3)
		self.assertEqual(home.focus, 8)
		self.assertEqual(home.first, 3)
		self.assertEqual(self.ringSlot(home), 5)
		self.assertEqual(home["name5"].text, "Channel 9")
		self.assertIn("Channel 9", home["meta"].text)

	def test_wraps_from_the_last_channel_to_the_first(self):
		home = self.openHome(start=9)
		home["actions"].actions["right"]()
		advance(0.3)
		self.assertEqual((home.focus, home.first), (0, 0))
		self.assertEqual(self.ringSlot(home), 0)

	def test_ok_watches_the_chosen_channel(self):
		home = self.openHome(start=3)
		home["actions"].actions["left"]()
		home["actions"].actions["ok"]()
		advance(0.3)
		self.assertEqual(home.closed[0], "watch")
		self.assertEqual(home.closed[1].toString(), self.services[2][0].toString())

	def test_menu_bar_pill_slides_and_text_follows(self):
		home = self.openHome()
		home["actions"].actions["up"]()
		home["actions"].actions["right"]()
		home["actions"].actions["right"]()
		advance(0.06)
		dark = [i for i in range(6) if home["nav%d" % i].instance.colour == Chrome.INK_DARK]
		self.assertEqual(len(dark), 1)
		advance(0.3)
		self.assertEqual(home["navPill"].instance.pos, (Chrome.navX(2), Chrome.NAV_Y))
		self.assertEqual(home["nav2"].instance.colour, Chrome.INK_DARK)
		home["actions"].actions["ok"]()
		advance(0.3)
		self.assertEqual(home.closed, ("menu", "recordings"))

	def test_down_returns_to_the_channel_row(self):
		home = self.openHome()
		home["actions"].actions["up"]()
		home["actions"].actions["right"]()
		home["actions"].actions["down"]()
		advance(0.3)
		self.assertEqual(home.zone, "channels")
		self.assertEqual(home["navPill"].instance.pos[0], Chrome.navX(0))
		home["actions"].actions["right"]()
		self.assertEqual(home.focus, 4)

	def test_plus_one_prompt_when_the_start_was_missed(self):
		services, now = makeServices(4, extraNames=["Channel 1 +1"])
		self.services = services
		home = self.openHome(start=0)
		current = home.nowNext(0)[0]
		missed = now - current["begin"] > 300
		self.assertEqual(home["plusOne"].visible, missed)
		if missed:
			self.assertIn("Channel 1 +1", home["plusOne"].text)
		home["actions"].actions["right"]()
		self.assertFalse(home["plusOne"].visible)  # no +1 for Channel 2

	def test_works_with_the_native_engine(self):
		home = self.openHome(widgetClass=NativeWidget)
		home["actions"].actions["right"]()
		self.assertEqual(home["ring"].instance.native[2], Home.TILE_X0 + 2 * Home.TILE_STEP - Home.RING)


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
		self.assertIs(session.opened[-1][0], Home.HaloHome)
		session.lastCallback(("menu", "settings"))
		self.assertTrue(infobar.openedMainMenu)
		session.lastCallback(("menu", "apps"))
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


class GuideTests(unittest.TestCase):
	def setUp(self):
		self.services, self.now = makeServices(8)
		self.timers = FakeRecordTimers()

	def openGuide(self, start=0):
		guide = Guide.HaloGuide(Session(), self.services, start, self.timers)
		guide.layout()
		advance(0.4)
		return guide

	def pillRect(self, guide):
		inst = guide["focus"].instance
		return inst.pos

	def test_opens_on_the_programme_on_now(self):
		guide = self.openGuide(start=3)
		self.assertEqual(guide.instance.pos, (0, 0))
		event = guide.selected
		self.assertLessEqual(event["begin"], self.now)
		self.assertGreater(event["end"], self.now)
		self.assertEqual(guide.top + guide.row, 3)
		x, y, w = guide.cellRect(event, guide.row)
		self.assertEqual(self.pillRect(guide), (x, y))
		self.assertIn(event["title"], guide["focus"].text)
		self.assertEqual(guide["title"].text, event["title"])

	def test_right_and_left_slide_the_pill_between_programmes(self):
		guide = self.openGuide()
		first = guide.selected
		guide["actions"].actions["right"]()
		second = guide.selected
		self.assertEqual(second["begin"], first["end"])
		advance(0.3)
		x, y, w = guide.cellRect(second, guide.row)
		self.assertEqual(self.pillRect(guide), (x, y))
		guide["actions"].actions["left"]()
		advance(0.3)
		self.assertEqual(guide.selected["id"], first["id"])

	def test_moving_right_far_enough_pages_the_window(self):
		guide = self.openGuide()
		start = guide.windowStart
		for _ in range(6):
			guide["actions"].actions["right"]()
			advance(0.3)
		self.assertGreater(guide.windowStart, start)
		self.assertGreaterEqual(guide.selected["end"], guide.windowStart)
		self.assertLess(guide.selected["begin"], guide.windowEnd())
		for _ in range(12):
			guide["actions"].actions["left"]()
			advance(0.3)
		self.assertLessEqual(guide.windowStart, start)

	def test_up_down_scroll_the_channel_rows(self):
		guide = self.openGuide(start=0)
		for _ in range(7):
			guide["actions"].actions["down"]()
			advance(0.2)
		self.assertEqual(guide.top + guide.row, 7)
		self.assertEqual(guide.top, 3)
		self.assertTrue(guide["channel4"].text.strip().endswith("Channel 8"))
		guide["actions"].actions["down"]()  # already at the last channel
		self.assertEqual(guide.top + guide.row, 7)
		guide["actions"].actions["prevBouquet"]()
		self.assertEqual(guide.top + guide.row, 2)

	def test_selection_keeps_its_time_when_changing_channel(self):
		guide = self.openGuide(start=0)
		guide["actions"].actions["right"]()
		target = guide.selected["begin"]
		guide["actions"].actions["down"]()
		event = guide.selected
		self.assertLessEqual(event["begin"], target)
		self.assertGreater(event["end"], target)

	def test_cells_fill_the_window_and_mark_now_and_past(self):
		guide = self.openGuide()
		row = [guide["cell0_%d" % c] for c in range(Guide.CELLS_PER_ROW) if guide["cell0_%d" % c].visible]
		self.assertGreaterEqual(len(row), 4)
		lefts = [cell.instance.pos[0] for cell in row]
		self.assertEqual(lefts, sorted(lefts))
		self.assertGreaterEqual(min(lefts), Guide.GRID_X)
		for cell in row:
			self.assertLessEqual(cell.instance.pos[0] + cell.instance.size[0], Guide.GRID_X + Guide.GRID_W)
		colours = {cell.instance.background for cell in row}
		self.assertIn(Guide.CARD_NOW, colours)
		self.assertTrue(guide["now"].visible)

	def test_green_records_and_cancels(self):
		guide = self.openGuide()
		guide["actions"].actions["right"]()
		guide["actions"].actions["green"]()
		self.assertEqual(len(self.timers.timer_list), 1)
		self.assertEqual(self.timers.timer_list[0].eit, guide.selected["id"])
		recorded = [guide["cell%d_%d" % (guide.row, c)] for c in range(Guide.CELLS_PER_ROW) if guide["cell%d_%d" % (guide.row, c)].visible]
		self.assertIn(Guide.RECORD, {cell.instance.background for cell in recorded})
		guide["actions"].actions["green"]()
		self.assertEqual(self.timers.timer_list, [])

	def test_ok_slides_away_and_returns_the_channel(self):
		guide = self.openGuide(start=2)
		guide["actions"].actions["down"]()
		guide["actions"].actions["ok"]()
		self.assertEqual(guide.closed, "not closed")
		advance(0.3)
		self.assertEqual(guide.instance.pos, (0, 140))
		self.assertEqual(guide.closed.toString(), self.services[3][0].toString())

	def test_channel_without_epg_shows_a_message(self):
		EPG[self.services[0][0].toString()] = []
		guide = self.openGuide(start=0)
		self.assertIsNone(guide.selected)
		self.assertFalse(guide["focus"].visible)
		self.assertEqual(guide["title"].text, "No programme information")

	def test_epg_button_opens_the_halo_guide_unless_switched_off(self):
		opened = []
		saved = Guide.openGuide
		Guide.openGuide = lambda session, infobar=None: opened.append(infobar)
		try:
			plugin.installGuideHook()
			bar = InfoBarEPG()
			bar.session = Session()
			config.plugins.halo.guide.value = True
			bar.openGraphEPG()
			self.assertEqual(opened, [bar])
			config.plugins.halo.guide.value = False
			bar.openGraphEPG()
			self.assertTrue(bar.openedStockGuide)
		finally:
			Guide.openGuide = saved
			config.plugins.halo.guide.value = True

	def test_skin_names_every_widget(self):
		import xml.etree.ElementTree as ET
		for screen in (Guide.HaloGuide(Session(), self.services, 0, self.timers), Home.HaloHome(Session(), self.services, 0)):
			skin = ET.fromstring(type(screen).skin)
			names = {w.get("name") for w in skin.findall("widget") if w.get("name")}
			self.assertEqual(names, {name for name, component in screen.items() if isinstance(component, Label)}, type(screen).__name__)

	def test_details_show_record_and_plus_one_chips(self):
		services, now = makeServices(3, extraNames=["Channel 1 +1"])
		self.services = services
		guide = self.openGuide(start=0)
		self.assertIn("Record", guide["chipRecord"].text)
		self.assertIn("Channel 1 +1", guide["chipPlus"].text)
		self.assertTrue(guide["meta"].text.startswith("1 · Channel 1 · "))
		self.assertIn("\n", guide["focus"].text)  # title and times
		guide["actions"].actions["green"]()
		self.assertIn("Recording set", guide["chipRecord"].text)
		guide["actions"].actions["down"]()
		self.assertFalse(guide["chipPlus"].visible)


if __name__ == "__main__":
	unittest.main()
