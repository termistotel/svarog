from kivy.uix.gridlayout import GridLayout
from kivy.uix.boxlayout import BoxLayout

from kivy.properties import NumericProperty, StringProperty

from kivy_garden.graph import Graph, LinePlot, HBar

from kivy.clock import Clock

flow_color = [1, 0, 0, 1]
temp_color = [0, 1, 0, 1]
temp_predict_color = [0, 1, 0, 0.5]
power_color = [1, 1, 0, 0.4]
setpoint_color = [0.3, 0.3, 1, 0.8]

class Values_control_layout(GridLayout):
    """docstring for Values_control_layout"""
    def __init__(self, *args, **kwargs):
        super(Values_control_layout, self).__init__(*args, **kwargs)

    def initialize_plots(self, dt):
        # point_size = 2
        line_width = 1.5

        # self.ar_flow_plot = ScatterPlot(color=flow_color, point_size=point_size)
        self.ar_flow_plot = LinePlot(color=flow_color, line_width=line_width)
        self.ar_flow_setpoint_plot = LinePlot(color=setpoint_color, line_width=line_width/2)
        self.ids.ar_flow.add_plot(self.ar_flow_plot)
        self.ids.ar_flow.add_plot(self.ar_flow_setpoint_plot)

        # self.h2_flow_plot = ScatterPlot(color=flow_color, point_size=point_size)
        self.h2_flow_plot = LinePlot(color=flow_color, line_width=line_width)
        self.h2_flow_setpoint_plot = LinePlot(color=setpoint_color, line_width=line_width/2)
        self.ids.h2_flow.add_plot(self.h2_flow_plot)
        self.ids.h2_flow.add_plot(self.h2_flow_setpoint_plot)

        # self.samp_temp_plot = ScatterPlot(color=temp_color, point_size=point_size)
        self.samp_temp_plot = LinePlot(color=temp_color, line_width=line_width)
        self.samp_temp_setpoint_plot = LinePlot(color=setpoint_color, line_width=line_width/2)
        self.samp_power_plot = LinePlot(color=power_color, line_width=line_width)
        self.ids.samp_temp.add_plot(self.samp_temp_plot)
        self.ids.samp_temp.add_plot(self.samp_temp_setpoint_plot)
        self.ids.samp_temp.add_plot(self.samp_power_plot)

        # self.halc_temp_plot = ScatterPlot(color=temp_color, point_size=point_size)
        self.halc_temp_plot = LinePlot(color=temp_color, line_width=line_width)
        self.halc_temp_setpoint_plot = LinePlot(color=setpoint_color, line_width=line_width/2)
        self.halc_power_plot = LinePlot(color=power_color, line_width=line_width)
        self.ids.halc_temp.add_plot(self.halc_temp_plot)
        self.ids.halc_temp.add_plot(self.halc_temp_setpoint_plot)
        self.ids.halc_temp.add_plot(self.halc_power_plot)

    def add_plot(self, color, line_width, plotType=LinePlot):
        plot = plotType(color=color, line_width = line_width)
        return plot

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
        elif self.typ == "linear_round":
            value = value + sign*self.perc_inc
            # value = (tmp_value//self.perc_inc) * self.perc_inc

        value = min(self.max_val, max(self.min_val, value))
        self.value = value

    def __init__(self, **kwargs):
        super(ControlBox, self).__init__(**kwargs)


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
        super(RTdisp, self).__init__(*args, **kwargs)
