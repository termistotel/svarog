from kivy.uix.boxlayout import BoxLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.gridlayout import GridLayout
from kivy.uix.button import Button
from kivy.uix.textinput import TextInput
from kivy.properties import NumericProperty

import numpy as np

class KernelEditor(BoxLayout):

	def increaseDimension(self):
		self.ids.matrix.dimension+=2

	def __init__(self, main, **kwargs):
		super(KernelEditor, self).__init__(**kwargs)
		self.ids.returnbutton.on_press = main.kernelEditorReturnFunction
		self.ids.savekernelbutton.on_press = lambda: main.kernelEditorSave(group=self.ids.filtergroup.text, name=self.ids.filtername.text, mode="grayscale", npArray=self.ids.matrix.toNumpy())

		self.ids.dimensionbutton.on_press=self.increaseDimension


class KernelMatrix(GridLayout):

	dimension = NumericProperty(3)
	childWidth = NumericProperty(0)
	matrix = []

	def drawMatrix(self):
		self.clear_widgets()
		self.matrix = [TextInput(text='0') for x in range(self.dimension**2)]
		for elem in self.matrix:
			self.add_widget(elem)

	def toNumpy(self):
		return np.array(list(map(lambda x: float(x.text), self.matrix))).reshape(self.dimension,self.dimension)

	def on_dimension(self, val1, val2):
		self.drawMatrix()
	
	def __init__(self, **kwargs):
		super(KernelMatrix, self).__init__(**kwargs)
		self.drawMatrix()