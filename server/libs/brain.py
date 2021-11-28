import os, json, re

import numpy as np
import tensorflow as tf
tf.compat.v1.disable_eager_execution()

from libs.agent import Agent

class Predict_Control_System():
    def __init__(self, model_dir_predict, model_dir_control, length_pred, length_cont):
        self.sess = None
        self.model_dir_predict = model_dir_predict
        self.model_dir_control = model_dir_control
        self.length_pred = length_pred
        self.length_cont = length_cont

        # Load meta, norms
        with open(os.path.join(model_dir_predict, 'predict_metadata.json'), 'r') as fp:
            self.meta_predict = json.load(fp)
        with open(os.path.join(model_dir_predict, 'norms.json'), 'r') as fp:
            self.norms_predict = json.load(fp)
        with open(os.path.join(model_dir_control, 'metadata.json'), 'r') as fp:
            self.meta_control = json.load(fp)
        with open(os.path.join(model_dir_control, 'norms.json'), 'r') as fp:
            self.norms_control = json.load(fp)

        self.agent_predict = Agent(1, [self.meta_predict['asize']], self.meta_predict['hln'], self.meta_predict['f'], out_activation = tf.nn.tanh)
        self.agent_control = Agent(1, [self.meta_control['asize']], self.meta_control['hln'], self.meta_control['f'], out_activation = tf.nn.sigmoid)

        self.build_graph_forward()
        self.build_graph_learn()
        self.start_session()
        self.load_model()

    def __exit__(self, exc_type, exc_value, traceback):
        self.sess.close()
        self.sess = None

    def start_session(self):
        self.sess = tf.compat.v1.Session()
        self.sess.run(tf.compat.v1.global_variables_initializer())

    def update_lr(self, value=1e-5):
        self.sess.run(self.alpha.assign(value))

    def load_model(self):
        # load_dir = 'main_agent_model/weights_predict'
        load_dir = self.model_dir_predict
        files = os.listdir(load_dir)
        for i, val in enumerate(self.agent_predict_vars):
            for file in files:
                target_name = val.name.replace("/", "\%5c").replace(":", "\%3a")
                if re.match("[0-9]+_"+target_name+".npy", file):
                    np_val = np.load(os.path.join(load_dir, file))
                    self.sess.run(val.assign(np_val))
                    print("FOUND VAL", file, val.name)
                    continue

        # load_dir = 'main_agent_model/weights_control'
        load_dir = self.model_dir_control
        files = os.listdir(load_dir)
        for i, val in enumerate(self.agent_control_vars):
            for file in files:
                target_name = val.name.replace("/", "\%5c").replace(":", "\%3a")
                if re.match("[0-9]+_"+target_name+".npy", file):
                    np_val = np.load(os.path.join(load_dir, file))
                    self.sess.run(val.assign(np_val))
                    print("FOUND VAL", file, val.name)
                    continue

    # def feed_forward(self, environment_pred_np, environment_cont_np):
        # environment_predict = tf.concat([Tpreds_simu[-1], T_env, Psets_simu[-1]], axis=-1)
        # environment_control = tf.concat([Tpreds_simu[-1], newTpred, setpoint_T], axis=-1)
    def feed_forward(self, current_temp=25.0, current_P=0.0, set_temp = 25.0, T_env = 25):
        current_temp = current_temp/self.norms_predict['Tnorm']
        T_env = T_env/self.norms_predict['Tnorm']
        current_P = current_P
        set_temp = set_temp/self.norms_control['Tnorm']

        feeds = {self._environment_pred_tf: np.concatenate([[[current_temp]], [[T_env]], [[current_P]]], axis=-1)}
        for state, val in zip(self._states_pred_tf, self._states_pred_np):
            feeds[state[0]] = val[0]
            feeds[state[1]] = val[1]
        output_pred = self.sess.run(self.fp_pred, feed_dict=feeds)
        newTpred = current_temp + output_pred[0][0,0]*self.norms_predict['dT_norm']

        feeds = {self._environment_cont_tf: np.concatenate([[[current_temp]], [[newTpred]], [[set_temp]]], axis=-1)}
        for state, val in zip(self._states_cont_tf, self._states_cont_np):
            feeds[state[0]] = val[0]
            feeds[state[1]] = val[1]
        output_cont = self.sess.run(self.fp_cont, feed_dict=feeds)
 
        self._states_pred_np = output_pred[1]
        self._states_cont_np = output_cont[1]
        return newTpred*self.norms_predict['Tnorm'], output_cont[0][0,0], output_pred[1], output_cont[1]

    def build_graph_forward(self):
        self._environment_pred_tf = tf.compat.v1.placeholder(tf.float32, shape=[1, 3])
        self._states_pred_tf = [(tf.compat.v1.placeholder(tf.float32, shape=[1, self.meta_predict['asize']]),
                                tf.compat.v1.placeholder(tf.float32, shape=[1, self.meta_predict['asize']])) for i in range(self.meta_predict['hln'])]
        self._states_pred_np = [(np.random.uniform(size=(1, self.meta_predict['asize'])),
                                np.random.uniform(size=(1, self.meta_predict['asize']))) for i in range(self.meta_predict['hln'])]
        self.fp_pred = self.agent_predict(self._environment_pred_tf, self._states_pred_tf)

        self._environment_cont_tf = tf.compat.v1.placeholder(tf.float32, shape=[1, 3])
        self._states_cont_tf = [(tf.compat.v1.placeholder(tf.float32, shape=[1, self.meta_control['asize']]),
                                tf.compat.v1.placeholder(tf.float32, shape=[1, self.meta_control['asize']])) for i in range(self.meta_control['hln'])]
        self._states_cont_np = [(np.zeros((1, self.meta_control['asize'])),
                                np.zeros((1, self.meta_control['asize']))) for i in range(self.meta_control['hln'])]
        self.fp_cont = self.agent_control(self._environment_cont_tf, self._states_cont_tf)

    def learning_step(self, set_the_T, Tenv, Trues, states):
        part_true_T, part_true_P = Trues
        T_current, P_current = part_true_T[-1], part_true_P[-1]
        feeds = {
            self.T_env: [[Tenv]],
            self.setpoint_T: [[set_the_T]],
            self.true_T: [part_true_T],
            self.true_P: [part_true_P],
            self.Tpreds_simu[0]: [[T_current]],
            self.Psets_simu[0]: [[P_current]],
            self.Tpreds_real[0]: [[part_true_T[0]]],
        }

        for state, val in zip(self.transfers_pred_real[0], states[0][0]):
            feeds[state[0]] = val[0]
            feeds[state[1]] = val[1]
        for state, val in zip(self.transfers_pred_simu[0], states[0][-1]):
            feeds[state[0]] = val[0]
            feeds[state[1]] = val[1]
        for state, val in zip(self.transfers_cont_simu[0], states[1][-1]):
            feeds[state[0]] = val[0]
            feeds[state[1]] = val[1]

    #     last_transfers_pred, last_transfers_cont, last_Temp, last_P, n_control_cost, _ = sess.run([transfers_pred[-1], transfers_cont[-1], Tpreds[-1], Psets[-1], control_loss, control_steps], feed_dict = feeds)
        _, _ = self.sess.run([self.prediction_steps, self.control_steps], feed_dict = feeds)

    def build_graph_learn(self):
        self.T_env = tf.compat.v1.placeholder(tf.float32, shape=[1,1])

        length_pred = self.length_pred
        length_cont = self.length_cont
        dT_norm = self.norms_predict['dT_norm']
        asize_pred = self.meta_predict['asize']
        asize_cont = self.meta_control['asize']
        hln_pred = self.meta_predict['hln']
        hln_cont = self.meta_control['hln']

        self.true_T = tf.compat.v1.placeholder(tf.float32, shape=[1, length_pred])
        self.true_P = tf.compat.v1.placeholder(tf.float32, shape=[1, length_pred])
        self.Tpreds_real = [tf.compat.v1.placeholder(tf.float32, shape=[1,1])]

        # Graph for temperature prediction
        self.transfers_pred_real = [[(tf.compat.v1.placeholder(tf.float32, shape=[1, asize_pred]), tf.compat.v1.placeholder(tf.float32, shape=[1, asize_pred])) for i in range(hln_pred)]]
        for i in range(self.length_pred-1):
            environment_predict = tf.concat([self.Tpreds_real[-1], self.T_env, self.true_P[:, i:i+1]], axis=-1)
        #     environment_predict = tf.concat([true_T[:, i:i+1], T_env, true_P[:, i:i+1]], axis=-1)
            output_predict, states_predict = self.agent_predict(environment_predict, self.transfers_pred_real[-1])
            dT = output_predict
            newTpred = self.Tpreds_real[-1] + dT*dT_norm

            self.Tpreds_real.append(newTpred)
            self.transfers_pred_real.append(states_predict)

        self.setpoint_T = tf.compat.v1.placeholder(tf.float32, shape=[1,1])
        self.Tpreds_simu = [tf.compat.v1.placeholder(tf.float32, shape=[1,1])]
        self.Psets_simu = [tf.compat.v1.placeholder(tf.float32, shape=[1,1])]

        # Simulation graph for control
        self.transfers_pred_simu = [[(tf.compat.v1.placeholder(tf.float32, shape=[1, asize_pred]), tf.compat.v1.placeholder(tf.float32, shape=[1, asize_pred])) for i in range(hln_pred)]]
        self.transfers_cont_simu = [[(tf.compat.v1.placeholder(tf.float32, shape=[1, asize_cont]), tf.compat.v1.placeholder(tf.float32, shape=[1, asize_cont])) for i in range(hln_cont)]]
        for i in range(self.length_cont-1):
            environment_predict = tf.concat([self.Tpreds_simu[-1], self.T_env, self.Psets_simu[-1]], axis=-1)
            output_predict, states_predict = self.agent_predict(environment_predict, self.transfers_pred_simu[-1])
            dT = output_predict
            newTpred = self.Tpreds_simu[-1] + dT*dT_norm

            environment_control = tf.concat([self.Tpreds_simu[-1], newTpred, self.setpoint_T], axis=-1)
            output_control, states_control = self.agent_control(environment_control, self.transfers_cont_simu[-1])
            newPset = output_control

            self.Tpreds_simu.append(newTpred)
            self.Psets_simu.append(newPset)
            self.transfers_pred_simu.append(states_predict)
            self.transfers_cont_simu.append(states_control)

        self.alpha = tf.Variable(1e-5, trainable = False)

        self.prediction_loss = tf.sqrt(tf.reduce_mean([tf.square(T[0, 0] - self.true_T[0, i]) for i, T in enumerate(self.Tpreds_real)]))
        self.control_loss = tf.reduce_mean([tf.math.abs(T[0, 0] - self.setpoint_T[0, 0]) for i, T in enumerate(self.Tpreds_simu[1:])])

        optimizer = tf.compat.v1.train.AdamOptimizer(self.alpha)

        # GET WEIGHTS IN GRAPH
        self.agent_predict_vars = [layer.weights for layer in self.agent_predict.all_layers]
        self.agent_predict_vars += [self.agent_predict.output_layer.weights]

        tmp_foo = lambda l:  (tmp_foo(l[0]) + tmp_foo(l[1:]) if len(l)>0 else []) if isinstance(l, list) else [l]
        self.agent_predict_vars = tmp_foo(self.agent_predict_vars)

        self.agent_control_vars = [layer.weights for layer in self.agent_control.all_layers]
        self.agent_control_vars += [self.agent_control.output_layer.weights]

        tmp_foo = lambda l:  (tmp_foo(l[0]) + tmp_foo(l[1:]) if len(l)>0 else []) if isinstance(l, list) else [l]
        self.agent_control_vars = tmp_foo(self.agent_control_vars)

        # Create gradient and optimization operations
        gradients, variables = zip(*optimizer.compute_gradients(self.prediction_loss, var_list=self.agent_predict_vars))
        gradients, _ = tf.clip_by_global_norm(gradients, 5.0)
        self.prediction_steps = optimizer.apply_gradients(zip(gradients, variables))

        gradients, variables = zip(*optimizer.compute_gradients(self.control_loss, var_list=self.agent_control_vars))
        gradients, _ = tf.clip_by_global_norm(gradients, 5.0)
        self.control_steps = optimizer.apply_gradients(zip(gradients, variables))

