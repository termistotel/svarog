import kivy
kivy.require('1.10.0') # replace with your current kivy version !
from kivy.app import App
from pylib.mainbox import MainBox
# from kivy.core.window import Window
from kivy.config import Config
from kivy.resources import resource_add_path, resource_find
import sys

class SvarogApp(App):
    def build(self):
        mainbox = MainBox()
        return mainbox

if __name__ == '__main__':
    # Window.fullscreen = 'auto'
    # Config.set('graphics', 'fullscreen', 'auto')
    if hasattr(sys, '_MEIPASS'):
        resource_add_path(os.path.join(sys._MEIPASS))
    Config.set('graphics', 'window_state', 'maximized')
    SvarogApp().run()

