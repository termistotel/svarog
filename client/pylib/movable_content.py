from kivy.uix.boxlayout import BoxLayout
from kivy.uix.togglebutton import ToggleButton

from kivy.properties import NumericProperty

from kivy.animation import Animation

class StepProgButton(ToggleButton, ):
	number = NumericProperty(0)

	def __init__(self, main, contentLength=0.7, number=0, **kwargs):
		self.main = main
		self.number = number
		self.contentLength = contentLength
		self.lockChild = StepMoveableContent(main, self)
		super(StepProgButton, self).__init__(**kwargs)

	def on_state(self, val1, state):
		if state=="normal":
			Animation(x = self.lockChild.lowVal, duration=0.4, t='out_cubic').start(self.lockChild)
			print(self.y)
		else:
			Animation(x = self.lockChild.highVal, duration=0.4, t='out_cubic').start(self.lockChild)

class StepMoveableContent(BoxLayout):
	lowVal = NumericProperty(0)
	highVal = NumericProperty(0)

	def __init__(self, main, lockParent, **kwargs):
		self.main = main
		self.lockParent = lockParent
		super(StepMoveableContent, self).__init__(**kwargs)

	def on_lowVal(self, val1, val2):
		if self.lockParent.state=="normal":
			self.x = self.lowVal
		else:
			self.x = self.highVal

class ManualProgButton(ToggleButton):
	def __init__(self, main, contentLength=0.7, **kwargs):
		self.contentLength = contentLength
		self.lockChild = ManualMoveableContent(main, self)
		super(ManualProgButton, self).__init__(**kwargs)

	def on_state(self, val1, state):
		if state=="normal":
			Animation(x = self.lockChild.lowVal, duration=0.4, t='out_cubic').start(self.lockChild)
		else:
			Animation(x = self.lockChild.highVal, duration=0.4, t='out_cubic').start(self.lockChild)

class ManualMoveableContent(BoxLayout):
	lowVal = NumericProperty(0)
	highVal = NumericProperty(0)

	def __init__(self, main, lockParent, **kwargs):
		self.lockParent = lockParent
		self.main = main
		super(ManualMoveableContent, self).__init__(**kwargs)

	def on_lowVal(self, val1, val2):
		if self.lockParent.state=="normal":
			self.x = self.lowVal
		else:
			self.x = self.highVal
