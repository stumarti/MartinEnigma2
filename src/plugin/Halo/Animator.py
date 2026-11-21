# Halo animation helper.
#
# On a Halo image, Enigma2's widgets have animateMove() (the C++ engine from
# the Halo patch): the move runs in C++ on its own timer. On stock openATV that
# method is missing, so the same animation runs from Python on an eTimer. The
# result looks the same; the C++ path is smoother and cheaper.

from time import monotonic

from enigma import ePoint, eTimer

EASE_LINEAR = 0
EASE_OUT_CUBIC = 1
EASE_IN_OUT_CUBIC = 2
EASE_OUT_BACK = 3

FRAME_MS = 16


def ease(curve, t):
	if t <= 0.0:
		return 0.0
	if t >= 1.0:
		return 1.0
	if curve == EASE_LINEAR:
		return t
	if curve == EASE_IN_OUT_CUBIC:
		if t < 0.5:
			return 4.0 * t * t * t
		f = -2.0 * t + 2.0
		return 1.0 - f * f * f / 2.0
	if curve == EASE_OUT_BACK:
		c1 = 1.70158
		c3 = c1 + 1.0
		f = t - 1.0
		return 1.0 + c3 * f * f * f + c1 * f * f
	f = 1.0 - t
	return 1.0 - f * f * f


def hasNativeAnimation(instance):
	return instance is not None and hasattr(instance, "animateMove")


class _PythonMove:
	def __init__(self, instance, start, end, durationMs, curve, onDone):
		self.instance = instance
		self.start = start
		self.end = end
		self.duration = max(1, durationMs) / 1000.0
		self.curve = curve
		self.onDone = onDone
		self.began = monotonic()
		self.timer = eTimer()
		self.timer.callback.append(self.frame)
		self.apply(0.0)
		self.timer.start(FRAME_MS, False)

	def apply(self, progress):
		e = ease(self.curve, progress)
		x = int(round(self.start[0] + (self.end[0] - self.start[0]) * e))
		y = int(round(self.start[1] + (self.end[1] - self.start[1]) * e))
		self.instance.move(ePoint(x, y))

	def frame(self):
		progress = (monotonic() - self.began) / self.duration
		if progress >= 1.0:
			self.stop(jumpToEnd=True)
			if self.onDone:
				self.onDone()
			return
		self.apply(progress)

	def stop(self, jumpToEnd=True):
		if self.timer is not None:
			self.timer.stop()
			self.timer = None
			if jumpToEnd:
				self.apply(1.0)


class _NativeMove:
	def __init__(self, instance, start, end, durationMs, curve, onDone):
		self.instance = instance
		self.onDone = onDone
		self.timer = None
		instance.animateMove(ePoint(*start), ePoint(*end), int(durationMs), int(curve))
		if onDone:
			self.timer = eTimer()
			self.timer.callback.append(self.finished)
			self.timer.start(int(durationMs) + 20, True)

	def finished(self):
		self.timer = None
		if self.onDone:
			self.onDone()

	def stop(self, jumpToEnd=True):
		if self.timer is not None:
			self.timer.stop()
			self.timer = None
		self.instance.stopAnimation(1 if jumpToEnd else 0)


class Animator:
	"""Runs moves for one screen. Keep one per screen; stop() on close."""

	def __init__(self):
		self.running = {}

	def move(self, instance, start, end, durationMs=250, curve=EASE_OUT_CUBIC, onDone=None):
		"""Move a widget (a screen's or a GUI component's instance) from start
		to end, both (x, y) tuples in the coordinates used by instance.move().
		onDone runs once when the move completes (not when it is cancelled)."""
		self.cancel(instance)
		job = _NativeMove if hasNativeAnimation(instance) else _PythonMove
		self.running[id(instance)] = job(instance, start, end, durationMs, curve, onDone)

	def cancel(self, instance, jumpToEnd=True):
		job = self.running.pop(id(instance), None)
		if job is not None:
			job.stop(jumpToEnd)

	def stop(self):
		for job in list(self.running.values()):
			job.stop(True)
		self.running = {}
