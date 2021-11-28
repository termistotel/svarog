import numpy as np

import _thread
from threading import Thread, Lock

import sqlite3

import time, datetime

import socket, serial

import cherrypy
import mimetypes

import json, re
from libs.temp_control import TempController

key_order = ["ar_flow", "h2_flow", "Temperature_sample", "Temperature_halcogenide", "Power_main", "Power_seco", "time"]

def linear(fx, x1, y1, x2, y2):
    k = (y2 - y1)/(x2 - x1)
    y = y1 + k*(fx() - x1)
    return y

class FurnaceServer(object):
    values = {"ar_flow": 0, "h2_flow": 0, "Temperature_sample": 1, "Temperature_halcogenide": 1, 'Power_main': 0, 'Power_seco': 0}
    setpoints = {"ar_flow": 0, "h2_flow": 0, "Temperature_sample": 1, "Temperature_halcogenide": 1}
    minvalues = {"ar_flow": lambda: 0, "h2_flow": lambda: 0, "Temperature_sample": lambda: 75, "Temperature_halcogenide": lambda: 75}
    temp_t = {"ar_flow": time.time(), "h2_flow": time.time(), "Temperature_sample": time.time(), "Temperature_halcogenide": time.time()}
    sample_gains = [1,1,1]
    halcogenide_gains = [50,75,250]
    maxTime = 30*60
    programs = []
    data_thread = None
    program_thread = None
    random_heating_thread = None
    random_setpoint_thread = None
    relative_tolerance = 0.05 #
    port = '/dev/ttyUSB0'
    baudrate = 115200
    ser = None
    direct_power_values = {'main': 0.0, 'seco': 0.0}
    program_current_wait = 0
    program_current_wait_status = "None"

    nn_control = True
    learn_flag = False

    # This should be read in the future
    Tenv = 25
    length_contr = 1000
    length_pred = 1000

    def __init__(self, dbName = "example.db"):
        self.ar_flow, self.h2_flow, self.Temperature_sample, self.Temperature_halcogenide = 0.0, 0.0, 0.0, 0.0
        self.dbName = dbName

        # Compensation for primary furnace heating up the secondary furnace
        self.minvalues['Temperature_halcogenide'] = lambda: linear(lambda: self.values["Temperature_sample"], 35, 35, 800, 90)

        # Start connection to arduino and clear input
        self.serial_lock = Lock()
        self.ser = serial.Serial(port=self.port, baudrate=self.baudrate, timeout=1)
        time.sleep(5)
        self.clear_serial_input()

        # Start data collection from arduino
        # self.data_thread = _thread.start_new_thread(self.data_collection, ())
        self.data_thread = Thread(target=self.data_collection, name="data collection")
        self.data_thread.start()
        # Start control thread
        # self.control_thread = _thread.start_new_thread(self.furnace_control, ())
        self.control_thread = Thread(target=self.furnace_control, name="furnace control")
        self.control_thread.start()

    def clear_serial_input(self):
        self.ser.reset_input_buffer()

    def target_reached(self, key):
        # Consider target reached if it is within tolerance of setpoint or less than minimal value (~room temperature)
        if self.setpoints[key] < self.minvalues[key]():
            cryterion = (self.values[key] <= self.minvalues[key]())
        else:
            cryterion = (self.values[key] >= (1 - self.relative_tolerance)*self.setpoints[key]) and (self.values[key] <= (1 + self.relative_tolerance)*self.setpoints[key])
        return cryterion

    def run_random_heating(self, name = "RANDOM_HEATING", heater = 'main'):
        lowest_time = {"main": 5, 'seco':1}
        highest_time = {"main": 20, 'seco':5}

        start_t = datetime.datetime.now().timestamp()

        currently_heating = True
        randomize_power = True
        time_before_power_reset = 1

        while self.random_heating_run:
            if currently_heating:
                time_to_heat = np.random.uniform(low=lowest_time[heater], high=highest_time[heater])
            else:
                time_to_heat = np.random.uniform(low=lowest_time[heater]*4, high=highest_time[heater]*4)

            self.program_current_wait = time_to_heat*60
            previous_time = datetime.datetime.now().timestamp()
            power_value = np.random.uniform()

            time_power_reset = 0
            while (self.program_current_wait > 0) and self.random_heating_run:
                current_time = datetime.datetime.now().timestamp()
                delta_time = current_time - previous_time

                # Check if temperature is above maximum values
                if currently_heating:
                    ret = self.get_vals(t0=time.time() - 2)
                    ret = json.loads(ret)
                    if 'data' in ret:
                        graph_data = ret["data"]
                        if max(graph_data['Temperature_sample']) > 950:
                            self.program_current_wait = 0

                    if randomize_power:
                        if time_power_reset >= time_before_power_reset:
                            time_power_reset = 0
                            power_value += np.random.uniform(low = -0.1, high = 0.1)
                            power_value = min(max(power_value, 0), 1)
                        else:
                            time_power_reset += delta_time

                self.values['Power_'+heater] = currently_heating*power_value

                previous_time = current_time
                self.program_current_wait -= delta_time  
                self.program_current_wait_status = "{:02d}:{:02d}".format(int(self.program_current_wait)//60, int(self.program_current_wait)%60)
                time.sleep(0.25/4)

            currently_heating = not currently_heating
            if currently_heating:
                randomize_power = not randomize_power

        end_t = datetime.datetime.now().timestamp()
        # print((end_t - start_t)/60)

        database = sqlite3.connect(self.dbName)
        db_write_cursor = database.cursor()
        db_write_cursor.execute('INSERT INTO programs VALUES (?,?,?)', (start_t, end_t, name))
        database.commit()
        database.close()

        self.random_heating_thread = None
        self.random_setpoint_thread = None

    def run_random_setpoint(self, name = "RANDOM_setpoint", heater = 'main'):
        # mins
        lowest_time = {"main": 10, 'seco':2}
        highest_time = {"main": 60, 'seco':10}

        start_t = datetime.datetime.now().timestamp()

        currently_heating = True
        while self.random_setpoint_run:
            if currently_heating:
                time_to_heat = np.random.uniform(low=lowest_time[heater], high=highest_time[heater])
                setpoint = np.random.uniform()*950
            else:
                time_to_heat = np.random.uniform(low=lowest_time[heater]*10, high=highest_time[heater]*10)
                setpoint = np.random.uniform()*25

            self.program_current_wait = time_to_heat*60
            previous_time = datetime.datetime.now().timestamp()

            time_power_reset = 0
            while (self.program_current_wait > 0) and self.random_setpoint_run:
                current_time = datetime.datetime.now().timestamp()
                delta_time = current_time - previous_time

                # Check if temperature is above maximum values
                if currently_heating:
                    ret = self.get_vals(t0=time.time() - 2)
                    ret = json.loads(ret)
                    if 'data' in ret:
                        graph_data = ret["data"]
                        if max(graph_data['Temperature_sample']) > 950:
                            self.program_current_wait = 0

                if heater=='main':
                    self.setpoints['Temperature_sample'] = setpoint
                elif heater=='seco':
                    self.setpoints['Temperature_halcogenide'] = setpoint

                previous_time = current_time
                self.program_current_wait -= delta_time  
                self.program_current_wait_status = "{:02d}:{:02d}".format(int(self.program_current_wait)//60, int(self.program_current_wait)%60)
                time.sleep(0.25/4)

            currently_heating = not currently_heating

        end_t = datetime.datetime.now().timestamp()
        # print((end_t - start_t)/60)

        database = sqlite3.connect(self.dbName)
        db_write_cursor = database.cursor()
        db_write_cursor.execute('INSERT INTO programs VALUES (?,?,?)', (start_t, end_t, name))
        database.commit()
        database.close()
        self.random_setpoint_thread = None

    def run_program(self, name = "TEST"):
        def run_step():
            if not self.programs:
                return "DONE"
            plan = self.programs[0]
            print(plan)

            # Set setpoints
            self.set_setpoints(ar_flow=plan["ar_flow"], h2_flow=plan["h2_flow"],
                Temperature_sample=plan["Temperature_sample"], Temperature_halcogenide=plan["Temperature_halcogenide"])

            self.program_current_wait = float(plan["time"])*60
            # Wait until set values are reached
            print("waiting for setpoint")
            self.program_current_wait_status = "Wait"
            while self.program_run:
                break_flag = True
                for key in self.setpoints:
                    # print(key, self.target_reached(key))
                    break_flag = break_flag and (self.target_reached(key))
                if break_flag:
                    break
                time.sleep(0.25)
            print("setpoint done")

            # Wait for planned time
            previous_time = datetime.datetime.now().timestamp()
            while (self.program_current_wait > 0) and self.program_run:
                time.sleep(0.25)
                current_time = datetime.datetime.now().timestamp()
                delta_time = current_time - previous_time
                previous_time = current_time
                self.program_current_wait -= delta_time  
                self.program_current_wait_status = "{:02d}:{:02d}".format(int(self.program_current_wait)//60, int(self.program_current_wait)%60)

            self.program_current_wait = 0
            self.program_current_wait_status = "None"

            # remove current step from the list
            self.programs = self.programs[1:]
            return run_step()

        start_t = datetime.datetime.now().timestamp()
        run_step()
        end_t = datetime.datetime.now().timestamp()
        print((end_t - start_t)/60)

        database = sqlite3.connect(self.dbName)
        db_write_cursor = database.cursor()
        db_write_cursor.execute('INSERT INTO programs VALUES (?,?,?)', (start_t, end_t, name))
        database.commit()
        database.close()

        self.program_thread = None

    def get_data(self):
        t1 = time.time()

        # Request data from arduino and read it
        self.clear_serial_input()
        self.ser.write(('get,' + '\r\n').encode())
        ret = self.ser.read_until().decode()

        sensor_values = re.findall('(.+?),', ret)
        if sensor_values is None:
            return None
        try:
            ar_flow, h2_flow, Temperature_sample, Temperature_halcogenide = [float(x) for x in sensor_values]
        except Exception as e:
            print(e)
            return None

        t2 = time.time()

        # time of meassured values is an average of before request and after recieval
        t = np.mean([t1, t2])

        # Value of current dictionary
        self.values['ar_flow'] = ar_flow
        self.values['h2_flow'] = h2_flow
        self.values['time'] = t
        self.values['Temperature_sample'] = Temperature_sample
        self.values['Temperature_halcogenide'] = Temperature_halcogenide
        for key in self.values:
            if np.isnan(self.values[key]):
                print(key, "is", self.values[key])
                self.values[key] = 25
        return self.values

    def send_setpoints(self):
        setpoints_strs = ["{:.2f}".format(self.setpoints[key]) + ',' for key in ['ar_flow', 'h2_flow', 'Temperature_sample', 'Temperature_halcogenide']]
        total_command = 'set,' + ''.join(setpoints_strs) + '\r\n'
        self.ser.write((total_command).encode())
        return total_command

    def send_direct(self):
        setpoints_strs = ["{:.2f}".format(self.setpoints[key]) + ',' for key in ['ar_flow', 'h2_flow']]
        setpoints_strs +=["{:.2f}".format(self.values[key]) +',' for key in ['Power_main', 'Power_seco']]
        total_command = 'set_direct,' + ''.join(setpoints_strs) + '\r\n'
        self.ser.write((total_command).encode())
        return total_command

    # def send_gains(self):
    #     gains_strs = [str(gain) + ',' for gain in self.sample_gains + self.halcogenide_gains]
    #     total_command = 'gains,' + ''.join(gains_strs) + '\r\n'
    #     self.ser.write((total_command).encode())
    #     return total_command

    def furnace_control(self):
        # Create temperature control wrapper quickfix for secondary
        self.tc = TempController(length_pred = self.length_pred, length_contr = self.length_contr)

        t0 = time.time()
        last_runs = {'main': t0, 'seco': t0}
        last_update = {'main': t0, 'seco': t0, 'send': t0}

        while True:
            current_time = time.time()
            if self.nn_control:
                # Main furnace control
                if (current_time - last_runs['main']) >= self.tc.main_Dt:
                    print(current_time - last_runs['main'])
                    last_runs['main'] = time.time()
                    current_temp = self.values['Temperature_sample']
                    current_P = self.values['Power_main']
                    set_tmp = self.setpoints['Temperature_sample']
                    tmp_T, tmp_P = self.tc.fp_main(current_temp, current_P, set_tmp, self.Tenv)
                    self.values['Power_main'] = float(tmp_P)
                    if self.learn_flag:
                        self.tc.learn_step_main(set_tmp, self.Tenv)

                # Seco temp update
                if current_time - last_update['seco'] > self.tc.seco_dt:
                    last_update['seco'] = time.time()
                    self.tc.update_temp_seco([self.values['Temperature_halcogenide']])

                # Seco furnace control
                if (current_time - last_runs['seco']) > self.tc.seco_Dt:
                    last_runs['seco'] = time.time()
                    self.values['Power_seco'] = self.tc.fp_seco(self.setpoints['Temperature_halcogenide'], self.Tenv)[0][0]
            if (current_time - last_update['send']) >= 1:
                with self.serial_lock:
                    self.send_direct()
                    time.sleep(0.01)
            time.sleep(0.01)


    def data_collection(self, buffer_num = 4):
        database = sqlite3.connect(self.dbName)
        db_write_cursor = database.cursor()
        N = 0
        dbvals = []
        # hard_fix = self.tc.main_dt//0.1

        t0 = time.time()
        DT = 0.25
        while True:
            current_time = time.time()
            if (current_time - t0) >= DT:
                t0 = current_time
                with self.serial_lock:
                    ret = self.get_data()

                if ret:
                    dbvals.append([ret[key] for key in key_order])
                else:
                    print("DATA ERROR")


                N += 1

                try:
                    if (N%buffer_num) == 0:
                        db_write_cursor.executemany('INSERT INTO logs VALUES (?,?,?,?,?,?,?)', dbvals)
                        database.commit()
                        dbvals = []
                        # print(self.values)
                except Exception as e:
                    print(e)
            time.sleep(0.01)

    @cherrypy.expose
    def index(self):
        return 'TEST'

    @cherrypy.expose
    def get_vals(self, t0=0, tend=None):
        database = sqlite3.connect(self.dbName)
        db_read_cursor = database.cursor()
        if tend is None:
            tend = float(t0) + self.maxTime
        else:
            tend =  float(tend)
        db_read_cursor.execute('SELECT * FROM logs WHERE (time>=?) AND (time<=?) ORDER BY time asc', (float(t0), tend))

        ret = {}

        data = {}
        vals = np.array(db_read_cursor.fetchall())
        if not (vals.size==0):
            for i, key in enumerate(key_order):
                data[key] = list(vals[..., i])
        else:
            for key in key_order:
                data[key] = []

        ret["data"] = data
        ret["maxTime"] = self.maxTime
        ret["setpoints"] = self.setpoints
        # ret["Program_time_remaining"] = "{:02d}:{:02d}".format(int(self.program_current_wait)//60, int(self.program_current_wait)%60)
        ret["Program_time_remaining"] = self.program_current_wait_status

        return json.dumps(ret)

    @cherrypy.expose
    def get_program_list(self):
        database = sqlite3.connect(self.dbName)
        db_read_cursor = database.cursor()

        db_read_cursor.execute('SELECT * FROM programs ORDER BY start_t asc')
        data = list(db_read_cursor.fetchall())

        ret = {}
        ret["data"] = data

        return json.dumps(ret)

    @cherrypy.expose
    def set_setpoints(self, ar_flow=None, h2_flow=None, Temperature_sample=None, Temperature_halcogenide=None):
        if ar_flow is not None:
            self.setpoints["ar_flow"] = float(ar_flow)
        if h2_flow is not None:
            self.setpoints["h2_flow"] = float(h2_flow)
        if Temperature_sample is not None:
            self.setpoints["Temperature_sample"] = float(Temperature_sample)
        if Temperature_halcogenide is not None:
            self.setpoints["Temperature_halcogenide"] = float(Temperature_halcogenide)
        with self.serial_lock:
            self.send_setpoints()
        return "setpoints set"

    @cherrypy.expose
    def add_to_program(self, ar_flow=0, h2_flow=0, Temperature_sample=0, Temperature_halcogenide=0, time=0):
        plan = {"ar_flow": ar_flow, "h2_flow": h2_flow,
            "Temperature_sample": Temperature_sample, "Temperature_halcogenide": Temperature_halcogenide,
            "time": time}
        self.programs.append(plan)
        return "DONE"

    @cherrypy.expose
    def start_program(self, state = "start", name="TEST"):
        print(name)
        if state == "start" and self.random_heating_thread is None:
            if self.program_thread is None:
                self.program_run = True
                self.program_thread = _thread.start_new_thread(self.run_program, (name,))
                return "DONE"
            else:
                return "ALREADY RUNNING"
        elif state == "stop":
            self.program_run = False
            self.program_thread = None
            self.program_current_wait_status = "None"

    @cherrypy.expose
    def start_random_heating(self, state = "start", heater='main', name="TEST"):
        print(name)
        if state == "start" and self.program_thread is None:
            if self.random_heating_thread is None:
                if self.random_setpoint_thread is not None:
                    self.start_random_heating(state = "stop")
                self.nn_control = False
                self.random_heating_run = True
                self.random_heating_thread = _thread.start_new_thread(self.run_random_heating, (name, heater))
                return "Random heating..."
            else:
                return "Random heating ALREADY RUNNING"
        elif state == "stop":
            self.random_heating_run = False
            self.random_heating_thread = None
            self.nn_control = True
            self.program_current_wait_status = "None"

    @cherrypy.expose
    def start_random_setpoint(self, state = "start", heater='main', name="TEST"):
        print(name)
        if state == "start" and self.program_thread is None:
            if self.random_setpoint_thread is None:
                if self.random_heating_thread is not None:
                    self.start_random_heating(state = "stop")
                self.nn_control = True
                self.random_setpoint_run = True
                self.random_setpoint_thread = _thread.start_new_thread(self.run_random_setpoint, (name, heater))
                return "Random setpoint..."
            else:
                return "Random setpoint ALREADY RUNNING"
        elif state == "stop":
            self.random_setpoint_run = False
            self.random_setpoint_thread = None
            self.program_current_wait_status = "None"

    @cherrypy.expose
    def start_learning(self, state="start", name="TEST"):
        print(name)
        if state == "start":
            self.learn_flag = True
        elif state == "stop":
            self.learn_flag = False

if __name__ == '__main__':
    dbName = "furnaceActivity.db"

    conf = {
        '/': {
            'tools.sessions.on': True
        }
    }
    cherrypy.config.update({
                'server.socket_host': '0.0.0.0',
                'server.socket_port': 1234,
                'log.screen': True,
                })

    # cherrypy.log.access_log.propagate = False
    cherrypy.quickstart(FurnaceServer(dbName), '/', conf)
