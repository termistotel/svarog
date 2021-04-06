from pylib.movable_content import StepProgButton, ManualProgButton
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.togglebutton import ToggleButton
from kivy_garden.graph import Graph, MeshLinePlot, SmoothLinePlot, LinePlot, HBar, ScatterPlot

from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.relativelayout import RelativeLayout
from kivy.graphics.texture import Texture
from kivy.clock import Clock

from kivy.properties import ObjectProperty, NumericProperty, StringProperty

from functools import partial

import numpy as np
import cv2

import json, requests, time, datetime

# Function for converting cv2 image type, to kivy texture type
def picToTextureBuffer(matrix):
    return cv2.flip(matrix[:,:,[2,1,0]],0).tostring()

key_order = ["ar_flow", "h2_flow", "Temperature_sample", "Temperature_halcogenide", "time"]
init_data = {}
for key in key_order:
    init_data[key] = np.ones((0,), dtype= np.float32)

class MainBox(RelativeLayout):
    graph_data = init_data.copy()
    getps = NumericProperty(2.0)
    max_step_num = 5
    min_step_num = 0
    main_pad_y = NumericProperty(0.05)
    main_pad_x = NumericProperty(0.05)
    step_config_size_hint_y = 0.99/max_step_num
    setpointTimer = None
    setpoints = {"ar_flow": 0, "h2_flow": 0, "Temperature_sample": 0, "Temperature_halcogenide": 0}
    setpoints_toset = {}
    address = "127.0.0.1"
    port = "1234"
    plot_points_num = 1000

    def change_step_num(self, dn):
        new_step_num = int(self.ids.step_num.text) + dn
        new_step_num = min(self.max_step_num, max(self.min_step_num, new_step_num))
        self.ids.step_num.text = str(new_step_num)

        self.change_choices(new_step_num)

    def change_choices(self, n):
        choice_bar = self.choice_bar
        for widget in self.steps:
            if widget in choice_bar.children:
                choice_bar.remove_widget(widget)
            if widget.lockChild in self.children:
                self.remove_widget(widget.lockChild)

        for i, widget in zip(range(n), self.steps):
            self.add_widget(widget.lockChild)
            choice_bar.add_widget(widget)
        choice_bar.add_widget(Label(size_hint_y=1-self.step_config_size_hint_y*n))

    def drop_data(self):
        self.graph_data= init_data.copy()
        # self.graph_data["time"] = []
        # self.graph_data["ar_flow"] = []
        # self.graph_data["h2_flow"] = []
        # self.graph_data["Temperature_sample"] = []
        # self.graph_data["Temperature_halcogenide"] = []

    def set_plot_points(self):
        t0 = self.t0.timestamp()
        N = max((len(self.graph_data["time"])//self.plot_points_num)*2, 1)

        ts = self.graph_data["time"][::N]
        arfs = self.graph_data["ar_flow"][::N]
        h2fs = self.graph_data["h2_flow"][::N]
        sTs = self.graph_data["Temperature_sample"][::N]
        hTs = self.graph_data["Temperature_halcogenide"][::N]
        # print(N, type(ts), ts.size, np.min(ts), np.max(ts))
        # print(N, type(arfs), arfs.size, np.min(arfs), np.max(arfs))        

        self.control.ar_flow_plot.points = [((t - t0)/60, v) for t, v in zip(ts, arfs)]
        self.control.h2_flow_plot.points = [((t - t0)/60, v) for t, v in zip(ts, h2fs)]
        self.control.samp_temp_plot.points = [((t - t0)/60, v) for t, v in zip(ts, sTs)]
        self.control.halc_temp_plot.points = [((t - t0)/60, v) for t, v in zip(ts, hTs)]

    def getmaxys(self):
        maxys = []
        for graph in self.graphs:
            maxy = max(max([point[1] for point in graph.plots[0].points], default=graph.ymax),
                        max(graph.plots[1].points, default=graph.ymax))
            maxys.append(maxy)
        return maxys

    def update_graphs(self, values):
        t0 = self.t0.timestamp()
        maxys = self.getmaxys()
        # maxys = [np.max(values[key]) for key in key_order]

        ts = values["time"]
        for t, val in zip((ts-t0)/60, values["ar_flow"]):
            self.control.ar_flow_plot.points.append([t, val])
        for t, val in zip((ts-t0)/60, values["h2_flow"]):            
            self.control.h2_flow_plot.points.append([t, val])
        for t, val in zip((ts-t0)/60, values["Temperature_sample"]):            
            self.control.samp_temp_plot.points.append([t, val])
        for t, val in zip((ts-t0)/60, values["Temperature_halcogenide"]):            
            self.control.halc_temp_plot.points.append([t, val])
        maxys[0] = np.amax(values["ar_flow"], initial=maxys[0])
        maxys[1] = np.amax(values["h2_flow"], initial=maxys[1])
        maxys[2] = np.amax(values["Temperature_sample"], initial=maxys[2])
        maxys[3] = np.amax(values["Temperature_halcogenide"], initial=maxys[3])

        tmax = np.amax(ts, initial=t0)

        N = (len(self.control.ar_flow_plot.points)//2) * 2
        if N > self.plot_points_num:
            # print(N)
            self.set_plot_points()

        widget_list = self.graphs

        t0 = self.t0.timestamp()
        for graph, maxy in zip(widget_list, maxys):
            if maxy > graph.ymax:
                graph.ymax *= 2
                graph.y_ticks_major = (graph.ymax - graph.ymin)/4

            if (tmax - t0)/60 > graph.xmax:
                graph.xmax *= 2
                graph.x_ticks_major = (graph.xmax - graph.xmin)/4

    def update_setpoints(self, setpoints, update_widgets = False):
        for key in setpoints:
            self.setpoints[key] = float(setpoints[key])

        tmin, tmax = self.control.ids.ar_flow.xmin, self.control.ids.ar_flow.xmax

        self.control.ar_flow_setpoint_plot.points = [(self.setpoints["ar_flow"])]
        self.control.h2_flow_setpoint_plot.points = [(self.setpoints["h2_flow"])]
        self.control.samp_temp_setpoint_plot.points = [(self.setpoints["Temperature_sample"])]
        self.control.halc_temp_setpoint_plot.points = [(self.setpoints["Temperature_halcogenide"])]

        if update_widgets:
            self.manual_button.lockChild.ids.ar_flow.value = self.setpoints["ar_flow"]
            self.manual_button.lockChild.ids.h2_flow.value = self.setpoints["h2_flow"]
            self.manual_button.lockChild.ids.samp_temp.value = self.setpoints["Temperature_sample"]
            self.manual_button.lockChild.ids.halc_temp.value = self.setpoints["Temperature_halcogenide"]

    def get_data(self, address='127.0.0.1', port="1234", update_widgets = False, dt = 0):
        url = "http://"+address+":"+port+"/get_vals"
        current_t = self.current_t.timestamp()

        try:
            resp = requests.get(url, params={"t0": current_t-2})
            returned = resp.text
            returned = json.loads(returned)
            resp.close()

            graph_data = returned["data"]
            setpoints = returned["setpoints"]

            indices = []
            time_length = len(graph_data["time"])
            for i, val in enumerate(graph_data["time"]):
                if val in self.graph_data["time"][-time_length:]:
                    continue
                else:
                    indices.append(i)

            for key in graph_data:
                graph_data[key] = np.array(graph_data[key])[indices]
                self.graph_data[key] = np.append(self.graph_data[key], graph_data[key])

            if graph_data["time"].size > 0:
                current_t = np.amax(graph_data["time"])
                # print(np.max(graph_data["time"]))
            else:
                current_t = min(current_t + float(returned["maxTime"]), datetime.datetime.now().timestamp())
            self.current_t = datetime.datetime.fromtimestamp(current_t)

            self.update_graphs(graph_data)
            self.update_setpoints(setpoints, update_widgets=update_widgets)

            Clock.schedule_once(partial(self.get_data, address, port, False), 1/self.getps)

        except Exception as e:
            print(e)

    def auto_toggle(self, widget):
        value = widget.state
        if value == "down":
            self.start_box.remove_widget(self.manual_bar)
            self.setup_bar.remove_widget(self.step_ph)
            self.manual_button.state="normal"

            self.start_box.add_widget(self.choice_bar)
            self.setup_bar.add_widget(self.step_box, index=-2)

        else:
            self.start_box.remove_widget(self.choice_bar)
            self.setup_bar.remove_widget(self.step_box)
            for widget in self.steps:
                widget.state = "normal"

            self.start_box.add_widget(self.manual_bar)
            self.setup_bar.add_widget(self.step_ph, index=-2)

    def connect(self, address, port):
        self.address = address
        self.port = port
        Clock.schedule_once(partial(self.get_data, address, port, True), 1/self.getps)

    def set_setpoint(self, setpoints):
        any_flag = False
        for key in setpoints:
            if self.setpoints[key] != setpoints[key]:
                self.setpoints_toset[key] = setpoints[key]
                any_flag = True
        if any_flag and (self.setpointTimer is None):
            self.setpointTimer = Clock.schedule_once(self.send_setpoint, 1/self.getps)

    def send_setpoint(self, dt=0):
        address = self.address
        port = self.port
        url = "http://"+address+":"+port+"/set_setpoints"

        params = {}
        for key in self.setpoints_toset:
            params[key] = self.setpoints_toset[key]
        try:
            resp = requests.get(url, params=params)
            resp.close()
        except Exception as e:
            print(e)
        self.setpointTimer = None
        self.setpoints_toset = {}

    def changet0(self, date=None, time=None):
        if date is None:
            date = datetime.datetime.now().date()
        else:
            date=datetime.date.fromisoformat(date)

        if time is None:
            time = datetime.datetime.now().time()
            time = time.replace(microsecond=0)
        else:
            time=datetime.time.fromisoformat(time)

        self.t0 = datetime.datetime.combine(date, time)
        # self.t0 = self.t0.replace(microsecond=0)
        self.current_t = self.t0

        self.drop_data()
        [graph.set_defaults() for graph in self.graphs]
        self.set_plot_points()
        self.update_time_text()

    def update_time_text(self):
        self.ids.date.text = self.t0.date().isoformat()
        self.ids.time.text = self.t0.time().isoformat()

    def start_plan(self, address=None, port=None):
        if address is None:
            address = self.address
        if port is None:
            port = self.port
        plan_url = "http://"+address+":"+port+"/add_to_program"
        run_url = "http://"+address+":"+port+"/start_program"

        def send_plan(plan_list):
            if not plan_list:
                return
            resp = requests.get(plan_url, params=plan_list[0])
            resp.close()
            send_plan(plan_list[1:])

        # Read plan
        plan_list = []
        N = int(self.ids.step_num.text)
        for plan_widget in [step.lockChild for step in self.steps[:N]]:
            plan = {"ar_flow": plan_widget.ids.ar_flow.value,
                    "h2_flow": plan_widget.ids.h2_flow.value,
                    "Temperature_sample": plan_widget.ids.samp_temp.value,
                    "Temperature_halcogenide": plan_widget.ids.halc_temp.value,
                    "time": plan_widget.ids.time.value}
            plan_list.append(plan)

        # Send plan
        send_plan(plan_list)

        # Start program
        name = datetime.datetime.now().isoformat()
        resp = requests.get(run_url, params={"state": "start", "name": name})
        resp.close()

    def __init__(self, db, **kwargs):
        super(MainBox, self).__init__(**kwargs)
        self.database = db
        self.t0 = datetime.datetime.now()
        self.t0 = self.t0.replace(microsecond=0)
        self.current_t = self.t0

        # Functions for quick debugging
        # self.browseButtonFunction = partial(self.browserReturnFunction, ("/home/alion/Desktop/cat.jpg",0), 0)
        # self.applyButtonFunction = partial(self.browserReturnFunction, ("/home/alion/Desktop/black_cat.jpg",0), 0)

        reserved_x = self.ids.choice_bar.size_hint_x
        reserved_y = self.ids.setup_bar.size_hint_y
        self.display_box = self.ids.display_box

        # Main Widgets
        self.control=Control()
        # self.browser=FileBrowser(main=self)
        # self.kernelEditor=KernelEditor(main=self)

        # Step configs
        self.steps = [StepProgButton(self, pos_hint={"y": self.step_config_size_hint_y*(self.max_step_num-(i+1))}, size_hint_y=self.step_config_size_hint_y) for i in range(self.max_step_num)]

        # Step_increments
        self.ids.step_num_inc.on_press=partial(self.change_step_num, 1)
        self.ids.step_num_dec.on_press=partial(self.change_step_num, -1)

        self.display_box.add_widget(self.control)

        self.start_box = self.ids.start_box
        self.choice_bar = self.ids.choice_bar
        self.manual_bar = self.ids.manual_bar
        self.manual_button = ManualProgButton(self)
        self.manual_bar.add_widget(self.manual_button)
        self.add_widget(self.manual_button.lockChild)

        self.setup_bar = self.ids.setup_bar
        self.step_box = self.ids.step_box
        self.step_ph = self.ids.step_ph

        self.start_box.remove_widget(self.choice_bar)
        self.setup_bar.remove_widget(self.step_box)

        # save references to graphs
        ar_widg = self.control.ids.ar_flow
        h2_widg = self.control.ids.h2_flow
        sampT_widg = self.control.ids.samp_temp
        halcT_widg =self.control.ids.halc_temp
        self.graphs = [ar_widg, h2_widg, sampT_widg, halcT_widg]

        self.update_time_text()

        # self.connect(self.address, self.port)
        # self.setup_bar.add_widget(self.step_ph, index=-2)
        # self.add_widget(self.start_box, index=1)

    # This is required for android to correctly display widgets on screen rotate
    def on_size(self, val1, val2):
        Clock.schedule_once(lambda dt: self.canvas.ask_update(), 0.2)

class Control(GridLayout):
    """docstring for Control"""
    def __init__(self, **kwargs):
        super(Control, self).__init__(**kwargs)     

        flow_color = [1, 0, 0, 1]
        temp_color = [0, 1, 0, 1]
        setpoint_color = [0.5, 0.5, 1, 1]
        # point_size = 2
        line_width = 2

        # self.ar_flow_plot = ScatterPlot(color=flow_color, point_size=point_size)
        self.ar_flow_plot = LinePlot(color=flow_color, line_width=line_width)
        self.ar_flow_setpoint_plot = HBar(color=setpoint_color)
        self.ids.ar_flow.add_plot(self.ar_flow_plot)
        self.ids.ar_flow.add_plot(self.ar_flow_setpoint_plot)

        # self.h2_flow_plot = ScatterPlot(color=flow_color, point_size=point_size)
        self.h2_flow_plot = LinePlot(color=flow_color, line_width=line_width)
        self.h2_flow_setpoint_plot = HBar(color=setpoint_color)
        self.ids.h2_flow.add_plot(self.h2_flow_plot)
        self.ids.h2_flow.add_plot(self.h2_flow_setpoint_plot)

        # self.samp_temp_plot = ScatterPlot(color=temp_color, point_size=point_size)
        self.samp_temp_plot = LinePlot(color=temp_color, line_width=line_width)
        self.samp_temp_setpoint_plot = HBar(color=setpoint_color)
        self.ids.samp_temp.add_plot(self.samp_temp_plot)
        self.ids.samp_temp.add_plot(self.samp_temp_setpoint_plot)

        # self.halc_temp_plot = ScatterPlot(color=temp_color, point_size=point_size)
        self.halc_temp_plot = LinePlot(color=temp_color, line_width=line_width)
        self.halc_temp_setpoint_plot = HBar(color=setpoint_color)
        self.ids.halc_temp.add_plot(self.halc_temp_plot)
        self.ids.halc_temp.add_plot(self.halc_temp_setpoint_plot)

class ControlBox(BoxLayout):
    """docstring for ControlBox"""
    perc_inc = NumericProperty(0.1)
    name = StringProperty("tst")
    typ = StringProperty("exp")
    min_val = NumericProperty(0)
    max_val = NumericProperty(1)
    value = NumericProperty(0)
    precision = NumericProperty(1)

    def change_value(self, sign, *args):
        value = float(self.value)
        if self.typ == "exp":
            value += sign*self.perc_inc*value
        elif self.typ == "linear":
            value += sign*self.perc_inc

        value = min(self.max_val, max(self.min_val, value))
        self.value = value

    def __init__(self, **kwargs):
        super(ControlBox, self).__init__(**kwargs)

        # Add control functions
        # self.ids.inc.on_press = print
        # self.ids.inc.on_press = partial(self.change_value, 1)
        # self.ids.dec.on_press = partial(self.change_value, -1)

class RTdisp(Graph):
    """docstring for RTdisp"""

    default_x = (-0, 15/8)
    default_y = (-0, 1)
    default_ticks = (0.25, 0.5)

    def set_defaults(self):
        self.xmin = self.default_x[0]
        self.xmax = self.default_x[1]

        self.ymin = self.default_y[0]
        self.ymax = self.default_y[1]

        self.x_ticks_major = self.default_ticks[0]
        self.y_ticks_major = self.default_ticks[1]

    def __init__(self, *args, **kwargs):
        # self.default_y = (-0, 1)
        # self.default_x = (-0, 1)
        # self.default_ticks = (0.25, 0.25)
        super(RTdisp, self).__init__(*args, **kwargs)
