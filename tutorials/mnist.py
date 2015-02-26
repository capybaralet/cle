import ipdb
import numpy as np
import theano
import theano.tensor as T
import time

from cle.cle.graph.net import Net
from cle.cle.layers import InputLayer, OnehotLayer, MulCrossEntropyLayer, InitCell
from cle.cle.layers.layer import FullyConnectedLayer
from cle.cle.train import Training
from cle.cle.train.ext import EpochCount, GradientClipping, Monitoring, Picklize
from cle.cle.train.opt import RMSProp, Adam, Momentum
from cle.cle.util import error, predict
from cle.datasets.mnist import MNIST


# Toy example to use cle!

# Set your dataset
try:
    datapath = '/data/lisa/data/mnist/mnist.pkl'
    (tr_x, tr_y), (val_x, val_y), (test_x, test_y) = np.load(datapath)
except IOError:
    datapath = '/home/junyoung/data/mnist/mnist.pkl'
    (tr_x, tr_y), (val_x, val_y), (test_x, test_y) = np.load(datapath)
savepath = '/home/junyoung/repos/cle/saved/'

batch_size = 128
num_batches = tr_x.shape[0] / batch_size

trdata = MNIST(name='train',
               data=(tr_x, tr_y),
               batch_size=batch_size)
valdata = MNIST(name='valid',
                data=(val_x, val_y),
                batch_size=batch_size)

# Choose the random initialization method
init_W, init_b = InitCell('randn'), InitCell('zeros')

# Define nodes: objects
inp, tar = trdata.theano_vars()
x = InputLayer(name='inp', root=inp, nout=784)
y = InputLayer(name='tar', root=tar, nout=1)
onehot = OnehotLayer(name='onehot',
                     parent=[y],
                     nout=10)
h1 = FullyConnectedLayer(name='h1',
                         parent=[x],
                         nout=1000,
                         unit='relu',
                         init_W=init_W,
                         init_b=init_b)
h2 = FullyConnectedLayer(name='h2',
                         parent=[h1],
                         nout=10,
                         unit='softmax',
                         init_W=init_W,
                         init_b=init_b)
cost = MulCrossEntropyLayer(name='cost', parent=[onehot, h2])

# You will fill in a list of nodes and fed them to the model constructor
nodes = [x, y, onehot, h1, h2, cost]

# Your model will build the Theano computational graph
model = Net(nodes=nodes)
model.build_graph()

# You can access any output of a node by simply doing model.nodes[$node_name].out
cost = model.nodes['cost'].out
err = error(predict(model.nodes['h2'].out), predict(model.nodes['onehot'].out))
cost.name = 'cost'
err.name = 'error_rate'

# Define your optimizer: Momentum (Nesterov), RMSProp, Adam
optimizer = RMSProp(
    lr=0.001
)

extension = [
    GradientClipping(batch_size),
    EpochCount(40),
    Monitoring(freq=100,
               ddout=[cost, err],
               data=[valdata]),
    Picklize(freq=10,
             path=savepath)
]

mainloop = Training(
    name='toy_mnist',
    data=trdata,
    model=model,
    optimizer=optimizer,
    cost=cost,
    outputs=[cost, err],
    extension=extension
)
mainloop.run()

# What are not done yet
# 1. Monitoring                      done!
# 2. Serialization / Checkpoint      done! Thanks to kastnerkyle and Blocks
#                                    working on early stopping
# 3. Dropout: use Theano.clone
# 4. Other Regularization
# 5. RNN                             jych is doing
# 6. CNN                             donghyunlee is doing
# 7. VAE                             laurent-dinh????????? :)
# 8. Predefined nets: larger building block such as MLP, ConvNet and Stacked RNN