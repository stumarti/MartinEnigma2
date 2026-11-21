# Halo: add the time-based animation engine to openATV's Enigma2.
FILESEXTRAPATHS:prepend := "${THISDIR}/files:"

SRC_URI:append:halo = " file://0001-Halo-time-based-widget-animation-engine.patch"
