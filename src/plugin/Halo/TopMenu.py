# Halo top menu: slides down over live TV when MENU is pressed.
#
# The menu window slides in from above the screen, and the white focus pill
# slides between items as you move left and right. The dark "on focus" text
# follows the pill as it travels, so the label under the pill is always the
# readable one. On close the menu slides back up before the chosen action runs.

from enigma import eTimer, gRGB

from Components.ActionMap import ActionMap
from Components.Label import Label
from Screens.Screen import Screen

from .Animator import EASE_OUT_BACK, EASE_OUT_CUBIC, Animator

ITEMS = [
	("home", _("Home")),
	("guide", _("TV Guide")),
	("recordings", _("Recordings")),
	("media", _("Media")),
	("apps", _("Apps")),
	("settings", _("Settings")),
]

# Geometry in 1080p skin pixels. Must match the HaloTopMenu screen in the skin.
MENU_Y = 0
MENU_HEIGHT = 180
ITEM_X0 = 360
ITEM_Y = 52
ITEM_WIDTH = 200
ITEM_STEP = 216

INK = gRGB(0x00F4F6FA)  # enigma2 colours: alpha first, 00 = opaque
INK_ON_FOCUS = gRGB(0x0007090C)


class HaloTopMenu(Screen):
	skin = """
	<screen name="HaloTopMenu" position="0,0" size="1920,180" flags="wfNoBorder" backgroundColor="#ff000000" resolution="1920,1080">
		<eLabel name="panel" position="96,32" size="1728,112" backgroundColor="#30121620" cornerRadius="56" zPosition="0" />
		<widget name="brand" position="136,32" size="190,112" font="Regular;34" foregroundColor="#00f4f6fa" backgroundColor="#30121620" transparent="1" valign="center" zPosition="2" />
		<widget name="focus" position="360,52" size="200,72" backgroundColor="#00f4f6fa" cornerRadius="36" zPosition="1" />
		<widget name="item0" position="360,52" size="200,72" font="Regular;28" halign="center" valign="center" transparent="1" zPosition="2" />
		<widget name="item1" position="576,52" size="200,72" font="Regular;28" halign="center" valign="center" transparent="1" zPosition="2" />
		<widget name="item2" position="792,52" size="200,72" font="Regular;28" halign="center" valign="center" transparent="1" zPosition="2" />
		<widget name="item3" position="1008,52" size="200,72" font="Regular;28" halign="center" valign="center" transparent="1" zPosition="2" />
		<widget name="item4" position="1224,52" size="200,72" font="Regular;28" halign="center" valign="center" transparent="1" zPosition="2" />
		<widget name="item5" position="1440,52" size="200,72" font="Regular;28" halign="center" valign="center" transparent="1" zPosition="2" />
		<widget source="global.CurrentTime" render="Label" position="1660,32" size="124,112" font="Regular;30" foregroundColor="#00f4f6fa" backgroundColor="#30121620" transparent="1" halign="right" valign="center" zPosition="2">
			<convert type="ClockToText">Format:%H:%M</convert>
		</widget>
	</screen>"""

	def __init__(self, session):
		Screen.__init__(self, session)
		self.animator = Animator()
		self.index = 0
		self.closing = False
		self["brand"] = Label(_("Halo"))
		self["focus"] = Label("")
		for i, (key, title) in enumerate(ITEMS):
			self["item%d" % i] = Label(title)
		self["actions"] = ActionMap(["OkCancelActions", "DirectionActions", "MenuActions"], {
			"ok": self.select,
			"cancel": self.exit,
			"menu": self.exit,
			"left": self.left,
			"right": self.right,
		}, -1)
		self.painted = None
		self.syncTimer = eTimer()
		self.syncTimer.callback.append(self.followPill)
		self.onLayoutFinish.append(self.slideIn)
		self.onClose.append(self.animator.stop)
		self.onClose.append(self.syncTimer.stop)

	def itemX(self, index):
		return ITEM_X0 + index * ITEM_STEP

	def paintItems(self, highlight=None):
		"""Dark text for the item under the pill, light text for the rest."""
		highlight = self.index if highlight is None else highlight
		if highlight == self.painted:
			return
		for i in range(len(ITEMS)):
			label = self["item%d" % i].instance
			if label:
				label.setForegroundColor(INK_ON_FOCUS if i == highlight else INK)
				label.invalidate()
		self.painted = highlight

	def itemUnderPill(self):
		focus = self["focus"].instance
		if not focus:
			return self.index
		index = int(round((focus.position().x() - ITEM_X0) / float(ITEM_STEP)))
		return max(0, min(len(ITEMS) - 1, index))

	def followPill(self):
		self.paintItems(self.itemUnderPill())

	def pillArrived(self):
		self.syncTimer.stop()
		self.paintItems()

	def slideIn(self):
		self.paintItems()
		self.animator.move(self.instance, (0, MENU_Y - MENU_HEIGHT), (0, MENU_Y), 320, EASE_OUT_BACK)

	def moveFocus(self, newIndex):
		self.index = newIndex % len(ITEMS)
		focus = self["focus"].instance
		if focus:
			# Start from wherever the pill is now, so fast key presses chain smoothly.
			current = focus.position()
			self.animator.move(focus, (current.x(), current.y()), (self.itemX(self.index), ITEM_Y), 180, EASE_OUT_CUBIC, onDone=self.pillArrived)
			self.syncTimer.start(16, False)
		else:
			self.paintItems()

	def left(self):
		if not self.closing:
			self.moveFocus(self.index - 1)

	def right(self):
		if not self.closing:
			self.moveFocus(self.index + 1)

	def select(self):
		self.slideOut(ITEMS[self.index][0])

	def exit(self):
		self.slideOut(None)

	def slideOut(self, choice):
		if self.closing:
			return
		self.closing = True
		self.animator.move(self.instance, (0, MENU_Y), (0, MENU_Y - MENU_HEIGHT), 200, EASE_OUT_CUBIC, onDone=lambda: self.close(choice))
