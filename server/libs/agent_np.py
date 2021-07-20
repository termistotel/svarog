import numpy as np

sigmoid = lambda x: 1/(1 + np.exp(-x))

class Dense_np():
    def __init__(self, output_shape):
        self.output_shape = output_shape
        self.W = None
        self.b = np.random.normal(size=[1, self.output_shape])
    def __call__(self, inputs):
        if self.W is None:
            self.input_shape = inputs.shape[-1]
            self.W = np.random.normal(size=[self.input_shape, self.output_shape])
            self.weights = [self.W, self.b]
        return inputs.dot(self.W) + self.b

class LSTM_np():
    def __init__(self, output_shape, a_shape, activation = sigmoid):
        self.a_shape = a_shape
        self.c_shape = a_shape
        self.gammao_dense_layers = []
        self.gammaf_dense_layers = []
        self.gammau_dense_layers = []
        self.c_dense_layers = []
        self.output_dense_layers = []
        self.out_shape = output_shape

        self.gammao_dense_layers.append(Dense_np(self.c_shape[-1]))
        self.gammao_dense_layers.append(sigmoid)

        self.gammaf_dense_layers.append(Dense_np(self.c_shape[-1]))
        self.gammaf_dense_layers.append(sigmoid)

        self.gammau_dense_layers.append(Dense_np(self.c_shape[-1]))
        self.gammau_dense_layers.append(sigmoid)

        self.c_dense_layers.append(Dense_np(self.c_shape[-1]))
        self.c_dense_layers.append(np.tanh)

        self.output_dense_layers.append(Dense_np(self.out_shape[-1]))
        self.output_dense_layers.append(activation)

        self.all_layers = self.gammao_dense_layers + self.gammaf_dense_layers + self.gammau_dense_layers + self.c_dense_layers + self.output_dense_layers

    def __call__(self, inputs):
        x, a, c = inputs
        tot_inputs = np.concatenate([x, a], axis=-1)

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
        new_a = gammao*np.tanh(new_c)

        A = new_a
        for layer in self.output_dense_layers:
            A = layer(A)
        out = A
        return out, new_a, new_c

    def get_vars(self):
        weights = []
        for layer in self.all_layers:
            try:
                weights += layer.weights
            except:
#                 print(layer)
                pass
        self.weights = weights
        return self.weights

class Agent_np():
    def __init__(self, out_shape, c_shape, hln, f):
        self.all_layers = []
        self.c_shape = c_shape
        self.out_shape = out_shape
        self.hln = hln
        self.f = f

        for _ in range(self.hln):
            self.all_layers.append(LSTM_np([f], c_shape, activation = np.tanh))
        self.all_layers.append(LSTM_np(out_shape, c_shape, activation = sigmoid))

    def __call__(self, inputs):
        x = inputs[0]
        ass = inputs[1:2+self.hln]
        css = inputs[2+self.hln:]
        new_as, new_cs = [], []

        A = x
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
            layer.get_vars()
            try:
                weights += layer.weights
            except:
                print(layer)
        self.weights = weights
        return self.weights