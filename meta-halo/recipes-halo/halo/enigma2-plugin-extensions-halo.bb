SUMMARY = "Halo: live TV on one channel, animated top menu, GitHub updates"
SECTION = "extra"
require conf/license/license-gplv2.inc
require conf/python/python3-compileall.inc

PACKAGE_ARCH = "all"
PV = "${@open(os.path.join(d.getVar('HALO_SRC'), '..', 'VERSION')).read().strip()}"
PR = "r0"

FILESEXTRAPATHS:prepend := "${HALO_SRC}:"
SRC_URI = "file://plugin/Halo"
S = "${UNPACKDIR}"

PLUGIN = "${libdir}/enigma2/python/Plugins/Extensions/Halo"
FILES:${PN} = "${PLUGIN} ${sysconfdir}/halo-version"

RDEPENDS:${PN} = "python3-json python3-netclient ofgwrite"

do_install() {
    install -d ${D}${PLUGIN}
    cp -r --no-preserve=ownership ${UNPACKDIR}/plugin/Halo/* ${D}${PLUGIN}/
    printf '{\n "repo": "%s",\n "version": "%s"\n}\n' "${HALO_GITHUB_REPO}" "${PV}" > ${D}${PLUGIN}/release.json
    install -d ${D}${sysconfdir}
    echo "${PV}" > ${D}${sysconfdir}/halo-version
}

do_package_qa[noexec] = "1"
