# Halo TV Guide: a channel-by-time grid with a sliding focus pill.
#
#   left / right    previous / next programme (the grid pages by an hour at the edges)
#   up / down       previous / next channel
#   channel + / -   a page of channels
#   OK              watch that channel
#   green           record the selected programme (again to cancel)
#   back            close
#
# The white focus pill carries the selected programme's title and slides to
# each new programme, so the readable title always travels with the pill.
# The guide slides up when it opens and down when it closes, like the Halo
# top menu.

from time import localtime, strftime, time

from enigma import eEPGCache, eServiceCenter, eServiceReference, eSize, ePoint

from Components.ActionMap import ActionMap
from Components.Label import Label
from Screens.Screen import Screen
from ServiceReference import ServiceReference

from . import Chrome
from .Animator import EASE_OUT_CUBIC, Animator
from .Chrome import CARD, CARD_NOW, CARD_PAST, INK, INK_PAST, RECORD

# Layout (1080p), matching the Halo TV Guide design.
SCREEN_W, SCREEN_H = 1920, 1080
CHANNEL_X, CHANNEL_W = 96, 288
GRID_X = 396           # left edge of the time grid
GRID_W = 1428          # width of the time grid
RULER_Y = 506
GRID_Y = 556
ROWS = 5
ROW_H = 80
ROW_PITCH = 90
CELL_GAP = 8
CELLS_PER_ROW = 12
WINDOW_MIN = 120       # minutes shown across the grid
PAGE_MIN = 60          # how far left/right paging jumps
PPM = GRID_W / float(WINDOW_MIN)  # pixels per minute
DETAIL_X = 585


def _hm(t):
	return strftime("%H:%M", localtime(t))


def _day(t):
	today = localtime(time())
	when = localtime(t)
	if when.tm_yday == today.tm_yday and when.tm_year == today.tm_year:
		return _("Today")
	return strftime("%a %d", when)


def _skin():
	"""The screen skin. Cells are a fixed pool of labels placed by code."""
	S = Chrome
	parts = ['<screen name="HaloGuide" position="0,0" size="%d,%d" flags="wfNoBorder" backgroundColor="%s" resolution="1920,1080">' % (SCREEN_W, SCREEN_H, S.S_GROUND)]
	add = parts.append
	parts.extend(Chrome.headerSkin(S.S_GROUND, 1))
	# Filter row: the day shown and the bouquet.
	add('<widget name="day" position="96,150" size="170,48" font="Regular;22" foregroundColor="%s" backgroundColor="%s" cornerRadius="24" halign="center" valign="center" zPosition="1" />' % (S.S_DARK, S.S_INK))
	add('<widget name="bouquet" position="278,150" size="520,48" font="Regular;22" foregroundColor="%s" backgroundColor="%s" cornerRadius="24" halign="center" valign="center" noWrap="1" zPosition="1" />' % (S.S_INK_QUIET, S.S_CARD))
	add('<widget name="hint" position="924,150" size="900,48" font="Regular;22" foregroundColor="%s" backgroundColor="%s" halign="right" valign="center" zPosition="1" />' % (S.S_INK_PAST, S.S_GROUND))
	# Selected programme: live picture on the left, details on the right.
	add('<eLabel position="96,222" size="441,248" backgroundColor="%s" cornerRadius="20" zPosition="0" />' % S.S_CARD)
	add('<widget source="session.VideoPicture" render="Pig" position="96,222" size="441,248" backgroundColor="%s" zPosition="1" />' % S.S_CLEAR)
	add('<widget name="live" position="114,238" size="170,34" font="Regular;18" foregroundColor="%s" backgroundColor="%s" cornerRadius="8" halign="center" valign="center" zPosition="2" />' % (S.S_DARK, S.S_INK))
	add('<widget name="meta" position="%d,232" size="1239,36" font="Regular;24" foregroundColor="%s" backgroundColor="%s" valign="center" noWrap="1" zPosition="1" />' % (DETAIL_X, S.S_INK_QUIET, S.S_GROUND))
	add('<widget name="title" position="%d,272" size="1239,64" font="Regular;48" foregroundColor="%s" backgroundColor="%s" valign="center" noWrap="1" zPosition="1" />' % (DETAIL_X, S.S_INK, S.S_GROUND))
	add('<widget name="description" position="%d,342" size="1239,66" font="Regular;22" foregroundColor="%s" backgroundColor="%s" zPosition="1" />' % (DETAIL_X, S.S_INK_QUIET, S.S_GROUND))
	add('<widget name="chipRecord" position="%d,418" size="240,52" font="Regular;22" foregroundColor="%s" backgroundColor="%s" cornerRadius="16" halign="center" valign="center" zPosition="1" />' % (DETAIL_X, S.S_DARK, S.S_INK))
	add('<widget name="chipWatch" position="%d,418" size="200,52" font="Regular;22" foregroundColor="%s" backgroundColor="%s" cornerRadius="16" halign="center" valign="center" zPosition="1" />' % (DETAIL_X + 254, S.S_INK, S.S_CARD_NOW))
	add('<widget name="chipPlus" position="%d,418" size="460,52" font="Regular;22" foregroundColor="%s" backgroundColor="%s" cornerRadius="16" halign="center" valign="center" noWrap="1" zPosition="1" />' % (DETAIL_X + 468, S.S_INK, S.S_CARD_NOW))
	# Time ruler.
	for i in range(WINDOW_MIN // 30):
		add('<widget name="tick%d" position="%d,%d" size="200,40" font="Regular;22" foregroundColor="%s" backgroundColor="%s" valign="center" zPosition="1" />' % (i, GRID_X + int(i * 30 * PPM), RULER_Y, S.S_INK_PAST, S.S_GROUND))
	# Rows.
	for r in range(ROWS):
		y = GRID_Y + r * ROW_PITCH
		add('<widget name="channel%d" position="%d,%d" size="%d,%d" font="Regular;24" foregroundColor="%s" backgroundColor="%s" cornerRadius="16" valign="center" noWrap="1" zPosition="1" />' % (r, CHANNEL_X, y, CHANNEL_W, ROW_H, S.S_INK, S.S_CARD))
		for c in range(CELLS_PER_ROW):
			add('<widget name="cell%d_%d" position="%d,%d" size="10,%d" font="Regular;22" foregroundColor="%s" backgroundColor="%s" cornerRadius="16" valign="center" zPosition="1" />' % (r, c, GRID_X, y, ROW_H, S.S_INK, S.S_CARD))
	add('<widget name="now" position="%d,%d" size="3,%d" backgroundColor="%s" zPosition="3" />' % (GRID_X, RULER_Y, GRID_Y - RULER_Y + ROWS * ROW_PITCH - (ROW_PITCH - ROW_H), S.S_ACCENT))
	add('<widget name="focus" position="%d,%d" size="200,%d" font="Regular;22" foregroundColor="%s" backgroundColor="%s" cornerRadius="16" valign="center" zPosition="4" />' % (GRID_X, GRID_Y, ROW_H, S.S_DARK, S.S_INK))
	add('</screen>')
	return "\n".join(parts)


def bouquetServices(root):
	"""(ref, name) for each playable service in a bouquet."""
	services = []
	if root is None:
		return services
	serviceList = eServiceCenter.getInstance().list(root)
	if serviceList is None:
		return services
	while True:
		ref = serviceList.getNext()
		if not ref.valid():
			break
		if ref.flags & (eServiceReference.isDirectory | eServiceReference.isMarker):
			continue
		services.append((ref, ServiceReference(ref).getServiceName()))
	return services


def loadEvents(ref, start, minutes):
	"""Events overlapping [start, start + minutes) for one service, in order."""
	try:
		result = eEPGCache.getInstance().lookupEvent(["IBDTSE", (ref.toString(), 0, int(start), int(minutes))]) or []
	except Exception as err:
		print("[Halo] EPG lookup failed: %s" % err)
		return []
	events = []
	for eventId, begin, duration, title, short, extended in result:
		if eventId is None or begin is None or not duration:
			continue
		events.append({"id": eventId, "begin": begin, "end": begin + duration, "title": title or "", "short": short or "", "extended": extended or ""})
	events.sort(key=lambda e: e["begin"])
	return events


class HaloGuide(Screen):
	skin = _skin()

	def __init__(self, session, services, startIndex=0, recordTimers=None, bouquetName=None, playing=None):
		Screen.__init__(self, session)
		self.services = services
		self.recordTimers = recordTimers
		self.playing = playing           # ref string of the channel on screen
		self.animator = Animator()
		self.closing = False
		now = time()
		self.windowStart = now - now % 1800  # start at the current half hour
		self.cursor = now                    # the time the selection points at
		self.top = max(0, min(startIndex - 2, len(services) - ROWS)) if len(services) > ROWS else 0
		self.row = startIndex - self.top     # selected row within the page
		self.selected = None                 # the selected event (dict) or None
		self.rows = {}                       # (service index, windowStart) -> events

		Chrome.addNavLabels(self)
		for name in ("day", "bouquet", "hint", "live", "meta", "title", "description", "chipRecord", "chipWatch", "chipPlus", "now", "focus"):
			self[name] = Label("")
		for i in range(WINDOW_MIN // 30):
			self["tick%d" % i] = Label("")
		for r in range(ROWS):
			self["channel%d" % r] = Label("")
			for c in range(CELLS_PER_ROW):
				self["cell%d_%d" % (r, c)] = Label("")
		self["hint"].setText(_("◀ ▶ programmes    ▲ ▼ channels    CH+/- page"))
		self["chipWatch"].setText(_("OK  Watch"))
		self["bouquet"].setText(bouquetName or _("All channels"))
		self["actions"] = ActionMap(["OkCancelActions", "DirectionActions", "ColorActions", "ChannelSelectBaseActions"], {
			"ok": self.watch,
			"cancel": self.exit,
			"left": self.left,
			"right": self.right,
			"up": self.up,
			"down": self.down,
			"green": self.record,
			"nextBouquet": self.pageDown,
			"prevBouquet": self.pageUp,
		}, -1)
		self.onLayoutFinish.append(self.start)
		self.onClose.append(self.animator.stop)

	# ---------------------------------------------------------------- data

	def windowEnd(self):
		return self.windowStart + WINDOW_MIN * 60

	def events(self, index):
		key = (index, self.windowStart)
		if key not in self.rows:
			ref = self.services[index][0]
			self.rows[key] = loadEvents(ref, self.windowStart, WINDOW_MIN)
		return self.rows[key]

	def visible(self):
		return range(self.top, min(self.top + ROWS, len(self.services)))

	def eventAt(self, index, when):
		events = self.events(index)
		for event in events:
			if event["begin"] <= when < event["end"]:
				return event
		later = [e for e in events if e["begin"] >= when]
		return later[0] if later else (events[-1] if events else None)

	def isRecording(self, index, event):
		if not event or self.recordTimers is None:
			return False
		ref = self.services[index][0].toString()
		return any(t.service_ref.ref.toString() == ref and t.begin <= event["begin"] + 60 and t.end >= event["end"] - 60 for t in self.recordTimers.timer_list)

	# ---------------------------------------------------------------- drawing

	def cellRect(self, event, r):
		start = max(event["begin"], self.windowStart)
		end = min(event["end"], self.windowEnd())
		x = GRID_X + int((start - self.windowStart) / 60.0 * PPM)
		w = max(8, int((end - start) / 60.0 * PPM) - CELL_GAP)
		return x, GRID_Y + r * ROW_PITCH, w

	def start(self):
		self.drawAll()
		self.select(animate=False)
		self.showLive()
		self.animator.move(self.instance, (0, 140), (0, 0), 260, EASE_OUT_CUBIC)

	def cellText(self, event, width):
		if width < 48:
			return ""
		if width < 150:
			return "  " + event["title"]
		return "  %s\n  %s – %s" % (event["title"], _hm(event["begin"]), _hm(event["end"]))

	def showLive(self):
		for i, (ref, name) in enumerate(self.services):
			if ref.toString() == self.playing:
				self["live"].setText(_("LIVE · %s") % Chrome.channelNumber(ref, i))
				return
		self["live"].setText(_("LIVE"))

	def drawAll(self):
		now = time()
		self["day"].setText(_day(self.windowStart))
		for i in range(WINDOW_MIN // 30):
			self["tick%d" % i].setText(_hm(self.windowStart + i * 1800))
		for r in range(ROWS):
			index = self.top + r
			channel = self["channel%d" % r]
			cells = [self["cell%d_%d" % (r, c)] for c in range(CELLS_PER_ROW)]
			if index >= len(self.services):
				channel.hide()
				for cell in cells:
					cell.hide()
				continue
			channel.setText("   %-4s %s" % (Chrome.channelNumber(self.services[index][0], index), self.services[index][1]))
			channel.show()
			events = self.events(index)
			for c, cell in enumerate(cells):
				if c >= len(events):
					cell.hide()
					continue
				event = events[c]
				x, y, w = self.cellRect(event, r)
				inst = cell.instance
				if inst:
					inst.move(ePoint(x, y))
					inst.resize(eSize(w, ROW_H))
					if self.isRecording(index, event):
						inst.setBackgroundColor(RECORD)
						inst.setForegroundColor(INK)
					elif event["end"] <= now:
						inst.setBackgroundColor(CARD_PAST)
						inst.setForegroundColor(INK_PAST)
					elif event["begin"] <= now:
						inst.setBackgroundColor(CARD_NOW)
						inst.setForegroundColor(INK)
					else:
						inst.setBackgroundColor(CARD)
						inst.setForegroundColor(INK)
				cell.setText(self.cellText(event, w))
				cell.show()
		marker = self["now"]
		if self.windowStart <= now < self.windowEnd() and marker.instance:
			marker.instance.move(ePoint(GRID_X + int((now - self.windowStart) / 60.0 * PPM) - 2, GRID_Y - 8))
			marker.show()
		else:
			marker.hide()

	def select(self, animate=True):
		index = self.top + self.row
		self.selected = self.eventAt(index, self.cursor) if index < len(self.services) else None
		focus = self["focus"]
		inst = focus.instance
		if self.selected and inst:
			x, y, w = self.cellRect(self.selected, self.row)
			focus.setText(self.cellText(self.selected, max(w, 200)))
			inst.resize(eSize(max(w, 200), ROW_H))
			current = inst.position()
			if animate:
				self.animator.move(inst, (current.x(), current.y()), (x, y), 160, EASE_OUT_CUBIC)
			else:
				inst.move(ePoint(x, y))
			focus.show()
		elif inst:
			focus.hide()
		self.showDetails(index)

	def showDetails(self, index):
		event = self.selected
		if index >= len(self.services):
			return
		ref, channel = self.services[index]
		number = Chrome.channelNumber(ref, index)
		plusOne = Chrome.plusOneFor(channel, self.services)
		if not event:
			self["meta"].setText("%s · %s" % (number, channel))
			self["title"].setText(_("No programme information"))
			self["description"].setText("")
			self["chipRecord"].hide()
			self["chipPlus"].hide()
			return
		self["meta"].setText("%s · %s · %s – %s" % (number, channel, _hm(event["begin"]), _hm(event["end"])))
		self["title"].setText(event["title"])
		text = event["short"]
		if event["extended"] and event["extended"] not in text:
			text = (text + "  " + event["extended"]).strip()
		self["description"].setText(text)
		self["chipRecord"].setText(_("●  Recording set") if self.isRecording(index, event) else _("●  Record"))
		self["chipRecord"].show()
		if plusOne:
			self["chipPlus"].setText(_("Also on %s at %s") % (plusOne[1], _hm(event["begin"] + 3600)))
			self["chipPlus"].show()
		else:
			self["chipPlus"].hide()

	# ---------------------------------------------------------------- keys

	def left(self):
		if self.closing or not self.selected:
			return self.shiftWindow(-PAGE_MIN)
		index = self.top + self.row
		earlier = [e for e in self.events(index) if e["begin"] < self.selected["begin"]]
		if earlier:
			target = earlier[-1]
			if target["begin"] < self.windowStart and self.selected["begin"] <= self.windowStart:
				self.cursor = target["begin"]
				return self.shiftWindow(-PAGE_MIN, keepCursor=True)
			self.cursor = max(target["begin"], self.windowStart)
			self.select()
		else:
			self.cursor = self.windowStart - 60
			self.shiftWindow(-PAGE_MIN, keepCursor=True)

	def right(self):
		if self.closing or not self.selected:
			return self.shiftWindow(PAGE_MIN)
		index = self.top + self.row
		later = [e for e in self.events(index) if e["begin"] > self.selected["begin"]]
		if later and later[0]["begin"] < self.windowEnd() - 15 * 60:
			self.cursor = later[0]["begin"]
			self.select()
		else:
			self.cursor = later[0]["begin"] if later else self.windowEnd()
			self.shiftWindow(PAGE_MIN, keepCursor=True)

	def shiftWindow(self, minutes, keepCursor=False):
		if self.closing:
			return
		self.windowStart += minutes * 60
		if not keepCursor:
			self.cursor += minutes * 60
		self.cursor = min(max(self.cursor, self.windowStart), self.windowEnd() - 60)
		self.drawAll()
		self.select(animate=False)

	def moveRow(self, delta):
		if self.closing or not self.services:
			return
		index = max(0, min(len(self.services) - 1, self.top + self.row + delta))
		if self.selected:
			self.cursor = max(self.selected["begin"], self.windowStart)
		if index < self.top:
			self.top = index
			self.drawAll()
		elif index >= self.top + ROWS:
			self.top = index - ROWS + 1
			self.drawAll()
		self.row = index - self.top
		self.select()

	def up(self):
		self.moveRow(-1)

	def down(self):
		self.moveRow(1)

	def pageUp(self):
		self.moveRow(-ROWS)

	def pageDown(self):
		self.moveRow(ROWS)

	def record(self):
		if self.closing or not self.selected or self.recordTimers is None:
			return
		from RecordTimer import RecordTimerEntry
		index = self.top + self.row
		event = self.selected
		for timer in list(self.recordTimers.timer_list):
			if timer.service_ref.ref.toString() == self.services[index][0].toString() and timer.eit == event["id"]:
				self.recordTimers.removeEntry(timer)
				break
		else:
			entry = RecordTimerEntry(ServiceReference(self.services[index][0]), event["begin"], event["end"], event["title"], event["short"], event["id"], justplay=False, always_zap=False)
			conflicts = self.recordTimers.record(entry)
			if conflicts:
				from Screens.MessageBox import MessageBox
				self.session.open(MessageBox, _("This recording clashes with another timer."), MessageBox.TYPE_ERROR, timeout=5)
		self.drawAll()
		self.select(animate=False)

	def watch(self):
		index = self.top + self.row
		if index < len(self.services):
			self.slideOut(self.services[index][0])

	def exit(self):
		self.slideOut(None)

	def slideOut(self, result):
		if self.closing:
			return
		self.closing = True
		self.animator.move(self.instance, (0, 0), (0, 140), 180, EASE_OUT_CUBIC, onDone=lambda: self.close(result))


def openGuide(session, infobar=None):
	"""Open the Halo guide on the current bouquet, starting at the current channel."""
	from Screens.InfoBar import InfoBar
	infobar = infobar or InfoBar.instance
	root = infobar.servicelist.getRoot() if infobar and getattr(infobar, "servicelist", None) else None
	services = bouquetServices(root)
	current = session.nav.getCurrentlyPlayingServiceReference()
	start = 0
	if current:
		for i, (ref, name) in enumerate(services):
			if ref.toString() == current.toString():
				start = i
				break

	def chosen(ref):
		if ref is not None and (current is None or ref.toString() != current.toString()):
			if infobar and getattr(infobar, "servicelist", None):
				infobar.servicelist.setCurrentSelection(ref)
				infobar.servicelist.zap()
			else:
				session.nav.playService(ref)

	bouquetName = ServiceReference(root).getServiceName() if root else None
	session.openWithCallback(chosen, HaloGuide, services, start, getattr(session.nav, "RecordTimer", None), bouquetName, current.toString() if current else None)
