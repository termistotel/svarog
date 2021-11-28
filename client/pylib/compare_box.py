from kivy.uix.relativelayout import RelativeLayout
from kivy.uix.togglebutton import ToggleButton
from kivy.properties import StringProperty, ObjectProperty

from pylib.control_widgets import flow_color, temp_color

from time import sleep
from kivy.clock import Clock
import requests, json, re

import numpy as np

key_order = ["ar_flow", "ar_flow_setpoint", "h2_flow", "h2_flow_setpoint",
             "Temperature_sample", "Temperature_sample_setpoint",
             "Temperature_halcogenide", "Temperature_halcogenide_setpoint",
             "Power_main", "Power_seco", "time"]
temp_color = np.array(temp_color)
flow_color = np.array(flow_color)
init_data = {}
for key in key_order:
    init_data[key] = np.ones((0,), dtype= np.float32)
initial_maxys = [200, 5, 300, 200]

class ReviewContainer(RelativeLayout):
    prog_list_url = StringProperty("")
    data_get_url = StringProperty("")
    graph_data = {'left': init_data.copy(), 'right': init_data.copy()}
    plot_points_num = 500
    def __init__(self, **kwargs):
        super(ReviewContainer, self).__init__(**kwargs)
        # self.initialize_review_box()

        Clock.schedule_once(self.initialize_review_box, 1)
        self.prog_geting = Clock.schedule_interval(lambda dt: self.get_progs(), 30)

    def initialize_review_box(self, dt):
        # save references to graphs
        ar_widg = self.ids.control.ids.ar_flow
        h2_widg = self.ids.control.ids.h2_flow
        sampT_widg = self.ids.control.ids.samp_temp
        halcT_widg =self.ids.control.ids.halc_temp
        self.graphs = [ar_widg, h2_widg, sampT_widg, halcT_widg]

        self.samp_temp_plot_left = self.ids.control.add_plot(temp_color, 1.5)
        self.samp_temp_plot_right = self.ids.control.add_plot(temp_color*0.7, 1.5)
        self.halc_temp_plot_left = self.ids.control.add_plot(temp_color, 1.5)
        self.halc_temp_plot_right = self.ids.control.add_plot(temp_color*0.7, 1.5)
        self.ar_flow_plot_left = self.ids.control.add_plot(flow_color, 1.5)
        self.ar_flow_plot_right = self.ids.control.add_plot(flow_color*0.7, 1.5)
        self.h2_flow_plot_left = self.ids.control.add_plot(flow_color, 1.5)
        self.h2_flow_plot_right = self.ids.control.add_plot(flow_color*0.7, 1.5)
        self.graphs[0].add_plot(self.ar_flow_plot_left)
        self.graphs[0].add_plot(self.ar_flow_plot_right)
        self.graphs[1].add_plot(self.h2_flow_plot_left)
        self.graphs[1].add_plot(self.h2_flow_plot_right)
        self.graphs[2].add_plot(self.samp_temp_plot_left)
        self.graphs[2].add_plot(self.samp_temp_plot_right)
        self.graphs[3].add_plot(self.halc_temp_plot_left)
        self.graphs[3].add_plot(self.halc_temp_plot_right)

    def set_plot_points(self):
        NL = max((len(self.graph_data["left"]["time"])//self.plot_points_num)*2, 1)
        NR = max((len(self.graph_data["right"]["time"])//self.plot_points_num)*2, 1)

        plots_left = [self.ar_flow_plot_left, self.h2_flow_plot_left, 
                      self.samp_temp_plot_left, self.halc_temp_plot_left]
        plots_right = [self.ar_flow_plot_right, self.h2_flow_plot_right, 
                      self.samp_temp_plot_right, self.halc_temp_plot_right]
        gd_keys = ['ar_flow', 'h2_flow', 'Temperature_sample', 'Temperature_halcogenide']

        ts_left = self.graph_data['left']["time"][::NL]
        ts_right = self.graph_data['right']["time"][::NR]
        t0r, t0l = np.amin(ts_right, initial=1e20), np.amin(ts_left, initial=1e20)
        for key, plot_left, plot_right in zip(gd_keys, plots_left, plots_right):
            gds = self.graph_data["left"][key][::NL]
            plot_left.points = [((t-t0l)/60, v) for t, v in zip(ts_left, gds)]
            gds = self.graph_data["right"][key][::NR]
            plot_right.points = [((t-t0r)/60, v) for t, v in zip(ts_right, gds)]

        values=self.graph_data
        for graph, maxy in zip(self.graphs, initial_maxys):
            graph.ymax = maxy
            graph.y_ticks_major = (graph.ymax - graph.ymin)/4
            graph.xmax = 2
            graph.x_ticks_major = (graph.xmax - graph.xmin)/4

        maxys = initial_maxys.copy()
        maxys[0] = np.amax(values['left']['ar_flow'], initial=np.amax(values['right']["ar_flow"], initial=200))
        maxys[1] = np.amax(values['left']['h2_flow'], initial=np.amax(values['right']["h2_flow"], initial=5))
        maxys[2] = np.amax(values['left']['Temperature_sample'], initial=np.amax(values['right']["Temperature_sample"], initial=maxys[2]))
        maxys[3] = np.amax(values['left']['Temperature_halcogenide'], initial=np.amax(values['right']["Temperature_halcogenide"], initial=maxys[3]))
        tmax = np.amax(ts_right-t0r, initial=np.amax(ts_left-t0l, initial=0))

        for graph, maxy in zip(self.graphs, maxys):
            while maxy > graph.ymax:
                graph.ymax *= 2
                graph.y_ticks_major = (graph.ymax - graph.ymin)/4
                # self.set_plot_points()

            while (tmax)/60 > graph.xmax:
                graph.xmax *= 2
                graph.x_ticks_major = (graph.xmax - graph.xmin)/4


    # Add
    def add_to_bar(self, bar, group, data = {}):
        button = ProgSelector(self, height=40, group= group, font_size='12sp')
        button.size_hint_y = None
        button.pos_hint_y = None
        button.data = data
        # button.text = data['name']
        button.height = 80
        button.y = bar.y + sum([child.height for child in bar.children])# - button.height
        bar.add_widget(button)
        # bar.height = sum([child.height for child in bar.children])

    def review_toggle(self, state='normal'):
        self.parent.review_toggle(state=state)

    def get_progs(self):
        try:
            resp = requests.get(self.prog_list_url)
            returned = resp.text
            returned = json.loads(returned)
            resp.close()
            self.update_programs(returned["data"])
        except Exception as e:
            print(e)

    def update_programs(self, progs):
        left_names = [child.name for child in self.left_bar.children]
        right_names = [child.name for child in self.right_bar.children]
        for prog in progs:
            start_t, end_t, name = prog
            if not (name in left_names):
                self.add_to_bar(self.left_bar, 'left', {'start_t': start_t, 'end_t': end_t, 'name': name})
            if not (name in right_names):
                self.add_to_bar(self.right_bar, 'right', {'start_t': start_t, 'end_t': end_t, 'name': name})

    def get_data(self, start_t, stop_t, group='left'):
        try:
            # Get request to server 
            resp = requests.get(self.data_get_url, params={"t0": start_t, "tend": stop_t}, timeout=5)
            returned = resp.text
            returned = json.loads(returned)
            resp.close()

            graph_data = returned["data"]

            # Add new data to graph data by numpy appending/concatenating
            for key in graph_data:
                self.graph_data[group][key] = np.array(graph_data[key])

            self.set_plot_points()
        except Exception as e:
            print(e)

    def clear_data(self, group='left'):
        self.graph_data[group] = init_data.copy()

class ProgSelector(ToggleButton):
    """docstring for ProgSelector"""
    name = StringProperty("")
    data = ObjectProperty({"name": "", "start_t": 0, "end_t": 0})
    def __init__(self, container, *args, **kwargs):
        super(ProgSelector, self).__init__(*args, **kwargs)
        self.container = container

    def name_to_text(self, name):
        reg_exp = '((.+?)_+)?(.+)T(.+)'
        m = re.match(reg_exp, name)
        total_name = ""
        if m:
            if m.group(2):
                total_name = m.group(2)
            if total_name != "":
                total_name += "\n"
            total_name += m.group(3) + "\n"
            total_name += m.group(4) + "\n"
            return total_name
        else:
            return name

    def on_state(self, *args):
        if self.state == 'down':
            self.container.get_data(self.data['start_t'], self.data['end_t'], group=self.group)
        else:
            self.container.clear_data(group=self.group)