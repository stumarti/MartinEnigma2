SUMMARY = "Halo skin (1080p)"
SECTION = "extra"
require conf/license/license-gplv2.inc

PACKAGE_ARCH = "all"
PV = "${@open(os.path.join(d.getVar('HALO_SRC'), '..', 'VERSION')).read().strip()}"
PR = "r0"

FILESEXTRAPATHS:prepend := "${HALO_SRC}:"
SRC_URI = "file://skin/Halo"
S = "${UNPACKDIR}"

FILES:${PN} = "${datadir}/enigma2/Halo"

do_install() {
    install -d ${D}${datadir}/enigma2/Halo
    cp -r --no-preserve=ownership ${UNPACKDIR}/skin/Halo/* ${D}${datadir}/enigma2/Halo/
}

# Make Halo the active skin on first boot, unless a skin was already chosen.
pkg_postinst:${PN}() {
#!/bin/sh
SETTINGS="$D${sysconfdir}/enigma2/settings"
mkdir -p "$(dirname "$SETTINGS")"
touch "$SETTINGS"
grep -q "^config.skin.primary_skin=" "$SETTINGS" || echo "config.skin.primary_skin=Halo/skin.xml" >> "$SETTINGS"
exit 0
}

do_package_qa[noexec] = "1"
