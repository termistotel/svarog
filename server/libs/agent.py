import tensorflow as tf
tf.compat.v1.disable_eager_execution()

class LSTM(tf.keras.layers.Layer):
    def __init__(self, output_shape, activation=tf.nn.tanh):
        super(LSTM, self).__init__()
        self.gammao_dense_layers = []
        self.gammaf_dense_layers = []
        self.gammau_dense_layers = []
        self.c_dense_layers = []
        self.out_shape = output_shape
        self.activation = activation

        self.gammao_dense_layers.append(tf.keras.layers.Dense(self.out_shape,
                                                              kernel_initializer='orthogonal',
                                                              bias_initializer="zeros",
                                                              activation=tf.nn.sigmoid))
#         self.gammao_dense_layers.append(tf.nn.sigmoid)

        self.gammaf_dense_layers.append(tf.keras.layers.Dense(self.out_shape, 
                                                              kernel_initializer='orthogonal',
                                                              activation=tf.nn.sigmoid,
                                                              bias_initializer="ones"))
#         self.gammaf_dense_layers.append(tf.nn.sigmoid)

        self.gammau_dense_layers.append(tf.keras.layers.Dense(self.out_shape,
                                                              kernel_initializer='orthogonal',
                                                              bias_initializer="zeros",
                                                              activation=tf.nn.sigmoid))
#         self.gammau_dense_layers.append(tf.nn.sigmoid)

        self.c_dense_layers.append(tf.keras.layers.Dense(self.out_shape,
                                                         kernel_initializer='glorot_uniform',
                                                         bias_initializer="zeros",
                                                         activation=tf.nn.tanh))
#         self.c_dense_layers.append(tf.nn.tanh)

        self.all_layers = self.gammao_dense_layers + self.gammaf_dense_layers + self.gammau_dense_layers + self.c_dense_layers

    def call(self, inputs, initial_state = None):
        x = inputs
        a, c = initial_state
        tot_inputs = tf.concat([x, a], axis=-1)

        A = tot_inputs
        for layer in self.gammaf_dense_layers:
            A = layer(A)
        gammaf = A

        A = tot_inputs
        for layer in self.gammau_dense_layers:
            A = layer(A)
        gammau = A

        A = tot_inputs
        for layer in self.gammao_dense_layers:
            A = layer(A)
        gammao = A

        A = tot_inputs
        for layer in self.c_dense_layers:
            A = layer(A)
        ctilde = A

        new_c = gammau*ctilde + gammaf*c
        new_a = gammao*self.activation(new_c)

        return new_a, new_a, new_c

    def get_vars(self):
        weights = []
        for layer in self.all_layers:
            try:
                weights.append(layer.weights)
            except:
                print(layer)
        return weights

class Agent():
    def __init__(self, out_shape, c_shape, hln, f, out_activation = tf.nn.sigmoid):
        super(Agent, self).__init__()
        self.all_layers = []
        self.c_shape = c_shape
        self.out_shape = out_shape
        self.hln = hln
        self.f = f

        for _ in range(self.hln):
            layer = LSTM(f)
            self.all_layers.append(layer)
        self.output_layer = tf.keras.layers.Dense(out_shape, activation=out_activation)

    def __call__(self, inputs, states):
        new_states = []

        A = inputs
        for i in range(len(self.all_layers)):
            layer, s = self.all_layers[i], states[i]
            A, new_a, new_c = layer(A, initial_state = s)
            new_states.append((new_a, new_c))
        out = self.output_layer(A)
        return [out, new_states]

    def get_vars(self):
        weights = []
        for layer in self.all_layers:
            try:
                weights.append(layer.weights)
            except:
                print(layer)
        return weights
