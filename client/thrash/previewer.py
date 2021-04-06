from kivy.uix.relativelayout import RelativeLayout
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.properties import NumericProperty
from kivy.properties import ObjectProperty
from kivy.properties import StringProperty
from kivy.graphics.texture import Texture

from pylib.FilterMenu import ClickMenuButton
from kivy.clock import Clock

class Previewer(RelativeLayout):
	ratio = NumericProperty()
	src = ObjectProperty()
	srcImg = ObjectProperty()
	convImg = ObjectProperty()
	srcLoc = StringProperty('')

	def __init__(self, main, **kwargs):
		self.ratio = 1
		self.srcImg = Texture.create(size=(0,0))
		self.convImg = Texture.create(size=(0,0))

		# Create Filter selector button and bound content
		self.filterselector = ClickMenuButton(main=main, contentLength=0.6)

		super(Previewer, self).__init__(**kwargs)

		# Set the height of bound content
		self.ids.mainview.bind(height=self.filterselector.lockChild.setter('height'))
		self.add_widget(self.filterselector.lockChild)
		self.add_widget(self.filterselector)

		# Set press-actions for buttons
		self.ids.brbutton.on_press=main.browseButtonFunction
		self.ids.applybutton.on_press=main.applyButtonFunction

	def adjustImageLayout(self):
		self.ids.imdisplaycont.chLayout()


class ImageDisplayContainer(BoxLayout):
	# Ratio of image's height/width. Should be bound 
	# to previewer's ratio property in kv file.
	# Initialise it as a different value to avoid division by zero
	ratio = NumericProperty(0)

	# Change box's layout between horizontal and vertical depending 
	# on the size of view area it would cover
	def chLayout(self):
		if self.ratio == 0:
			return

		if (self.ratio)*self.width**2.0 > (1/self.ratio)*self.height**2.0:
			self.orientation='horizontal'
		else:
			self.orientation='vertical'

	def on_size(self, val1, val2):
		self.chLayout()



class ImageDisplay(Label):
	ratio = NumericProperty(0)
	
	def on_size(self, val1, val2):
		self.parent.chLayout()


# Update all children in a tree, probably unused function

def updateAll(self):
	Clock.schedule_once(lambda dt: self.canvas.ask_update(), 0.2)

	if self.children == []:
		return
	for child in self.children:
		updateAll(child)