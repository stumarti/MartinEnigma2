# Halo Home: live TV stays on screen, with the menu bar at the top, what's on
# now in the middle, and a horizontal row of channel tiles (with picons) along
# the bottom. MENU opens it.
#
#   left / right    choose a channel tile (the row scrolls) or a menu item
#   up / down       move between the channel row and the menu bar
#   CH+ / CH-       scroll the row a page
#   OK              watch the chosen channel, or open the menu item
#   back / MENU     close
#
# A white ring slides between channel tiles and a white pill slides along the
# menu bar; the dark menu text follows the pill.

from time import localtime, strftime, time

from enigma import eSize, ePoint, eTimer, gRGB

from Components.ActionMap import ActionMap
from Components.Label import Label
from Components.Pixmap import Pixmap
from Screens.Screen import Screen

from . import Chrome
from .Animator import EASE_OUT_BACK, EASE_OUT_CUBIC, Animator
from .Chrome import INK, INK_DARK, INK_QUIET, NAV, NAV_Y, navX

TILES = 6
TILE_X0, TILE_Y = 96, 790
TILE_W, TILE_H = 268, 150
TILE_STEP = 292
RING = 4               # ring thickness around the focused tile
PROGRESS_W = 520       # the now-playing progress bar
BADGE_LIVE = gRGB(0x005B9BFF)   # the channel you're watching
BADGE_OTHER = gRGB(0xB0FFFFFF)  # any other channel: translucent white


def _hm(t):
	return strftime("%H:%M", localtime(t))


def _tileX(slot):
	return TILE_X0 + slot * TILE_STEP


def _skin():
	S = Chrome
	parts = ['<screen name="HaloHome" position="0,0" size="1920,1080" flags="wfNoBorder" backgroundColor="%s" resolution="1920,1080">' % S.S_CLEAR]
	add = parts.append
	# Shade behind the header and the lower half, so text reads over any picture.
	add('<eLabel position="0,0" size="1920,190" backgroundColor="%s" zPosition="0" />' % S.S_SHADE)
	add('<eLabel position="0,400" size="1920,680" backgroundColor="%s" zPosition="0" />' % S.S_SHADE)
	parts.extend(Chrome.headerSkin(S.S_SHADE, 0, interactive=True))
	# What's on now.
	add('<widget name="badge" position="96,424" size="110,36" font="Regular;20" foregroundColor="%s" backgroundColor="%s" cornerRadius="8" halign="center" valign="center" zPosition="1" />' % (S.S_DARK, S.S_ACCENT))
	add('<widget name="meta" position="222,420" size="1000,44" font="Regular;26" foregroundColor="%s" backgroundColor="%s" transparent="1" valign="center" noWrap="1" zPosition="1" />' % (S.S_INK_QUIET, S.S_SHADE))
	add('<widget name="title" position="96,470" size="1400,90" font="Regular;72" foregroundColor="%s" backgroundColor="%s" transparent="1" valign="center" noWrap="1" zPosition="1" />' % (S.S_INK, S.S_SHADE))
	add('<widget name="start" position="96,574" size="84,32" font="Regular;24" foregroundColor="%s" backgroundColor="%s" transparent="1" valign="center" zPosition="1" />' % (S.S_INK_QUIET, S.S_SHADE))
	add('<widget name="track" position="186,586" size="%d,8" backgroundColor="#b0ffffff" cornerRadius="4" zPosition="1" />' % PROGRESS_W)
	add('<widget name="bar" position="186,586" size="0,8" backgroundColor="%s" cornerRadius="4" zPosition="2" />' % S.S_ACCENT)
	add('<widget name="end" position="%d,574" size="84,32" font="Regular;24" foregroundColor="%s" backgroundColor="%s" transparent="1" valign="center" zPosition="1" />' % (196 + PROGRESS_W, S.S_INK_QUIET, S.S_SHADE))
	add('<widget name="left" position="%d,574" size="240,32" font="Regular;24" foregroundColor="%s" backgroundColor="%s" transparent="1" valign="center" zPosition="1" />' % (290 + PROGRESS_W, S.S_INK, S.S_SHADE))
	add('<eLabel text="NEXT" position="96,630" size="84,34" font="Regular;18" foregroundColor="%s" backgroundColor="#b0ffffff" cornerRadius="8" halign="center" valign="center" zPosition="1" />' % S.S_INK)
	add('<widget name="next" position="196,626" size="1100,42" font="Regular;26" foregroundColor="%s" backgroundColor="%s" transparent="1" valign="center" noWrap="1" zPosition="1" />' % (S.S_INK, S.S_SHADE))
	add('<widget name="plusOne" position="1240,618" size="584,56" font="Regular;24" foregroundColor="%s" backgroundColor="%s" cornerRadius="16" halign="center" valign="center" noWrap="1" zPosition="1" />' % (S.S_INK, S.S_GLASS))
	# Channel row.
	add('<eLabel text="Channels" position="96,730" size="400,44" font="Regular;28" foregroundColor="%s" backgroundColor="%s" transparent="1" valign="center" zPosition="1" />' % (S.S_INK, S.S_SHADE))
	add('<widget name="hint" position="1124,730" size="700,44" font="Regular;22" foregroundColor="%s" backgroundColor="%s" transparent="1" halign="right" valign="center" zPosition="1" />' % (S.S_INK_PAST, S.S_SHADE))
	add('<widget name="ring" position="%d,%d" size="%d,%d" backgroundColor="%s" cornerRadius="24" zPosition="1" />' % (_tileX(0) - RING, TILE_Y - RING, TILE_W + 2 * RING, TILE_H + 2 * RING, S.S_INK))
	for i in range(TILES):
		x = _tileX(i)
		add('<widget name="tile%d" position="%d,%d" size="%d,%d" backgroundColor="%s" cornerRadius="20" zPosition="2" />' % (i, x, TILE_Y, TILE_W, TILE_H, S.S_CARD))
		add('<widget name="picon%d" position="%d,%d" size="210,100" scale="centerScaled" alphatest="blend" zPosition="3" />' % (i, x + 29, TILE_Y + 26))
		add('<widget name="name%d" position="%d,%d" size="%d,%d" font="Regular;28" foregroundColor="%s" backgroundColor="%s" transparent="1" halign="center" valign="center" zPosition="3" />' % (i, x + 12, TILE_Y + 26, TILE_W - 24, 100, S.S_INK, S.S_CARD))
		add('<widget name="number%d" position="%d,%d" size="80,28" font="Regular;18" foregroundColor="%s" backgroundColor="%s" transparent="1" zPosition="4" />' % (i, x + 14, TILE_Y + 8, S.S_INK_QUIET, S.S_CARD))
		add('<widget name="tileTrack%d" position="%d,%d" size="%d,6" backgroundColor="#c8ffffff" zPosition="3" />' % (i, x + 20, TILE_Y + TILE_H - 14, TILE_W - 40))
		add('<widget name="tileBar%d" position="%d,%d" size="0,6" backgroundColor="%s" zPosition="4" />' % (i, x + 20, TILE_Y + TILE_H - 14, S.S_INK))
		add('<widget name="show%d" position="%d,%d" size="%d,32" font="Regular;22" foregroundColor="%s" backgroundColor="%s" transparent="1" noWrap="1" zPosition="1" />' % (i, x + 4, TILE_Y + TILE_H + 12, TILE_W - 8, S.S_INK, S.S_SHADE))
		add('<widget name="later%d" position="%d,%d" size="%d,28" font="Regular;18" foregroundColor="%s" backgroundColor="%s" transparent="1" noWrap="1" zPosition="1" />' % (i, x + 4, TILE_Y + TILE_H + 46, TILE_W - 8, S.S_INK_QUIET, S.S_SHADE))
	add('</screen>')
	return "\n".join(parts)


class HaloHome(Screen):
	skin = _skin()

	def __init__(self, session, services, startIndex=0, playing=None):
		Screen.__init__(self, session)
		self.services = services
		self.playing = playing          # ref string of the channel on screen
		self.animator = Animator()
		self.closing = False
		self.zone = "channels"           # or "nav"
		self.focus = max(0, min(startIndex, len(services) - 1)) if services else 0
		self.first = self.firstFor(self.focus)
		self.navIndex = 0
		self.painted = None
		self.cache = {}

		Chrome.addNavLabels(self)
		self["navPill"] = Label("")
		for name in ("badge", "meta", "title", "start", "track", "bar", "end", "left", "next", "plusOne", "hint", "ring"):
			self[name] = Label("")
		for i in range(TILES):
			for name in ("tile", "name", "number", "tileTrack", "tileBar", "show", "later"):
				self["%s%d" % (name, i)] = Label("")
			self["picon%d" % i] = Pixmap()
		self["hint"].setText(_("OK watch    ▲ menu    CH+/- page"))
		self.syncTimer = eTimer()
		self.syncTimer.callback.append(self.followNavPill)
		self["actions"] = ActionMap(["OkCancelActions", "DirectionActions", "MenuActions", "ChannelSelectBaseActions"], {
			"ok": self.ok,
			"cancel": self.exit,
			"menu": self.exit,
			"left": self.left,
			"right": self.right,
			"up": self.up,
			"down": self.down,
			"nextBouquet": lambda: self.page(TILES),
			"prevBouquet": lambda: self.page(-TILES),
		}, -1)
		self.onLayoutFinish.append(self.start)
		self.onClose.append(self.animator.stop)
		self.onClose.append(self.syncTimer.stop)

	# ---------------------------------------------------------------- data

	def firstFor(self, index):
		"""First tile so that `index` is visible, keeping the row full when possible."""
		last = max(0, len(self.services) - TILES)
		return max(0, min(index - 1, last))

	def nowNext(self, index):
		if index in self.cache:
			return self.cache[index]
		from .Guide import loadEvents
		now = time()
		events = [e for e in loadEvents(self.services[index][0], now, 240) if e["end"] > now]
		current = events[0] if events and events[0]["begin"] <= now else None
		later = events[1] if current and len(events) > 1 else (events[0] if events and not current else None)
		self.cache[index] = (current, later)
		return self.cache[index]

	# ---------------------------------------------------------------- drawing

	def start(self):
		self.drawTiles()
		self.placeRing(animate=False)
		self.paintNav(0)
		self.showDetails()
		self.animator.move(self.instance, (0, 140), (0, 0), 260, EASE_OUT_CUBIC)

	def drawTiles(self):
		now = time()
		for slot in range(TILES):
			index = self.first + slot
			names = ("tile", "name", "number", "tileTrack", "tileBar", "show", "later")
			if index >= len(self.services):
				for name in names:
					self["%s%d" % (name, slot)].hide()
				self["picon%d" % slot].hide()
				continue
			ref, name = self.services[index]
			for part in ("tile", "number", "tileTrack", "show", "later"):
				self["%s%d" % (part, slot)].show()
			self["number%d" % slot].setText(str(Chrome.channelNumber(ref, index)))
			picon = Chrome.piconFor(ref)
			pixmap = self["picon%d" % slot]
			if picon and pixmap.instance:
				pixmap.instance.setPixmapFromFile(picon)
				pixmap.show()
				self["name%d" % slot].hide()
			else:
				pixmap.hide()
				self["name%d" % slot].setText(name)
				self["name%d" % slot].show()
			current, later = self.nowNext(index)
			self["show%d" % slot].setText(current["title"] if current else _("No programme information"))
			self["later%d" % slot].setText(_("Next %s") % _hm(later["begin"]) if later else "")
			bar = self["tileBar%d" % slot]
			if current and bar.instance:
				done = (now - current["begin"]) / float(current["end"] - current["begin"])
				bar.instance.resize(eSize(max(2, int((TILE_W - 40) * done)), 6))
				bar.show()
			else:
				bar.hide()

	def ringPosition(self):
		return _tileX(self.focus - self.first) - RING, TILE_Y - RING

	def placeRing(self, animate=True):
		ring = self["ring"].instance
		if not ring:
			return
		target = self.ringPosition()
		if animate:
			current = ring.position()
			self.animator.move(ring, (current.x(), current.y()), target, 200, EASE_OUT_BACK)
		else:
			ring.move(ePoint(*target))

	def showDetails(self):
		if not self.services:
			self["title"].setText(_("No channels in this bouquet"))
			return
		index = self.focus
		ref, name = self.services[index]
		current, later = self.nowNext(index)
		number = Chrome.channelNumber(ref, index)
		self["meta"].setText("%s · %s" % (number, name))
		badge = self["badge"]
		live = ref.toString() == self.playing
		badge.setText(_("LIVE") if live else _("ON NOW"))
		if badge.instance:
			badge.instance.setBackgroundColor(BADGE_LIVE if live else BADGE_OTHER)
			badge.instance.setForegroundColor(INK_DARK if live else INK)
		now = time()
		if current:
			self["title"].setText(current["title"])
			self["start"].setText(_hm(current["begin"]))
			self["end"].setText(_hm(current["end"]))
			minutes = max(0, int((current["end"] - now) // 60))
			self["left"].setText(_("%d min left") % minutes)
			done = (now - current["begin"]) / float(current["end"] - current["begin"])
			if self["bar"].instance:
				self["bar"].instance.resize(eSize(max(8, int(PROGRESS_W * done)), 8))
			for part in ("start", "end", "track", "bar", "left"):
				self[part].show()
		else:
			self["title"].setText(name)
			for part in ("start", "end", "track", "bar", "left"):
				self[part].hide()
		self["next"].setText("%s  %s" % (_hm(later["begin"]), later["title"]) if later else "")
		plusOne = Chrome.plusOneFor(name, self.services)
		if current and plusOne and now - current["begin"] > 5 * 60 and current["begin"] + 3600 > now:
			self["plusOne"].setText(_("Missed the start?  %s at %s") % (plusOne[1], _hm(current["begin"] + 3600)))
			self["plusOne"].show()
		else:
			self["plusOne"].hide()

	def paintNav(self, highlight):
		if highlight == self.painted:
			return
		for i in range(len(NAV)):
			label = self["nav%d" % i].instance
			if label:
				label.setForegroundColor(INK_DARK if i == highlight else INK_QUIET if self.zone == "channels" else INK)
				label.invalidate()
		self.painted = highlight

	def followNavPill(self):
		pill = self["navPill"].instance
		if pill:
			index = int(round((pill.position().x() - navX(0)) / float(navX(1) - navX(0))))
			self.paintNav(max(0, min(len(NAV) - 1, index)))

	def moveNavPill(self):
		pill = self["navPill"].instance
		if not pill:
			return
		current = pill.position()
		self.animator.move(pill, (current.x(), current.y()), (navX(self.navIndex), NAV_Y), 180, EASE_OUT_CUBIC, onDone=self.navArrived)
		self.syncTimer.start(16, False)

	def navArrived(self):
		self.syncTimer.stop()
		self.paintNav(self.navIndex)

	# ---------------------------------------------------------------- keys

	def left(self):
		self.step(-1)

	def right(self):
		self.step(1)

	def step(self, delta):
		if self.closing:
			return
		if self.zone == "nav":
			self.navIndex = (self.navIndex + delta) % len(NAV)
			self.moveNavPill()
			return
		if not self.services:
			return
		self.focus = (self.focus + delta) % len(self.services)
		self.scrollTo(self.focus)

	def scrollTo(self, index):
		if index < self.first or index >= self.first + TILES:
			self.first = index if index < self.first else index - TILES + 1
			self.first = max(0, min(self.first, max(0, len(self.services) - TILES)))
			self.drawTiles()
			self.placeRing(animate=False)
		else:
			self.placeRing()
		self.showDetails()

	def page(self, delta):
		if self.closing or not self.services or self.zone != "channels":
			return
		self.focus = max(0, min(len(self.services) - 1, self.focus + delta))
		self.first = self.firstFor(self.focus)
		self.drawTiles()
		self.placeRing(animate=False)
		self.showDetails()

	def up(self):
		if self.closing or self.zone == "nav":
			return
		self.zone = "nav"
		self.painted = None
		self.paintNav(self.navIndex)

	def down(self):
		if self.closing or self.zone == "channels":
			return
		self.zone = "channels"
		self.navIndex = 0
		self.moveNavPill()
		self.painted = None
		self.paintNav(self.painted if self.painted is not None else 0)

	def ok(self):
		if self.zone == "nav":
			self.slideOut(("menu", NAV[self.navIndex][0]))
		elif self.services:
			self.slideOut(("watch", self.services[self.focus][0]))

	def exit(self):
		self.slideOut(None)

	def slideOut(self, result):
		if self.closing:
			return
		self.closing = True
		self.animator.move(self.instance, (0, 0), (0, 140), 180, EASE_OUT_CUBIC, onDone=lambda: self.close(result))


def openHome(session, infobar, onMenuChoice):
	"""Open Home on the current bouquet, focused on the channel being watched."""
	from .Guide import bouquetServices
	root = infobar.servicelist.getRoot() if getattr(infobar, "servicelist", None) else None
	services = bouquetServices(root)
	current = session.nav.getCurrentlyPlayingServiceReference()
	start = 0
	if current:
		for i, (ref, name) in enumerate(services):
			if ref.toString() == current.toString():
				start = i
				break

	def chosen(result):
		if not result:
			return
		kind, value = result
		if kind == "watch":
			if current is None or value.toString() != current.toString():
				if getattr(infobar, "servicelist", None):
					infobar.servicelist.setCurrentSelection(value)
					infobar.servicelist.zap()
				else:
					session.nav.playService(value)
		else:
			onMenuChoice(infobar, value)

	session.openWithCallback(chosen, HaloHome, services, start, current.toString() if current else None)
