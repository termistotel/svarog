import kivy
kivy.require('2.0.0') # replace with your current kivy version !
from kivy.app import App
from kivy.config import Config

class SvarogApp(App):
    def build(self):
        mainbox = MainBox()
        return mainbox

if __name__ == '__main__':
    # if hasattr(sys, '_MEIPASS'):
    #     resource_add_path(os.path.join(sys._MEIPASS))
    Config.set('graphics', 'window_state', 'maximized')
    from pylib.mainbox import MainBox
    SvarogApp().run()

