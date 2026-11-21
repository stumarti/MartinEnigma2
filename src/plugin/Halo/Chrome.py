# Shared Halo look: colours, the header (logo, menu bar, clock) and small helpers.

from enigma import gRGB

# Colours as skin strings (#AARRGGBB, AA = 00 opaque, ff fully transparent) ...
S_INK = "#00f4f6fa"
S_INK_QUIET = "#00aeb6c4"
S_INK_PAST = "#006f7889"
S_DARK = "#0007090c"
S_GROUND = "#00090b10"
S_CARD = "#00141922"
S_CARD_NOW = "#00232a35"
S_GLASS = "#38121620"
S_SHADE = "#50090b10"
S_ACCENT = "#005b9bff"
S_RECORD = "#00e5484d"
S_CLEAR = "#ff000000"

# ... and as colours for code.
INK = gRGB(0x00F4F6FA)
INK_QUIET = gRGB(0x00AEB6C4)
INK_PAST = gRGB(0x006F7889)
INK_DARK = gRGB(0x0007090C)
CARD = gRGB(0x00141922)
CARD_NOW = gRGB(0x00232A35)
CARD_PAST = gRGB(0x000E1117)
RECORD = gRGB(0x00E5484D)

NAV = [
	("home", _("Home")),
	("guide", _("TV Guide")),
	("recordings", _("Recordings")),
	("media", _("Media")),
	("apps", _("Apps")),
	("settings", _("Settings")),
]

# Header geometry (1080p).
NAV_X = 300            # first pill
NAV_Y = 62
NAV_W = 168            # every pill is this wide
NAV_STEP = 176
NAV_H = 56


def navX(index):
	return NAV_X + index * NAV_STEP


def headerSkin(background, activeIndex=None, interactive=False):
	"""Logo, menu bar and clock. With interactive=True the pill is a separate
	widget ("navPill") that code slides; otherwise the active item is drawn white."""
	parts = [
		'<eLabel position="96,72" size="36,36" backgroundColor="%s" borderWidth="3" borderColor="%s" cornerRadius="18" zPosition="2" />' % (background, S_ACCENT),
		'<eLabel text="Halo" position="146,56" size="140,68" font="Regular;30" foregroundColor="%s" backgroundColor="%s" transparent="1" valign="center" zPosition="2" />' % (S_INK, background),
		'<eLabel position="%d,%d" size="%d,%d" backgroundColor="%s" cornerRadius="34" zPosition="1" />' % (NAV_X - 6, NAV_Y - 6, len(NAV) * NAV_STEP - (NAV_STEP - NAV_W) + 12, NAV_H + 12, S_GLASS),
	]
	if interactive:
		parts.append('<widget name="navPill" position="%d,%d" size="%d,%d" backgroundColor="%s" cornerRadius="28" zPosition="2" />' % (navX(activeIndex or 0), NAV_Y, NAV_W, NAV_H, S_INK))
	for i, (key, title) in enumerate(NAV):
		active = (not interactive) and i == activeIndex
		if active:
			parts.append('<eLabel position="%d,%d" size="%d,%d" backgroundColor="%s" cornerRadius="28" zPosition="2" />' % (navX(i), NAV_Y, NAV_W, NAV_H, S_INK))
		parts.append('<widget name="nav%d" position="%d,%d" size="%d,%d" font="Regular;24" foregroundColor="%s" backgroundColor="%s" transparent="1" halign="center" valign="center" zPosition="3" />' % (
			i, navX(i), NAV_Y, NAV_W, NAV_H, S_DARK if active else S_INK_QUIET, S_INK if active else S_GLASS))
	parts.append('<widget source="global.CurrentTime" render="Label" position="1600,56" size="224,68" font="Regular;32" foregroundColor="%s" backgroundColor="%s" transparent="1" halign="right" valign="center" zPosition="2"><convert type="ClockToText">Format:%%H:%%M</convert></widget>' % (S_INK, background))
	return parts


def addNavLabels(screen):
	from Components.Label import Label
	for i, (key, title) in enumerate(NAV):
		screen["nav%d" % i] = Label(title)


def plusOneFor(name, services):
	"""The '+1' service for a channel name, if the list has one."""
	wanted = (name or "").replace(" ", "").lower() + "+1"
	for ref, other in services:
		if other.replace(" ", "").lower() == wanted:
			return ref, other
	return None


def channelNumber(ref, index):
	try:
		number = ref.getChannelNum()
	except Exception:
		number = 0
	return number if number and number > 0 else index + 1


def piconFor(ref):
	"""The channel logo (picon) file the box has for a service, or ''."""
	from os.path import exists
	try:
		from Components.Renderer.Picon import getPiconName
		path = getPiconName(ref.toString())
	except Exception:
		path = ""
	return path if path and exists(path) else ""
