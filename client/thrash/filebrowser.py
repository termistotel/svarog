from kivy.uix.boxlayout import BoxLayout
from kivy.uix.filechooser import FileChooser


class FileBrowser(BoxLayout):
	def __init__(self, main, **kwargs):
		super(FileBrowser, self).__init__(**kwargs)
		self.ids.filechooser.on_submit=main.browserReturnFunction


class MyFileChooser(FileChooser):
	pass

"""
	def __init__(self,  **kwargs):
		super(MyFileChooser, self).__init__(**kwargs)

	def on_submit(self, selection, touch):
		print("on submit: ")
		print(selection)
		print(touch)
	

	def on_entry_added(self,entry, parent):
		#print("on entry_added: ")
		#print(entry)
		#print(parent)
		return super(MyFileChooser,self).on_entry_added(entry,parent)
		
	
	def on_subentry_to_entry(self,entry, parent):
		print("on subentry to entry: ")
		print(entry)
		print(parent)

	def on_entries_cleared(self):
		#print("on entries cleared")
		return super(MyFileChooser,self).on_entries_cleared()
"""
	