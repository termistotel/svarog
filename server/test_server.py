import numpy as np

import _thread
from threading import Thread

import sqlite3

import time, datetime

import socket

import cherrypy
import mimetypes

import json

key_order = ["ar_flow", "h2_flow", "Temperature_sample", "Temperature_halcogenide", "time"]

class FurnaceServer(object):
    values = {"ar_flow": 0, "h2_flow": 0, "Temperature_sample": 1, "Temperature_halcogenide": 1}
    setpoints = {"ar_flow": 0, "h2_flow": 0, "Temperature_sample": 1, "Temperature_halcogenide": 1}
    temp_t = {"ar_flow": time.time(), "h2_flow": time.time(), "Temperature_sample": time.time(), "Temperature_halcogenide": time.time()}
    maxTime = 30*60
    programs = []
    data_thread = None
    program_thread = None
    relative_tolerance = 0.01

    def __init__(self, dbName = "example.db"):
        self.dbName = dbName

        # self.database = sqlite3.connect(dbName)
        # self.db_write_cursor = self.database.cursor()
        # self.db_read_cursor = self.database.cursor()

        self.data_thread = _thread.start_new_thread(self.data_collection, ())

    def target_reached(self, key):
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
        t = time.time()
        dt = {"Temperature_sample": t - self.temp_t["Temperature_sample"],
            "Temperature_halcogenide": t - self.temp_t["Temperature_halcogenide"]}
        p11, p12 = np.exp(-dt["Temperature_sample"]/100), np.exp(-20/dt["Temperature_sample"])
        p21, p22 = np.exp(-dt["Temperature_halcogenide"]/20), np.exp(-20/dt["Temperature_halcogenide"])
        ret = {
            "ar_flow": self.setpoints["ar_flow"],
            "h2_flow": self.setpoints["h2_flow"],
            "time": t,
            "Temperature_sample": (p11*self.values["Temperature_sample"] + p12*self.setpoints["Temperature_sample"])/(p11 + p12),
            "Temperature_halcogenide": (p21*self.values["Temperature_halcogenide"] + p22*self.setpoints["Temperature_halcogenide"])/(p21 + p22)}
        self.values = ret
        return ret

    def data_collection(self, buffer_num = 10):
        self.t0 = time.time()
        database = sqlite3.connect(self.dbName)
        db_write_cursor = database.cursor()
        N = 0
        dbvals = []
        while True:
            ret = self.get_data()
            dbvals.append([ret[key] for key in key_order])
            time.sleep(0.1)

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
            self.temp_t["ar_flow"] = time.time()
        if h2_flow is not None:
            self.setpoints["h2_flow"] = float(h2_flow)
            self.temp_t["h2_flow"] = time.time()
        if Temperature_sample is not None:
            self.setpoints["Temperature_sample"] = float(Temperature_sample)
            self.temp_t["Temperature_sample"] = time.time()
        if Temperature_halcogenide is not None:
            self.setpoints["Temperature_halcogenide"] = float(Temperature_halcogenide)
            self.temp_t["Temperature_halcogenide"] = time.time()
        return "set"

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
