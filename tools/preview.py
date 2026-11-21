#!/usr/bin/env python3
"""Render the Halo screens to PNG files, without a box.

    tools/preview.py --out out/preview

Runs the real Halo screen code (Home, TV Guide) against the Enigma2 stand-ins
from tests/test_smoke.py, with made-up channels and programmes, presses some
keys, then draws every widget where the code left it: position, size,
colours, rounded corners, text and visibility. Live TV is a painted stand-in.

It's an approximation of Enigma2's renderer (fonts, text fitting and alpha
blending differ a little), good for checking layout, overlaps, clipping and
colours before anything goes to the box.
"""

import argparse
import os
import re
import sys
import xml.etree.ElementTree as ET

from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tests"))

import test_smoke as e2  # noqa: E402  (installs the Enigma2 stand-ins)
from Halo import Guide, Home  # noqa: E402

FONT_DIRS = [
	os.environ.get("HALO_FONT_DIR", ""),
	"/usr/share/fonts/truetype/liberation",
	"/usr/share/fonts/truetype/liberation2",
	"/usr/share/fonts/liberation",
	os.path.join(ROOT, "tools", "fonts"),
]
FONT_FILES = {"Regular": "LiberationSans-Regular.ttf", "Bold": "LiberationSans-Bold.ttf"}
_fonts = {}


def font(spec):
	"""'Regular;24' -> a PIL font. Enigma2 sizes are pixel heights, roughly."""
	name, _, size = (spec or "Regular;20").partition(";")
	size = int(size or 20)
	key = (name, size)
	if key not in _fonts:
		path = None
		for folder in FONT_DIRS:
			candidate = os.path.join(folder, FONT_FILES.get(name, FONT_FILES["Regular"])) if folder else ""
			if candidate and os.path.exists(candidate):
				path = candidate
				break
		_fonts[key] = ImageFont.truetype(path, size) if path else ImageFont.load_default(size)
	return _fonts[key]


def colour(value, named):
	"""Enigma2 '#AARRGGBB' (AA = 00 opaque) or a named skin colour -> RGBA."""
	value = named.get(value, value) if value else None
	if not value or not value.startswith("#"):
		return None
	value = value.lstrip("#")
	if len(value) == 6:
		value = "00" + value
	a, r, g, b = (int(value[i:i + 2], 16) for i in (0, 2, 4, 6))
	return (r, g, b, 255 - a)


def gRGBtoRGBA(value):
	if value is None:
		return None
	a, r, g, b = (value >> 24) & 255, (value >> 16) & 255, (value >> 8) & 255, value & 255
	return (r, g, b, 255 - a)


def namedColours():
	skin = ET.parse(os.path.join(ROOT, "src", "skin", "Halo", "skin.xml")).getroot()
	return {c.get("name"): c.get("value") for c in skin.findall("colors/color")}


def livePicture(size):
	"""A stand-in TV picture: sky, hills, a little sun."""
	w, h = size
	img = Image.new("RGBA", size)
	draw = ImageDraw.Draw(img)
	for y in range(h):
		t = y / float(h)
		top, mid, bottom = (92, 124, 150), (169, 185, 194), (46, 58, 44)
		if t < 0.45:
			k = t / 0.45
			c = tuple(int(top[i] + (mid[i] - top[i]) * k) for i in range(3))
		else:
			k = (t - 0.45) / 0.55
			c = tuple(int(mid[i] + (bottom[i] - mid[i]) * k) for i in range(3))
		draw.line([(0, y), (w, y)], fill=c + (255,))
	draw.ellipse([w * 0.72, h * 0.12, w * 0.80, h * 0.12 + w * 0.08], fill=(250, 236, 200, 255))
	draw.ellipse([-w * 0.1, h * 0.43, w * 0.6, h * 0.85], fill=(62, 77, 58, 255))
	draw.ellipse([w * 0.45, h * 0.40, w * 1.2, h * 0.88], fill=(74, 89, 68, 255))
	return img


def fitText(draw, text, fnt, width, noWrap):
	lines = []
	for paragraph in text.split("\n"):
		if noWrap:
			line = paragraph
			while line and draw.textlength(line, font=fnt) > width:
				line = line[:-1]
			if line != paragraph and len(line) > 1:
				line = line[:-1] + "…"
			lines.append(line)
			continue
		indent = paragraph[:len(paragraph) - len(paragraph.lstrip(" "))]
		words, line = paragraph.lstrip(" ").split(" "), indent
		for word in words:
			trial = (line + " " + word) if line.strip() else line + word
			if draw.textlength(trial, font=fnt) <= width or not line.strip():
				line = trial
			else:
				lines.append(line)
				line = word
		lines.append(line)
	return lines


class Element:
	def __init__(self, node, order, named):
		self.node = node
		self.order = order
		self.named = named
		self.name = node.get("name")
		self.tag = node.tag
		self.source = node.get("source")
		self.render = node.get("render")
		x, y = (int(v) for v in node.get("position", "0,0").split(","))
		w, h = (int(v) for v in node.get("size", "0,0").split(","))
		self.pos, self.size = (x, y), (w, h)
		self.z = int(node.get("zPosition", "0"))
		self.text = node.get("text", "")
		self.font = node.get("font")
		self.fg = colour(node.get("foregroundColor"), named) or (244, 246, 250, 255)
		self.bg = colour(node.get("backgroundColor"), named)
		self.transparent = node.get("transparent") == "1"
		self.radius = int(re.split(r"[;,]", node.get("cornerRadius", "0"))[0] or 0)
		self.halign = node.get("halign", "left")
		self.valign = node.get("valign", "top")
		self.noWrap = node.get("noWrap") == "1"
		self.borderWidth = int(node.get("borderWidth", "0") or 0)
		self.borderColor = colour(node.get("borderColor"), named)
		self.visible = True
		self.pixmap = None
		self.isPixmap = False

	def applyRuntime(self, component):
		"""Take what the screen code did to this widget."""
		inst = component.instance
		if inst is not None:
			self.pos = tuple(inst.pos)
			if getattr(inst, "size", None):
				self.size = tuple(inst.size)
			if hasattr(inst, "colour"):
				self.fg = gRGBtoRGBA(inst.colour)
			if hasattr(inst, "background"):
				self.bg = gRGBtoRGBA(inst.background)
			self.pixmap = getattr(inst, "pixmap", None)
		self.text = component.text if component.text is not None else ""
		self.visible = component.visible
		self.isPixmap = isinstance(component, e2.Pixmap)


def render(screen, path, clock="21:44"):
	named = namedColours()
	skin = ET.fromstring(type(screen).skin)
	screenBg = colour(skin.get("backgroundColor"), named)
	canvas = livePicture((1920, 1080)) if screenBg and screenBg[3] == 0 else Image.new("RGBA", (1920, 1080), screenBg)
	offset = tuple(screen.instance.pos) if screen.instance else (0, 0)
	elements = [Element(node, i, named) for i, node in enumerate(skin) if node.tag in ("eLabel", "widget")]
	for element in elements:
		if element.name and element.name in screen:
			element.applyRuntime(screen[element.name])
		elif element.source == "global.CurrentTime":
			element.text = clock
	for element in sorted(elements, key=lambda e: (e.z, e.order)):
		if not element.visible:
			continue
		layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
		draw = ImageDraw.Draw(layer)
		x, y = element.pos[0] + offset[0], element.pos[1] + offset[1]
		w, h = element.size
		box = [x, y, x + max(0, w - 1), y + max(0, h - 1)]
		if element.render == "Pig":
			canvas.alpha_composite(livePicture((w, h)), (x, y))
			continue
		if element.isPixmap:
			if element.pixmap and os.path.exists(element.pixmap):
				try:
					picon = Image.open(element.pixmap).convert("RGBA")
					picon.thumbnail((w, h))
					canvas.alpha_composite(picon, (x + (w - picon.width) // 2, y + (h - picon.height) // 2))
				except Exception:
					pass
			continue
		if element.bg and not element.transparent and w > 0 and h > 0:
			radius = min(element.radius, w // 2, h // 2)
			draw.rounded_rectangle(box, radius=radius, fill=element.bg)
		if element.borderWidth and element.borderColor:
			draw.rounded_rectangle(box, radius=min(element.radius, w // 2, h // 2), outline=element.borderColor, width=element.borderWidth)
		if element.text:
			fnt = font(element.font)
			lines = fitText(draw, element.text, fnt, w, element.noWrap)
			lineHeight = int(fnt.size * 1.2)
			maxLines = max(1, h // lineHeight)
			lines = lines[:maxLines]
			total = len(lines) * lineHeight
			ty = y if element.valign == "top" else (y + (h - total) // 2 if element.valign == "center" else y + h - total)
			for line in lines:
				tw = draw.textlength(line, font=fnt)
				tx = x if element.halign == "left" else (x + (w - tw) / 2 if element.halign == "center" else x + w - tw)
				draw.text((tx, ty + (lineHeight - fnt.size) / 2), line, font=fnt, fill=element.fg)
				ty += lineHeight
		layer = layer.crop((0, 0, 1920, 1080))
		mask = Image.new("L", canvas.size, 0)
		ImageDraw.Draw(mask).rectangle(box, fill=255)
		clipped = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
		clipped.paste(layer, (0, 0), mask)
		canvas.alpha_composite(clipped)
	canvas.convert("RGB").save(path)
	return path


def openScreen(cls, *args):
	screen = cls(e2.Session(), *args)
	skin = ET.fromstring(cls.skin)
	positions = {}
	for node in skin:
		if node.get("name"):
			x, y = (int(v) for v in node.get("position", "0,0").split(","))
			w, h = (int(v) for v in node.get("size", "0,0").split(","))
			positions[node.get("name")] = ((x, y), (w, h))
	screen.instance = e2.FakeWidget(0, 0)
	for name, component in screen.items():
		if isinstance(component, e2.Label) and component.instance is None:
			(pos, size) = positions.get(name, ((0, 0), (0, 0)))
			component.instance = e2.FakeWidget(*pos)
			component.instance.size = size
	for fn in screen.onLayoutFinish:
		fn()
	e2.advance(0.5)
	return screen


def press(screen, *keys):
	for key in keys:
		screen["actions"].actions[key]()
		e2.advance(0.3)


def main():
	parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
	parser.add_argument("--out", default=os.path.join(ROOT, "out", "preview"))
	args = parser.parse_args()
	os.makedirs(args.out, exist_ok=True)

	names = ["RTÉ One", "RTÉ2", "Virgin Media One", "TG4", "Virgin Media Two", "Virgin Media Three", "RTÉ News", "Cúla4", "RTÉ One +1", "Virgin Media One +1"]
	services, now = e2.makeServices(0, extraNames=names)
	titles = ["Six One News", "The Late Late Show", "Fair City", "Nuacht", "Ireland AM", "Coronation Street", "Prime Time", "Ros na Rún", "Winning Streak", "Claire Byrne Live", "Room to Improve", "Love/Hate"]
	for i, (ref, name) in enumerate(services):
		events = e2.EPG[ref.toString()]
		e2.EPG[ref.toString()] = [(eid, b, d, titles[(i * 3 + n) % len(titles)], "A short description of this programme from the EPG.", "Longer details about the episode, the presenters and what to expect.") for n, (eid, b, d, t, s, x) in enumerate(events)]

	# Stand-in channel logos (the box uses its installed picons).
	logoDir = os.path.join(args.out, "logos")
	os.makedirs(logoDir, exist_ok=True)
	palette = [(0, 94, 184), (203, 32, 39), (230, 0, 126), (0, 150, 136), (120, 40, 140), (255, 140, 0), (0, 70, 130), (90, 180, 60)]
	for i, (ref, name) in enumerate(services[:8]):
		logo = Image.new("RGBA", (220, 132), (0, 0, 0, 0))
		draw = ImageDraw.Draw(logo)
		draw.rounded_rectangle([8, 20, 212, 112], radius=18, fill=palette[i % len(palette)] + (255,))
		label = "".join(word[0] for word in name.replace("+1", "").split())[:3]
		fnt = font("Bold;48")
		tw = draw.textlength(label, font=fnt)
		draw.text(((220 - tw) / 2, 40), label, font=fnt, fill=(255, 255, 255, 255))
		path = os.path.join(logoDir, "%d.png" % i)
		logo.save(path)
		e2.PICONS[ref.toString()] = path

	made = []
	home = openScreen(Home.HaloHome, services, 2, services[2][0].toString())
	made.append(render(home, os.path.join(args.out, "home.png")))
	press(home, "right", "right")
	made.append(render(home, os.path.join(args.out, "home-moved.png")))
	press(home, "up", "right")
	made.append(render(home, os.path.join(args.out, "home-menu.png")))

	guide = openScreen(Guide.HaloGuide, services, 0, e2.FakeRecordTimers(), "Favourites", services[0][0].toString())
	made.append(render(guide, os.path.join(args.out, "guide.png")))
	press(guide, "right", "down", "green")
	made.append(render(guide, os.path.join(args.out, "guide-moved.png")))
	for path in made:
		print(path)


if __name__ == "__main__":
	main()
