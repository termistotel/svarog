import kivy
kivy.require('1.10.0') # replace with your current kivy version !

from kivy.app import App

from pylib.mainbox import MainBox
from pylib.dblink import DBlink

class SvarogApp(App):
	dbFilename = "svarog.db"

	def connectToDb(self):
		return DBlink(self.dbFilename)

	def build(self):
		db = self.connectToDb()
		mainbox = MainBox(db=db)
		return mainbox

if __name__ == '__main__':
    SvarogApp().run()

