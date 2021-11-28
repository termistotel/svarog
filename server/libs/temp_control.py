from libs.agent_np import Agent_np
from libs.brain import Predict_Control_System
import os, re, json
import numpy as np

sigmoid = lambda x: 1/(1 + np.exp(-x))
class TempController(object):
    """docstring for TempController"""
    def __init__(self, main_dir = 'main_agent_model/weights', seco_dir = 'seco_agent_model/weights', length_pred = 500, length_contr = 500):
        super(TempController, self).__init__()
        self.main_dir = main_dir
        self.seco_dir = seco_dir
        self.main_Tnorm = 1
        self.seco_Tnorm = 1

        self.pcs = Predict_Control_System(main_dir+"_predict", main_dir+"_control", length_pred, length_contr)

        # Initial values
        self.main_Ts_list = [25.0 for _ in range(self.pcs.length_pred)]
        self.main_Ps_list = [0.0 for _ in range(self.pcs.length_pred)]
        self.main_states_pred_list = [self.pcs._states_pred_np for _ in range(self.pcs.length_pred)]
        self.main_states_cont_list = [self.pcs._states_cont_np for _ in range(self.pcs.length_pred)]

        self.seco_Ts_list = [25.0,25.0,25.0]

        self.load_main()
        self.load_seco()

    def load_main(self):
        self.main_last_temp = self.pcs.length_pred
        # self.main_dt = self.pcs.meta_predict['ddt']
        # self.main_Dt = self.pcs.meta_predict['ddt']
        self.main_dt = 1
        self.main_Dt = 1
        self.main_Tnorm = self.pcs.norms_predict['Tnorm']

    def load_seco(self):
        model_dir = self.seco_dir
        with open(os.path.join(model_dir, 'metadata.json'), 'r') as fp:
            self.seco_agent_meta = json.load(fp)
        with open(os.path.join(model_dir, 'extracted_params'), 'r') as fp:
            self.seco_physics_meta = json.load(fp)

        self.seco_last_temp = 5
        self.seco_dt = self.seco_agent_meta['Dt']*self.seco_physics_meta['tnorm']
        self.seco_Dt = self.seco_agent_meta['Dt']*self.seco_physics_meta['tnorm']
        self.seco_Tnorm = self.seco_physics_meta['Tnorm']

        print("seco dt:", self.seco_dt, self.seco_Dt)

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

    def update_vals_main(self, Ts, Ps):
        self.main_Ts_list += Ts
        self.main_Ps_list += Ps
        self.main_Ts_list = self.main_Ts_list[-self.main_last_temp:]
        self.main_Ps_list = self.main_Ps_list[-self.main_last_temp:]

    def fp_main(self, current_temp, current_P, set_tmp, T_env):
        T_pred, newPset, state_pred, state_cont = self.pcs.feed_forward(current_temp=current_temp, current_P=current_P, set_temp = set_tmp, T_env = T_env)

        self.main_Ts_list.append(current_temp)
        self.main_Ps_list.append(current_P)
        self.main_states_pred_list.append(state_pred)
        self.main_states_cont_list.append(state_cont)

        self.main_Ts_list = self.main_Ts_list[-self.main_last_temp:]
        self.main_Ps_list = self.main_Ps_list[-self.main_last_temp:]
        self.main_states_pred_list = self.main_states_pred_list[-self.main_last_temp:]
        self.main_states_cont_list = self.main_states_cont_list[-self.main_last_temp:]

        return T_pred, newPset

    def learn_step_main(self, setpoint_T, Tenv):
        # set_the_T = np.ones((1, self.pcs.length_cont))*setpoint_T/self.pcs.norms_control['Tnorm']
        set_the_T = setpoint_T/self.pcs.norms_control['Tnorm']
        set_Tenv = Tenv/self.pcs.norms_predict['Tnorm']
        self.pcs.learning_step(set_the_T, set_Tenv, (self.main_Ts_list, self.main_Ps_list), (self.main_states_pred_list, self.main_states_cont_list))
