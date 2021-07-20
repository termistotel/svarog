import tf

class LSTM(tf.keras.layers.Layer):
    def __init__(self, output_shape, a_shape, activation = tf.nn.sigmoid):
        super(LSTM, self).__init__()
        self.a_shape = a_shape
        self.c_shape = a_shape
        self.gammao_dense_layers = []
        self.gammaf_dense_layers = []
        self.gammau_dense_layers = []
        self.c_dense_layers = []
        self.output_dense_layers = []
        self.out_shape = output_shape

        self.gammao_dense_layers.append(tf.keras.layers.Dense(self.c_shape[-1]))
        self.gammao_dense_layers.append(tf.nn.sigmoid)

        self.gammaf_dense_layers.append(tf.keras.layers.Dense(self.c_shape[-1]))
        self.gammaf_dense_layers.append(tf.nn.sigmoid)

        self.gammau_dense_layers.append(tf.keras.layers.Dense(self.c_shape[-1]))
        self.gammau_dense_layers.append(tf.nn.sigmoid)

        self.c_dense_layers.append(tf.keras.layers.Dense(self.c_shape[-1]))
        self.c_dense_layers.append(tf.nn.tanh)

        self.output_dense_layers.append(tf.keras.layers.Dense(self.out_shape[-1]))
        self.output_dense_layers.append(activation)

        self.all_layers = self.gammao_dense_layers + self.gammaf_dense_layers + self.gammau_dense_layers + self.c_dense_layers + self.output_dense_layers

    def call(self, inputs):
        x, a, c = inputs
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
        new_a = gammao*tf.nn.tanh(new_c)

        A = new_a
        for layer in self.output_dense_layers:
            A = layer(A)
        out = A
        return out, new_a, new_c

    def get_vars(self):
        weights = []
        for layer in self.all_layers:
            try:
                weights.append(layer.weights)
            except:
                print(layer)
        return weights

class Agent(tf.keras.Model):
    def __init__(self, out_shape, c_shape, hln, f):
        super(Agent, self).__init__()
        self.all_layers = []
        self.c_shape = c_shape
        self.out_shape = out_shape
        self.hln = hln
        self.f = f

        for _ in range(self.hln):
            self.all_layers.append(LSTM([f], c_shape, activation = tf.nn.tanh))
        self.all_layers.append(LSTM(out_shape, c_shape, activation = tf.nn.sigmoid))

    def call(self, inputs):
        x = inputs[0]
        ass = inputs[1:2+hln]
        css = inputs[2+hln:]
#         print(len(ass), len(css))
        new_as, new_cs = [], []

        A = x
#         for layer, a, c in zip(self.all_layers, ass, css):
        for i in range(len(self.all_layers)):
            layer, a, c = self.all_layers[i], ass[i], css[i]
            A, new_a, new_c = layer([A, a, c])
            new_as.append(new_a)
            new_cs.append(new_c)
        out = A
        return [out, *new_as, *new_cs]

    def get_vars(self):
        weights = []
        for layer in self.all_layers:
            try:
                weights.append(layer.weights)
            except:
                print(layer)
        return weights
