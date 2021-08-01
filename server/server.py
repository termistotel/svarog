import numpy as np

import _thread
from threading import Thread

import sqlite3

import time, datetime

import socket, serial

import cherrypy
import mimetypes

import json, re
from libs.temp_control import TempController

key_order = ["ar_flow", "h2_flow", "Temperature_sample", "Temperature_halcogenide", "time"]

def linear(fx, x1, y1, x2, y2):
    k = (y2 - y1)/(x2 - x1)
    y = y1 + k*(fx() - x1)
    return y

class FurnaceServer(object):
    values = {"ar_flow": 0, "h2_flow": 0, "Temperature_sample": 1, "Temperature_halcogenide": 1}
    setpoints = {"ar_flow": 0, "h2_flow": 0, "Temperature_sample": 1, "Temperature_halcogenide": 1}
    minvalues = {"ar_flow": lambda: 0, "h2_flow": lambda: 0, "Temperature_sample": lambda: 75, "Temperature_halcogenide": lambda: 75}
    temp_t = {"ar_flow": time.time(), "h2_flow": time.time(), "Temperature_sample": time.time(), "Temperature_halcogenide": time.time()}
    sample_gains = [1,1,1]
    halcogenide_gains = [50,75,250]
    maxTime = 30*60
    programs = []
    data_thread = None
    program_thread = None
    relative_tolerance = 0.1
    port = '/dev/ttyUSB0'
    baudrate = 115200
    ser = None
    direct_power_values = {'main': 0.0, 'seco': 0.0}

    # This should be read in the future
    Tenv = 25

    def __init__(self, dbName = "example.db"):
        self.dbName = dbName

        # Compensation for primary furnace heating up the secondary furnace
        self.minvalues['Temperature_halcogenide'] = lambda: linear(lambda: self.values["Temperature_sample"], 25, 25, 800, 90)

        # Start connection to arduino and clear input
        self.ser = serial.Serial(port=self.port, baudrate=self.baudrate, timeout=1)
        time.sleep(5)
        self.clear_serial_input()

        # Create temperature control wrapper
        self.tc = TempController()

        # Start data collection from arduino
        self.data_thread = _thread.start_new_thread(self.data_collection, ())

    def clear_serial_input(self):
        self.ser.reset_input_buffer()

    def target_reached(self, key):
        # Consider target reached if it is within tolerance of setpoint or less than minimal value (~room temperature)
        if self.setpoints[key] < self.minvalues[key]():
            cryterion = (self.values[key] <= self.minvalues[key]())
        else:
            cryterion = (self.values[key] >= (1 - self.relative_tolerance)*self.setpoints[key]) and (self.values[key] <= (1 + self.relative_tolerance)*self.setpoints[key])
        return cryterion

    def run_program(self, name = "TEST"):
        def run_step():
            if not self.programs:
                return "DONE"
            plan = self.programs[0]
            print(plan)

            # Set setpoints
            self.set_setpoints(ar_flow=plan["ar_flow"], h2_flow=plan["h2_flow"],
                Temperature_sample=plan["Temperature_sample"], Temperature_halcogenide=plan["Temperature_halcogenide"])

            # Wait until set values are reached
            print("waiting for setpoint")
            while True:
                break_flag = True
                for key in self.setpoints:
                    # print(key, self.target_reached(key))
                    break_flag = break_flag and (self.target_reached(key))
                if break_flag:
                    break
                time.sleep(0.5)
            print("setpoint done")

            # Wait for planned time
            print(float(plan["time"]))
            time.sleep(float(plan["time"])*60)

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
        # print("RET", ret)
        sensor_values = re.findall('(.+?),', ret)
        ar_flow, h2_flow, Temperature_sample, Temperature_halcogenide = [float(x) for x in sensor_values]

        t2 = time.time()

        # time of meassured values is an average of before request and after recieval
        t = np.mean([t1, t2])

        # Value of current dictionary
        ret = {
            "ar_flow": ar_flow,
            "h2_flow": h2_flow,
            "time": t,
            "Temperature_sample": Temperature_sample,
            "Temperature_halcogenide": Temperature_halcogenide}
        self.values = ret
        for key in ret:
            if np.isnan(ret[key]):
                print(key, "is", ret[key])
                ret[key] = 25
        return ret

    def send_setpoints(self):
        setpoints_strs = ["{:.2f}".format(self.setpoints[key]) + ',' for key in ['ar_flow', 'h2_flow', 'Temperature_sample', 'Temperature_halcogenide']]
        total_command = 'set,' + ''.join(setpoints_strs) + '\r\n'
        self.ser.write((total_command).encode())
        return total_command

    def send_direct(self):
        setpoints_strs = ["{:.2f}".format(self.setpoints[key]) + ',' for key in ['ar_flow', 'h2_flow']]
        setpoints_strs +=["{:.2f}".format(self.direct_power_values[key]) +',' for key in ['main', 'seco']]
        total_command = 'set_direct,' + ''.join(setpoints_strs) + '\r\n'
        self.ser.write((total_command).encode())
        return total_command

    def send_gains(self):
        gains_strs = [str(gain) + ',' for gain in self.sample_gains + self.halcogenide_gains]
        total_command = 'gains,' + ''.join(gains_strs) + '\r\n'
        self.ser.write((total_command).encode())
        return total_command

    def data_collection(self, buffer_num = 4):
        self.t0 = time.time()
        last_runs = {'main': self.t0, 'seco': self.t0}
        last_update = {'main': self.t0, 'seco': self.t0}
        database = sqlite3.connect(self.dbName)
        db_write_cursor = database.cursor()
        N = 0
        dbvals = []
        easy_fix = 4
        # hard_fix = self.tc.main_dt//0.1
        while True:
            ret = self.get_data()
            dbvals.append([ret[key] for key in key_order])

            # Main temp update
            if ret['time'] - last_update['main'] > self.tc.main_dt:
                #  Take mean of main temperatures #dbvals[i][2] for i = max-easy_fix, max (about last second)#
                self.tc.update_temp_main([np.mean([val[2] for val in dbvals[-easy_fix:]])])
                last_update['main'] = time.time()

            # Main furnace control
            if (ret['time'] - last_runs['main']) > self.tc.main_Dt:
                # Agregated last n seconds
                self.direct_power_values['main'] = self.tc.fp_main(self.setpoints['Temperature_sample'], self.Tenv)[0][0]
                last_runs['main'] = time.time()

            # Seco temp update
            if ret['time'] - last_update['seco'] > self.tc.seco_dt:
                # print("SECO_update")
                self.tc.update_temp_seco([np.mean([val[3] for val in dbvals[-easy_fix:]])])
                last_update['seco'] = time.time()

            # Seco furnace control
            if (ret['time'] - last_runs['seco']) > self.tc.seco_Dt:
                # print("SECO_control")
                # Agregated last n seconds
                self.direct_power_values['seco'] = self.tc.fp_seco(self.setpoints['Temperature_halcogenide'], self.Tenv)[0][0]
                last_runs['seco'] = time.time()

            print(self.direct_power_values)
            self.send_direct()
            time.sleep(0.25)

            N += 1

            if (N%buffer_num) == 0:
                db_write_cursor.executemany('INSERT INTO logs VALUES (?,?,?,?,?)', dbvals)
                database.commit()
                dbvals = []

    @cherrypy.expose
    def index(self):
        return 'TEST'

    @cherrypy.expose
    def get_vals(self, t0=time.time()):
        database = sqlite3.connect(self.dbName)
        db_read_cursor = database.cursor()

        db_read_cursor.execute('SELECT * FROM logs WHERE (time>=?) AND (time<=?) ORDER BY time asc', (float(t0), float(t0) + self.maxTime))

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
        self.send_setpoints()
        return "setpoints set"

    @cherrypy.expose
    def set_gains(self, T_samp_p=None, T_samp_i=None, T_samp_d=None, T_halc_p=None, T_halc_i=None, T_halc_d=None):
        if T_samp_p is not None:
            self.sample_gains[0] = float(T_samp_p)
        if T_samp_i is not None:
            self.sample_gains[1] = float(T_samp_i)
        if T_samp_d is not None:
            self.sample_gains[2] = float(T_samp_d)
        if T_halc_p is not None:
            self.halcogenide_gains[0] = float(T_halc_p)
        if T_halc_i is not None:
            self.halcogenide_gains[1] = float(T_halc_i)
        if T_halc_d is not None:
            self.halcogenide_gains[2] = float(T_halc_d)
        self.send_gains()
        return "gains set"

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
        if self.program_thread is None:
            self.program_thread = _thread.start_new_thread(self.run_program, (name,))
            return "DONE"
        else:
            return "ALREADY RUNNING"

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
                'log.screen': False,
                })

    cherrypy.log.access_log.propagate = False
    cherrypy.quickstart(FurnaceServer(dbName), '/', conf)
