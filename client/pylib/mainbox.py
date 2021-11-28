from pylib.movable_content import StepProgButton, ManualProgButton
from pylib.compare_box import ReviewContainer

from kivy.uix.relativelayout import RelativeLayout

from kivy.uix.label import Label
from kivy.clock import Clock

from kivy.properties import NumericProperty, StringProperty

from functools import partial

import numpy as np

import json, requests, time, datetime
import _thread

# key_order = ["ar_flow", "h2_flow", "Temperature_sample", "Temperature_halcogenide", "time"]
key_order = ["ar_flow", "ar_flow_setpoint", "h2_flow", "h2_flow_setpoint",
             "Temperature_sample", "Temperature_sample_setpoint",
             "Temperature_halcogenide", "Temperature_halcogenide_setpoint",
             "Power_main", "Power_seco", "time"]
init_data = {}
for key in key_order:
    init_data[key] = np.ones((0,), dtype= np.float32)

class MainBox(RelativeLayout):
    _power_max_quickfix = 0.99
    graph_data = init_data.copy()
    getps = NumericProperty(1.0)
    max_step_num = 10
    min_step_num = 0
    main_pad_y = NumericProperty(0.1)
    main_pad_x = NumericProperty(0.06)
    step_config_size_hint_y = 0.2
    setpointTimer = None
    setpoints = {"ar_flow": 0, "h2_flow": 0, "Temperature_sample": 0, "Temperature_halcogenide": 0}
    setpoints_toset = {}
    address = StringProperty("127.0.0.1")
    port = StringProperty("1234")
    plot_points_num = 1000

    def change_step_num(self, dn):
        new_step_num = int(self.ids.step_num.text) + dn
        new_step_num = min(self.max_step_num, max(self.min_step_num, new_step_num))
        self.ids.step_num.text = str(new_step_num)

        self.change_choices(new_step_num)

    def change_choices(self, n):
        step_bar = self.step_bar
        content_bar = self
        for widget in self.steps:
            if widget in step_bar.children:
                step_bar.remove_widget(widget)
            if widget.lockChild in content_bar.children:
                content_bar.remove_widget(widget.lockChild)

        for i, widget in zip(range(n), self.steps):
            content_bar.add_widget(widget.lockChild, index=0)
            step_bar.add_widget(widget)
        # step_bar.add_widget(Label(size_hint_y=1-self.step_config_size_hint_y*n))

    def drop_data(self):
        self.graph_data= init_data.copy()

    def set_plot_points(self):
        t0 = self.t0.timestamp()
        N = max((len(self.graph_data["time"])//self.plot_points_num)*2, 1)

        cnt = self.control
        plots = [cnt.ar_flow_plot, cnt.ar_flow_setpoint_plot, cnt.h2_flow_plot, cnt.h2_flow_setpoint_plot,
                 cnt.samp_temp_plot, cnt.samp_temp_setpoint_plot, cnt.halc_temp_plot, cnt.halc_temp_setpoint_plot,
                 cnt.samp_power_plot, cnt.halc_power_plot]
        gd_keys = key_order

        ts = self.graph_data["time"][::N]
        for key, plot in zip(gd_keys, plots):
            if key =="time":
                continue
            gds = self.graph_data[key][::N]
            if key == 'Power_main':
                plot.points = [((t - t0)/60, v*self.control.ids.samp_temp.ymax*self._power_max_quickfix) for t, v in zip(ts, gds)]
            elif key == 'Power_seco':
                plot.points = [((t - t0)/60, v*self.control.ids.halc_temp.ymax*self._power_max_quickfix) for t, v in zip(ts, gds)]
            else:
                plot.points = [((t - t0)/60, v) for t, v in zip(ts, gds)]

        # arfs = self.graph_data["ar_flow"][::N]
        # h2fs = self.graph_data["h2_flow"][::N]
        # sTs = self.graph_data["Temperature_sample"][::N]
        # sPs = self.graph_data["Power_main"][::N]
        # hTs = self.graph_data["Temperature_halcogenide"][::N]
        # hPs = self.graph_data["Power_seco"][::N]
        # # print(N, type(ts), ts.size, np.min(ts), np.max(ts))
        # # print(N, type(arfs), arfs.size, np.min(arfs), np.max(arfs))        

        # self.control.ar_flow_plot.points = [((t - t0)/60, v) for t, v in zip(ts, arfs)]
        # self.control.h2_flow_plot.points = [((t - t0)/60, v) for t, v in zip(ts, h2fs)]
        # self.control.samp_temp_plot.points = [((t - t0)/60, v) for t, v in zip(ts, sTs)]
        # self.control.samp_power_plot.points = [((t - t0)/60, v*self.control.ids.samp_temp.ymax*self._power_max_quickfix) for t, v in zip(ts, sPs)]
        # self.control.halc_temp_plot.points = [((t - t0)/60, v) for t, v in zip(ts, hTs)]
        # self.control.halc_power_plot.points = [((t - t0)/60, v*self.control.ids.halc_temp.ymax*self._power_max_quickfix) for t, v in zip(ts, hPs)]

    def getmaxys(self):
        maxys = []
        for graph in self.graphs:
            maxy = max(max([point[1] for point in graph.plots[0].points], default=graph.ymax),
                        max([point[1] for point in graph.plots[1].points], default=graph.ymax))
            maxys.append(maxy)
        return maxys

    def update_graphs(self, values):
        t0 = self.t0.timestamp()
        maxys = self.getmaxys()
        # maxys = [np.max(values[key]) for key in key_order]

        cnt = self.control
        plots = [cnt.ar_flow_plot, cnt.ar_flow_setpoint_plot, cnt.h2_flow_plot, cnt.h2_flow_setpoint_plot,
                 cnt.samp_temp_plot, cnt.samp_temp_setpoint_plot, cnt.halc_temp_plot, cnt.halc_temp_setpoint_plot,
                 cnt.samp_power_plot, cnt.halc_power_plot]
        gd_keys = key_order

        ts = values["time"]
        for key, plot in zip(gd_keys, plots):
            for t, val in zip((ts-t0)/60, values[key]):
                if key == 'Power_main':
                    plot.points.append([t, val*self.control.ids.samp_temp.ymax*self._power_max_quickfix])
                elif key == 'Power_seco':
                    plot.points.append([t, val*self.control.ids.halc_temp.ymax*self._power_max_quickfix])
                else:
                    plot.points.append([t, val])

        # for t, val in zip((ts-t0)/60, values["ar_flow"]):
        #     self.control.ar_flow_plot.points.append([t, val])
        # for t, val in zip((ts-t0)/60, values["h2_flow"]): 
        #     self.control.h2_flow_plot.points.append([t, val])
        # for t, val in zip((ts-t0)/60, values["Temperature_sample"]):
        #     self.control.samp_temp_plot.points.append([t, val])
        # for t, val in zip((ts-t0)/60, values["Power_main"]*self.control.ids.samp_temp.ymax*self._power_max_quickfix):
        #     self.control.samp_power_plot.points.append([t, val])
        # for t, val in zip((ts-t0)/60, values["Temperature_halcogenide"]):
        #     self.control.halc_temp_plot.points.append([t, val])
        # for t, val in zip((ts-t0)/60, values["Power_seco"]*self.control.ids.halc_temp.ymax*self._power_max_quickfix):
        #     self.control.halc_power_plot.points.append([t, val])

        maxys[0] = np.amax(values["ar_flow"], initial=maxys[0])
        maxys[1] = np.amax(values["h2_flow"], initial=maxys[1])
        maxys[2] = np.amax(values["Temperature_sample"], initial=maxys[2])
        maxys[3] = np.amax(values["Temperature_halcogenide"], initial=maxys[3])

        tmax = np.amax(ts, initial=t0)

        N = (len(self.control.ar_flow_plot.points)//2) * 2
        if N > self.plot_points_num:
            self.set_plot_points()

        widget_list = self.graphs

        t0 = self.t0.timestamp()
        for graph, maxy in zip(widget_list, maxys):
            if maxy > graph.ymax:
                graph.ymax *= 2
                graph.y_ticks_major = (graph.ymax - graph.ymin)/4
                self.set_plot_points()

            if (tmax - t0)/60 > graph.xmax:
                graph.xmax *= 2
                graph.x_ticks_major = (graph.xmax - graph.xmin)/4

    def update_setpoints(self, setpoints, update_widgets = False):
        for key in setpoints:
            self.setpoints[key] = float(setpoints[key])

        tmin, tmax = self.control.ids.ar_flow.xmin, self.control.ids.ar_flow.xmax

        # self.control.ar_flow_setpoint_plot.points = [(self.setpoints["ar_flow"])]
        # self.control.h2_flow_setpoint_plot.points = [(self.setpoints["h2_flow"])]
        # self.control.samp_temp_setpoint_plot.points = [(self.setpoints["Temperature_sample"])]
        # self.control.halc_temp_setpoint_plot.points = [(self.setpoints["Temperature_halcogenide"])]

        if update_widgets:
            self.manual_button.lockChild.ids.ar_flow.value = self.setpoints["ar_flow"]
            self.manual_button.lockChild.ids.h2_flow.value = self.setpoints["h2_flow"]
            self.manual_button.lockChild.ids.samp_temp.value = self.setpoints["Temperature_sample"]
            self.manual_button.lockChild.ids.halc_temp.value = self.setpoints["Temperature_halcogenide"]

    def get_data(self, address='127.0.0.1', port="1234", update_widgets = False, dt = 0):
        url = "http://"+address+":"+port+"/get_vals"
        current_t = self.current_t.timestamp()

        # Define data acquisition as separate function
        # We do this to start this function in a thread
        # to prevent UI blocking while waiting for get request
        def get_data_thread(self, url, current_t):
            try:
                # Get request to server 
                resp = requests.get(url, params={"t0": current_t-2}, timeout=5)
                returned = resp.text
                returned = json.loads(returned)
                resp.close()

                graph_data = returned["data"]
                setpoints = returned["setpoints"]

                # Display program remaining time:
                # print(returned["Program_time_remaining"]//60, returned["Program_time_remaining"]%60)
                # self.ids["Program_time_remaining"].text = "countdown: {:02d}:{:02d}".format(int(returned["Program_time_remaining"])//60, int(returned["Program_time_remaining"])%60)
                self.ids["Program_time_remaining"].text = "status: " + returned["Program_time_remaining"]

                # Take indices of values that have not been preveously entered
                indices = []
                time_length = len(graph_data["time"])
                for i, val in enumerate(graph_data["time"]):
                    if val in self.graph_data["time"][-time_length:]:
                        continue
                    else:
                        indices.append(i)

                # Add setpoint data to graph data
                for key in setpoints:
                    set_key = key + '_setpoint'
                    setpoint_data = np.array([setpoints[key] for _ in range(len(indices))])
                    self.graph_data[set_key] = np.append(self.graph_data[set_key], setpoint_data)

                # Add new data to graph data by numpy appending/concatenating
                for key in graph_data:
                    graph_data[key] = np.array(graph_data[key])[indices]
                    self.graph_data[key] = np.append(self.graph_data[key], graph_data[key])

                    # set text for current values
                    if key + "_text" in self.ids:
                        if len(graph_data[key]) > 0:
                            self.ids[key+"_text"].text = "{:.1f}".format(np.mean(graph_data[key]))

                # Set the current time to the most recently recieved time
                if graph_data["time"].size > 0:
                    current_t = np.amax(graph_data["time"])
                    # print(np.max(graph_data["time"]))
                else:
                    current_t = min(current_t + float(returned["maxTime"]), datetime.datetime.now().timestamp())
                self.current_t = datetime.datetime.fromtimestamp(current_t)

                self.update_setpoints(setpoints, update_widgets=update_widgets)
                for key in setpoints:
                    set_key = key + '_setpoint'
                    graph_data[set_key] = [setpoints[key] for _ in range(time_length)]
                # print(graph_data)
                self.update_graphs(graph_data)

                # repeat getting of data in 1/self.getps seconds
                Clock.schedule_once(partial(self.get_data, address, port, False), 1/self.getps)

            except Exception as e:
                print(e)

        _thread.start_new_thread(get_data_thread, (self, url, current_t))

    def auto_toggle(self, widget):
        value = widget.state
        if value == "down":
            self.start_box.remove_widget(self.manual_bar)
            self.setup_bar.remove_widget(self.step_ph)
            self.manual_button.state="normal"

            # self.start_box.add_widget(self.choice_bar)
            self.start_box.add_widget(self.content_bar)
            self.setup_bar.add_widget(self.step_box, index=-2)

        else:
            # self.start_box.remove_widget(self.choice_bar)
            self.start_box.remove_widget(self.content_bar)
            self.setup_bar.remove_widget(self.step_box)
            for widget in self.steps:
                widget.state = "normal"

            self.start_box.add_widget(self.manual_bar)
            self.setup_bar.add_widget(self.step_ph, index=-2)

    def review_toggle(self, state='down'):
        if state == "down":
            self.remove_widget(self.main_container)
            self.add_widget(self.review_container)
        else:
            self.remove_widget(self.review_container)
            self.add_widget(self.main_container)
 
    def connect(self, address, port):
        self.address = address
        self.port = port
        Clock.schedule_once(partial(self.get_data, address, port, True), 1/self.getps)
        self.review_container.get_progs()

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

    def cancel_plan(self, address=None, port=None):
        if address is None:
            address = self.address
        if port is None:
            port = self.port
        run_url = "http://"+address+":"+port+"/start_program"
        requests.get(run_url, params={"state": "stop"})

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

    def cancel_random(self, address=None, port=None, main=True):
        if address is None:
            address = self.address
        if port is None:
            port = self.port
        run_url = "http://"+address+":"+port+"/start_random_heating"
        requests.get(run_url, params={"state": "stop"})

    def start_random(self, address=None, port=None, main=True):
        if address is None:
            address = self.address
        if port is None:
            port = self.port
        run_url = "http://"+address+":"+port+"/start_random_heating"
        if main:
            name = datetime.datetime.now().isoformat() + "_random_main"
            resp = requests.get(run_url, params={"state": "start", "name": name, "heater": "main"})
            resp.close()
        else:
            name = datetime.datetime.now().isoformat() + "_random_seco"
            resp = requests.get(run_url, params={"state": "start", "name": name, "heater": "seco"})
            resp.close()

    def cancel_random_setpoint(self, address=None, port=None, main=True):
        if address is None:
            address = self.address
        if port is None:
            port = self.port
        run_url = "http://"+address+":"+port+"/start_random_setpoint"
        requests.get(run_url, params={"state": "stop"})

    def start_random_setpoint(self, address=None, port=None, main=True):
        if address is None:
            address = self.address
        if port is None:
            port = self.port
        run_url = "http://"+address+":"+port+"/start_random_setpoint"
        if main:
            name = datetime.datetime.now().isoformat() + "_random_setpoint_main"
            resp = requests.get(run_url, params={"state": "start", "name": name, "heater": "main"})
            resp.close()
        else:
            name = datetime.datetime.now().isoformat() + "_random_setpoint_seco"
            resp = requests.get(run_url, params={"state": "start", "name": name, "heater": "seco"})
            resp.close()

    def cancel_learn(self, address=None, port=None):
        if address is None:
            address = self.address
        if port is None:
            port = self.port
        run_url = "http://"+address+":"+port+"/start_learning"
        requests.get(run_url, params={"state": "stop"})

    def start_learn(self, address=None, port=None):
        if address is None:
            address = self.address
        if port is None:
            port = self.port
        run_url = "http://"+address+":"+port+"/start_learning"
        requests.get(run_url, params={"state": "start"})

    def __init__(self, **kwargs):
        super(MainBox, self).__init__(**kwargs)
        self.initialize_mainbox(0)
        # Clock.schedule_once(self.initialize_mainbox, 10)

    def initialize_mainbox(self, dt):
        self.t0 = datetime.datetime.now()
        self.t0 = self.t0.replace(microsecond=0)
        self.current_t = self.t0

        # Functions for quick debugging
        # self.browseButtonFunction = partial(self.browserReturnFunction, ("/home/alion/Desktop/cat.jpg",0), 0)
        # self.applyButtonFunction = partial(self.browserReturnFunction, ("/home/alion/Desktop/black_cat.jpg",0), 0)

        self.display_box = self.ids.display_box
        self.start_box = self.ids.start_box
        self.choice_bar = self.ids.choice_bar
        self.step_bar = self.ids.step_bar
        self.content_bar = self.ids.content_bar

        # Main Widgets
        # self.control=Control()
        self.control=self.ids.control
        self.control.initialize_plots(0)

        # self.browser=FileBrowser(main=self)
        # self.kernelEditor=KernelEditor(main=self)

        # Step configs
        self.steps = [StepProgButton(self, number = i, size_hint_y=None, size=(0, 0)) for i in range(self.max_step_num)]

        # Step_increments
        self.ids.step_num_inc.on_press=partial(self.change_step_num, 1)
        self.ids.step_num_dec.on_press=partial(self.change_step_num, -1)

        # self.display_box.add_widget(self.control)

        self.manual_bar = self.ids.manual_bar
        self.manual_button = ManualProgButton(self)
        self.manual_bar.add_widget(self.manual_button)
        self.manual_bar.add_widget(Label(size_hint_y=0.5))
        self.add_widget(self.manual_button.lockChild)

        self.setup_bar = self.ids.setup_bar
        self.step_box = self.ids.step_box
        self.step_ph = self.ids.step_ph

        # self.start_box.remove_widget(self.choice_bar)
        self.start_box.remove_widget(self.content_bar)
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

        # self.main_container = self.ids.main_container
        # self.review_container = self.ids.review_container
        self.remove_widget(self.review_container)

    # This is required for android to correctly display widgets on screen rotate
    def on_size(self, val1, val2):
        for step_button in self.steps:
            step_button.size = (0, self.step_config_size_hint_y*self.height)
        Clock.schedule_once(lambda dt: self.canvas.ask_update(), 0.2)
