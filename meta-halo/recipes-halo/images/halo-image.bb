SUMMARY = "Halo minimal image: Enigma2 on one channel with the Halo top menu"

# The shared OE-Alliance image boilerplate (rootfs, package index, versions).
require recipes-oe-alliance/image/oea-image-common.inc

# Everything the box needs to boot, tune and show live TV, and nothing else.
# Add packages back one at a time as you need them.
IMAGE_INSTALL = "\
    packagegroup-oea-linux-core \
    packagegroup-oea-machine-core \
    packagegroup-oea-network-core \
    packagegroup-oea-python-core \
    packagegroup-oea-multimedia \
    packagegroup-oea-gui \
    packagegroup-base \
    oe-alliance-branding \
    oe-alliance-remote \
    tuxbox-links \
    tuxbox-common \
    enigma2 \
    enigma2-plugin-systemplugins-hotplug \
    enigma2-plugin-extensions-halo \
    enigma2-plugin-skins-halo \
    ofgwrite \
    vsftpd \
    busybox-telnetd \
    "

IMAGE_FEATURES += "package-management allow-empty-password empty-root-password allow-root-login"
INHIBIT_DEFAULT_DEPS = "1"

export IMAGE_BASENAME = "halo-image"

# Record which Halo release this image is, so the updater can offer newer images.
HALO_IMAGE_VERSION = "${@open(os.path.join(d.getVar('HALO_SRC'), '..', 'VERSION')).read().strip()}"
ROOTFS_POSTPROCESS_COMMAND += " halo_write_image_version"
halo_write_image_version() {
    install -d ${IMAGE_ROOTFS}${sysconfdir}
    echo "${HALO_IMAGE_VERSION}" > ${IMAGE_ROOTFS}${sysconfdir}/halo-image-version
}
