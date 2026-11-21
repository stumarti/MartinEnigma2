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

from enigma import eEPGCache, eServiceCenter, eServiceReference, eSize, ePoint, gRGB

from Components.ActionMap import ActionMap
from Components.Label import Label
from Screens.Screen import Screen
from ServiceReference import ServiceReference

from .Animator import EASE_OUT_CUBIC, Animator

# Layout (1080p).
SCREEN_W, SCREEN_H = 1920, 1080
GRID_X = 392           # left edge of the time grid
GRID_W = 1432          # width of the time grid
CHANNEL_X, CHANNEL_W = 96, 280
GRID_Y = 476
ROWS = 6
ROW_H = 76
ROW_PITCH = 84
CELL_GAP = 6
CELLS_PER_ROW = 12
WINDOW_MIN = 120       # minutes shown across the grid
PAGE_MIN = 60          # how far left/right paging jumps
PPM = GRID_W / float(WINDOW_MIN)  # pixels per minute
RULER_Y = 430

# Colours: alpha first, 00 = opaque.
INK = gRGB(0x00F4F6FA)
INK_QUIET = gRGB(0x00AEB6C4)
INK_PAST = gRGB(0x006F7889)
INK_DARK = gRGB(0x0007090C)
CARD = gRGB(0x00141922)
CARD_NOW = gRGB(0x00232A35)
CARD_PAST = gRGB(0x000E1117)
RECORD = gRGB(0x00E5484D)


def _hm(t):
	return strftime("%H:%M", localtime(t))


def _skin():
	"""The screen skin. Cells are a fixed pool of labels placed by code."""
	parts = ['<screen name="HaloGuide" position="0,0" size="%d,%d" flags="wfNoBorder" backgroundColor="#00090b10" resolution="1920,1080">' % (SCREEN_W, SCREEN_H)]
	add = parts.append
	add('<eLabel text="TV Guide" position="96,44" size="420,64" font="Regular;44" foregroundColor="#00f4f6fa" backgroundColor="#00090b10" valign="center" />')
	add('<widget name="bouquet" position="520,44" size="1040,64" font="Regular;28" foregroundColor="#00aeb6c4" backgroundColor="#00090b10" valign="center" noWrap="1" />')
	add('<widget source="global.CurrentTime" render="Label" position="1600,44" size="224,64" font="Regular;32" foregroundColor="#00f4f6fa" backgroundColor="#00090b10" halign="right" valign="center"><convert type="ClockToText">Format:%H:%M</convert></widget>')
	# Detail card.
	add('<eLabel position="96,132" size="1728,272" backgroundColor="#00141922" cornerRadius="28" zPosition="0" />')
	add('<widget name="when" position="136,154" size="1648,36" font="Regular;26" foregroundColor="#00aeb6c4" backgroundColor="#00141922" transparent="1" noWrap="1" zPosition="1" />')
	add('<widget name="title" position="136,194" size="1648,64" font="Regular;46" foregroundColor="#00f4f6fa" backgroundColor="#00141922" transparent="1" noWrap="1" zPosition="1" />')
	add('<widget name="description" position="136,264" size="1648,100" font="Regular;26" foregroundColor="#00aeb6c4" backgroundColor="#00141922" transparent="1" zPosition="1" />')
	add('<widget name="progressTrack" position="136,378" size="1648,6" backgroundColor="#00232a35" cornerRadius="3" zPosition="1" />')
	add('<widget name="progress" position="136,378" size="0,6" backgroundColor="#005b9bff" cornerRadius="3" zPosition="2" />')
	# Time ruler.
	for i in range(WINDOW_MIN // 30):
		add('<widget name="tick%d" position="%d,%d" size="200,36" font="Regular;24" foregroundColor="#00aeb6c4" backgroundColor="#00090b10" zPosition="1" />' % (i, GRID_X + int(i * 30 * PPM), RULER_Y))
	# Rows.
	for r in range(ROWS):
		y = GRID_Y + r * ROW_PITCH
		add('<widget name="channel%d" position="%d,%d" size="%d,%d" font="Regular;26" foregroundColor="#00f4f6fa" backgroundColor="#00141922" cornerRadius="16" valign="center" noWrap="1" zPosition="1" />' % (r, CHANNEL_X, y, CHANNEL_W, ROW_H))
		for c in range(CELLS_PER_ROW):
			add('<widget name="cell%d_%d" position="%d,%d" size="10,%d" font="Regular;24" foregroundColor="#00f4f6fa" backgroundColor="#00141922" cornerRadius="16" valign="center" noWrap="1" zPosition="1" />' % (r, c, GRID_X, y, ROW_H))
	add('<widget name="now" position="%d,%d" size="4,%d" backgroundColor="#005b9bff" zPosition="3" />' % (GRID_X, GRID_Y - 8, ROWS * ROW_PITCH))
	add('<widget name="focus" position="%d,%d" size="200,%d" font="Regular;24" foregroundColor="#0007090c" backgroundColor="#00f4f6fa" cornerRadius="16" valign="center" noWrap="1" zPosition="4" />' % (GRID_X, GRID_Y, ROW_H))
	add('<widget name="hint" position="96,1000" size="1728,40" font="Regular;24" foregroundColor="#006f7889" backgroundColor="#00090b10" valign="center" />')
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

	def __init__(self, session, services, startIndex=0, recordTimers=None):
		Screen.__init__(self, session)
		self.services = services
		self.recordTimers = recordTimers
		self.animator = Animator()
		self.closing = False
		now = time()
		self.windowStart = now - now % 1800  # start at the current half hour
		self.cursor = now                    # the time the selection points at
		self.top = max(0, min(startIndex - 2, len(services) - ROWS)) if len(services) > ROWS else 0
		self.row = startIndex - self.top     # selected row within the page
		self.selected = None                 # the selected event (dict) or None
		self.rows = {}                       # (service index, windowStart) -> events

		self["bouquet"] = Label("")
		for name in ("when", "title", "description", "progressTrack", "progress", "now", "focus", "hint"):
			self[name] = Label("")
		for i in range(WINDOW_MIN // 30):
			self["tick%d" % i] = Label("")
		for r in range(ROWS):
			self["channel%d" % r] = Label("")
			for c in range(CELLS_PER_ROW):
				self["cell%d_%d" % (r, c)] = Label("")
		self["hint"].setText(_("OK  Watch     Green  Record     CH+/-  Page     Back  Close"))
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
		self.animator.move(self.instance, (0, SCREEN_H), (0, 0), 280, EASE_OUT_CUBIC)

	def drawAll(self):
		now = time()
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
			channel.setText("  %s" % self.services[index][1])
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
				cell.setText(("  " + event["title"]) if w > 48 else "")
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
			focus.setText("  " + self.selected["title"])
			inst.resize(eSize(max(w, 120), ROW_H))
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
		channel = self.services[index][1]
		if not event:
			self["when"].setText(channel)
			self["title"].setText(_("No programme information"))
			self["description"].setText("")
			self.setProgress(None)
			return
		self["when"].setText("%s – %s    %s" % (_hm(event["begin"]), _hm(event["end"]), channel))
		self["title"].setText(event["title"])
		text = event["short"]
		if event["extended"] and event["extended"] not in text:
			text = (text + "\n" + event["extended"]).strip()
		self["description"].setText(text)
		self.setProgress(event)

	def setProgress(self, event):
		bar = self["progress"]
		now = time()
		if event and event["begin"] <= now < event["end"] and bar.instance:
			done = (now - event["begin"]) / float(event["end"] - event["begin"])
			bar.instance.resize(eSize(max(6, int(1648 * done)), 6))
			bar.show()
			self["progressTrack"].show()
		else:
			bar.hide()
			self["progressTrack"].hide()

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
		self.animator.move(self.instance, (0, 0), (0, SCREEN_H), 220, EASE_OUT_CUBIC, onDone=lambda: self.close(result))


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

	session.openWithCallback(chosen, HaloGuide, services, start, getattr(session.nav, "RecordTimer", None))
