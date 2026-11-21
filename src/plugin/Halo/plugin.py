# Halo plugin entry point.
#
# At session start Halo:
#   1. makes MENU open Halo Home: the menu bar, what's on and a channel row
#      (its Settings item opens the normal Enigma2 main menu),
#   2. makes the EPG button open the Halo TV Guide (switchable in settings),
#   3. tunes the Halo channel, if one is set,
#   4. starts the GitHub release updater.

from enigma import eServiceReference, eTimer

from Components.config import ConfigInteger, ConfigSelection, ConfigSubsection, ConfigText, ConfigYesNo, config
from Plugins.Plugin import PluginDescriptor

config.plugins.halo = ConfigSubsection()
config.plugins.halo.service = ConfigText(default="")
config.plugins.halo.repo = ConfigText(default="", fixed_size=False)
config.plugins.halo.autoupdate = ConfigSelection(default="install", choices=[
	("install", _("Install automatically")),
	("notify", _("Tell me only")),
	("off", _("Off")),
])
config.plugins.halo.lastcheck = ConfigInteger(default=0)
config.plugins.halo.skipimage = ConfigText(default="")  # an image version the user said no to
config.plugins.halo.guide = ConfigYesNo(default=True)  # the EPG button opens the Halo guide

updater = None
tuneTimer = None


def openTopMenu(infobar):
	"""MENU opens Halo Home: live TV with the menu bar and the channel row."""
	from .Home import openHome
	openHome(infobar.session, infobar, menuChosen)


def menuChosen(infobar, choice):
	if choice in (None, "home"):
		return
	if choice == "settings":
		infobar._haloOriginalShowMainMenu()
	elif choice == "guide":
		from .Guide import openGuide
		openGuide(infobar.session, infobar)
	elif choice == "recordings":
		method = getattr(infobar, "showMovies", None)
		if method:
			method()
	elif choice in ("media", "apps"):
		from Screens.PluginBrowser import PluginBrowser
		infobar.session.open(PluginBrowser)


def installMenuHook():
	from Screens.InfoBarGenerics import InfoBarMenu
	if getattr(InfoBarMenu, "_haloOriginalShowMainMenu", None):
		return
	InfoBarMenu._haloOriginalShowMainMenu = InfoBarMenu.showMainMenu
	InfoBarMenu.showMainMenu = openTopMenu


def openGraphEPG(infobar, *args, **kwargs):
	"""The EPG button opens the Halo guide (Halo settings can switch this off)."""
	if config.plugins.halo.guide.value:
		from .Guide import openGuide
		openGuide(infobar.session, infobar)
	else:
		infobar._haloOriginalOpenGraphEPG(*args, **kwargs)


def installGuideHook():
	from Screens.InfoBarGenerics import InfoBarEPG
	if getattr(InfoBarEPG, "_haloOriginalOpenGraphEPG", None):
		return
	InfoBarEPG._haloOriginalOpenGraphEPG = InfoBarEPG.openGraphEPG
	InfoBarEPG.openGraphEPG = openGraphEPG


def tuneHaloChannel(session):
	ref = config.plugins.halo.service.value
	if not ref:
		return
	current = session.nav.getCurrentlyPlayingServiceReference()
	if current is None or current.toString() != ref:
		session.nav.playService(eServiceReference(ref))


def sessionstart(reason, session=None, **kwargs):
	global updater, tuneTimer
	if reason != 0 or session is None:
		return
	installMenuHook()
	installGuideHook()
	ref = config.plugins.halo.service.value
	if ref:
		# The InfoBar restores the last service when it opens; point it at ours,
		# then make sure once the GUI has settled.
		config.tv.lastservice.value = ref
		tuneTimer = eTimer()
		tuneTimer.callback.append(lambda: tuneHaloChannel(session))
		tuneTimer.start(3000, True)
	from .Updater import HaloUpdater
	updater = HaloUpdater(session)


def openSetup(session, **kwargs):
	from .Setup import HaloSetup
	session.open(HaloSetup, updater)


def Plugins(**kwargs):
	return [
		PluginDescriptor(where=PluginDescriptor.WHERE_SESSIONSTART, fnc=sessionstart),
		PluginDescriptor(name="Halo", description=_("Halo channel and updates"), where=PluginDescriptor.WHERE_PLUGINMENU, fnc=openSetup),
	]
