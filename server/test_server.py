import numpy as np

import _thread
from threading import Thread

import sqlite3

import time

import socket

import cherrypy
import mimetypes

import json

key_order = ["ar_flow", "h2_flow", "Temperature_sample", "Temperature_halcogenide", "time"]

class FurnaceServer(object):
    values = {"ar_flow": 0, "h2_flow": 0, "Temperature_sample": 0, "Temperature_halcogenide": 0}
    setpoints = {"ar_flow": 0, "h2_flow": 0, "Temperature_sample": 0, "Temperature_halcogenide": 0}
    temp_t = {"ar_flow": time.time(), "h2_flow": time.time(), "Temperature_sample": time.time(), "Temperature_halcogenide": time.time()}
    maxTime = 5*60

    def __init__(self, dbName = "example.db"):
        self.dbName = dbName

        # self.database = sqlite3.connect(dbName)
        # self.db_write_cursor = self.database.cursor()
        # self.db_read_cursor = self.database.cursor()

        self.data_thread = _thread.start_new_thread(self.data_collection, ())

    def get_data(self):
        t = time.time()
        dt = {"Temperature_sample": t - self.temp_t["Temperature_sample"],
            "Temperature_halcogenide": t - self.temp_t["Temperature_halcogenide"]}
        p11, p12 = np.exp(-dt["Temperature_sample"]/1000), np.exp(-200/dt["Temperature_sample"])
        p21, p22 = np.exp(-dt["Temperature_halcogenide"]/200), np.exp(-200/dt["Temperature_halcogenide"])
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

        db_read_cursor.execute('SELECT * FROM logs WHERE time BETWEEN ? AND ?', (float(t0), float(t0) + self.maxTime))

        ret = {}

        data = []
        for val in db_read_cursor:
            dic = {}
            for i, key in enumerate(key_order):
                dic[key] = val[i]
            data.append(dic)

        ret["data"] = data
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


    @cherrypy.expose
    def camera_stream(self):
        cherrypy.response.headers["Content-Type"] = 'multipart/x-mixed-replace; boundary=frame'
        def stream():
            while True:
                if self.streamFlag:
                    yield self.data
                sleep(0.2)

        return stream()

if __name__ == '__main__':

    dbName = "furnaceActivity.db"

    conf = {
        '/': {
            'tools.sessions.on': True
        }
    }
    cherrypy.config.update({
                'server.socket_host': '127.0.0.1',
                'server.socket_port': 1234,
                })

    cherrypy.quickstart(FurnaceServer(dbName), '/', conf)
