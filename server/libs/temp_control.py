from libs.agent_np import Agent_np
import os, re, json
import numpy as np

sigmoid = lambda x: 1/(1 + np.exp(-x))
class TempController(object):
    """docstring for TempController"""
    def __init__(self, main_dir = 'main_agent_model/weights', seco_dir = 'seco_agent_model/weights'):
        super(TempController, self).__init__()
        self.main_dir = main_dir
        self.seco_dir = seco_dir
        self.main_Ts_list = [25,25,25]
        self.seco_Ts_list = [25,25,25]
        self.main_Tnorm = 1
        self.seco_Tnorm = 1

        self.load_main()
        self.load_seco()

    def load_main(self):
        model_dir = self.main_dir
        self.main_last_temp = 5
        self.main_dt = 2

        with open(os.path.join(model_dir, 'metadata.json'), 'r') as fp:
            self.main_agent_meta = json.load(fp)
        with open(os.path.join(model_dir, 'extracted_params'), 'r') as fp:
            self.main_physics_meta = json.load(fp)

        self.main_Dt = self.main_agent_meta['Dt']
        self.main_Tnorm = self.main_physics_meta['Tnorm']

        self.main_ass = [np.zeros([1,self.main_agent_meta['asize']], dtype=np.float32) for i in range(self.main_agent_meta['hln']+1)]
        self.main_css = [np.zeros([1,self.main_agent_meta['asize']], dtype=np.float32) for i in range(self.main_agent_meta['hln']+1)]

        TP, TI, TD, test_T_env = [[0.0]], [[0.0]], [[0.0]], [[0.0]]
        environment = np.concatenate([TP, TI, TD, test_T_env], axis=-1)

        self.main_agent = Agent_np([1], [self.main_agent_meta['asize']], self.main_agent_meta['hln'], self.main_agent_meta['f'])
        self.main_agent([environment, *self.main_ass, *self.main_css])
        self.main_agent.get_vars()

        file_list = os.listdir(model_dir)
        for i, weight in enumerate(self.main_agent.weights):
            candidates = list(filter(lambda x: re.match(str(i)+'_', x), file_list))
            loaded_weight = np.load(os.path.join(model_dir, candidates[0]))
            weight[...] = loaded_weight[...]

    def load_seco(self):
        model_dir = self.seco_dir
        self.seco_last_temp = 5
        self.seco_dt = 1

        with open(os.path.join(model_dir, 'metadata.json'), 'r') as fp:
            self.seco_agent_meta = json.load(fp)
        with open(os.path.join(model_dir, 'extracted_params'), 'r') as fp:
            self.seco_physics_meta = json.load(fp)

        self.seco_Dt = self.seco_agent_meta['Dt']
        self.seco_Tnorm = self.seco_physics_meta['Tnorm']

        self.seco_ass = [np.zeros([1,self.seco_agent_meta['asize']], dtype=np.float32) for i in range(self.seco_agent_meta['hln']+1)]
        self.seco_css = [np.zeros([1,self.seco_agent_meta['asize']], dtype=np.float32) for i in range(self.seco_agent_meta['hln']+1)]

        TP, TI, TD, test_T_env = [[0.0]], [[0.0]], [[0.0]], [[0.0]]
        environment = np.concatenate([TP, TI, TD], axis=-1)

        self.seco_agent = Agent_np([1], [self.seco_agent_meta['asize']], self.seco_agent_meta['hln'], self.seco_agent_meta['f'])
        self.seco_agent([environment, *self.seco_ass, *self.seco_css])
        self.seco_agent.get_vars()

        file_list = os.listdir(model_dir)
        for i, weight in enumerate(self.seco_agent.weights):
            candidates = list(filter(lambda x: re.match(str(i)+'_', x), file_list))
            loaded_weight = np.load(os.path.join(model_dir, candidates[0]))
            weight[...] = loaded_weight[...]

    def update_temp_seco(self, Ts):
        self.seco_Ts_list += Ts
        self.seco_Ts_list = self.seco_Ts_list[-self.seco_last_temp:]

    def fp_seco(self, setpoint_T, Tenv):
        TP, TI, TD = self.seco_Ts_list[-1] - setpoint_T, np.mean(self.seco_Ts_list) - setpoint_T, self.seco_Ts_list[-1] - self.seco_Ts_list[-2]
        environment = np.concatenate([[[TP]], [[TI]], [[TD]]], axis=-1)/self.seco_Tnorm
        hln = self.seco_agent_meta['hln']

        output = self.seco_agent([environment, *self.seco_ass, *self.seco_css])

        newPset = output[0]
        self.seco_ass = output[1:2+hln]
        self.seco_css = output[2+hln:]

        return newPset

    def update_temp_main(self, Ts):
        self.main_Ts_list += Ts
        self.main_Ts_list = self.main_Ts_list[-self.main_last_temp:]

    def fp_main(self, setpoint_T, Tenv):
        TP, TI, TD = self.main_Ts_list[-1] - setpoint_T, np.mean(self.main_Ts_list) - setpoint_T, self.main_Ts_list[-1] - self.main_Ts_list[-2]
        environment = np.concatenate([[[TP]], [[TI]], [[TD]], [[Tenv]]], axis=-1)/self.main_Tnorm
        hln = self.main_agent_meta['hln']

        output = self.main_agent([environment, *self.main_ass, *self.main_css])

        newPset = output[0]
        self.main_ass = output[1:2+hln]
        self.main_css = output[2+hln:]

        return newPset





