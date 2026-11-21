# Halo settings: the channel to show, how updates work, and a manual check.

from enigma import eServiceReference

from Components.ActionMap import ActionMap
from Components.config import config, getConfigListEntry
from Components.ConfigList import ConfigListScreen
from Components.Sources.StaticText import StaticText
from Screens.Screen import Screen
from ServiceReference import ServiceReference

from .Updater import installedImageVersion, installedVersion, releaseRepo


class HaloSetup(ConfigListScreen, Screen):
	skin = """
	<screen name="HaloSetup" position="center,center" size="1200,640" title="Halo" resolution="1920,1080">
		<widget name="config" position="40,30" size="1120,420" font="Regular;30" itemHeight="56" scrollbarMode="showOnDemand" />
		<widget source="info" render="Label" position="40,470" size="1120,80" font="Regular;24" foregroundColor="#00aeb6c4" />
		<widget source="key_red" render="Label" position="40,580" size="260,40" font="Regular;24" />
		<widget source="key_green" render="Label" position="320,580" size="260,40" font="Regular;24" />
		<widget source="key_yellow" render="Label" position="600,580" size="300,40" font="Regular;24" />
		<widget source="key_blue" render="Label" position="920,580" size="260,40" font="Regular;24" />
	</screen>"""

	def __init__(self, session, updater=None):
		Screen.__init__(self, session, enableHelp=True)
		self.updater = updater
		self.setTitle(_("Halo settings"))
		self["key_yellow"] = StaticText(_("Use this channel"))
		self["key_blue"] = StaticText(_("Check for updates"))
		self["info"] = StaticText()
		ConfigListScreen.__init__(self, [], session=session, fullUI=True)
		self["haloActions"] = ActionMap(["ColorActions"], {
			"yellow": self.useCurrentChannel,
			"blue": self.checkNow,
		}, -2)
		self.buildList()

	def buildList(self):
		halo = config.plugins.halo
		self["config"].list = [
			getConfigListEntry(_("Updates"), halo.autoupdate),
			getConfigListEntry(_("Release repository (owner/name)"), halo.repo),
		]
		ref = halo.service.value
		channel = ServiceReference(eServiceReference(ref)).getServiceName() if ref else _("last channel watched")
		self["info"].setText(_("Channel: %s\nHalo %s, image %s, releases from %s") % (
			channel, installedVersion(), installedImageVersion() or _("not a Halo image"), releaseRepo() or _("not set")))

	def useCurrentChannel(self):
		ref = self.session.nav.getCurrentlyPlayingServiceReference()
		if ref:
			config.plugins.halo.service.value = ref.toString()
			config.plugins.halo.service.save()
			self.buildList()

	def checkNow(self):
		if self.updater:
			self.updater.check(manual=True)
