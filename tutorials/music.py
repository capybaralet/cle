import ipdb
import numpy as np

from cle.cle.data import Iterator
from cle.cle.cost import NllBin
from cle.cle.graph.net import Net
from cle.cle.models import Model
from cle.cle.layers import InitCell
from cle.cle.layers.feedforward import FullyConnectedLayer
from cle.cle.layers.recurrent import LSTM
from cle.cle.train import Training
from cle.cle.train.ext import (
    EpochCount,
    GradientClipping,
    Monitoring,
    Picklize
)
from cle.cle.train.opt import RMSProp
from cle.cle.utils import OrderedDict
from cle.datasets.music import Music


#data_path = '/data/lisa/data/music/MuseData.pickle'
#save_path = '/u/chungjun/repos/cle/saved/'
data_path = '/home/junyoung/data/music/MuseData.pickle'
save_path = '/home/junyoung/repos/cle/saved/'

batch_size = 10
nlabel = 105
debug = 0

model = Model()
trdata = Music(name='train',
               path=data_path,
               nlabel=nlabel)
valdata = Music(name='valid',
                path=data_path,
                nlabel=nlabel)

# Choose the random initialization method
init_W = InitCell('randn')
init_U = InitCell('ortho')
init_b = InitCell('zeros')

model.inputs = trdata.theano_vars()
x, y, mask = model.inputs
# You must use THEANO_FLAGS="compute_test_value=raise" python -m ipdb
if debug:
    x.tag.test_value = np.zeros((10, batch_size, nlabel), dtype=np.float32)
    y.tag.test_value = np.zeros((10, batch_size, nlabel), dtype=np.float32)
    mask.tag.test_value = np.ones((10, batch_size), dtype=np.float32)

inputs = [x, y, mask]
inputs_dim = {'x':nlabel}

h1 = LSTM(name='h1',
          parent=['x'],
          batch_size=batch_size,
          nout=50,
          unit='tanh',
          init_W=init_W,
          init_U=init_U,
          init_b=init_b)

h2 = LSTM(name='h2',
          parent=['x', 'h1'],
          batch_size=batch_size,
          nout=50,
          unit='tanh',
          init_W=init_W,
          init_U=init_U,
          init_b=init_b)

h3 = LSTM(name='h3',
          parent=['x', 'h2'],
          batch_size=batch_size,
          nout=50,
          unit='tanh',
          init_W=init_W,
          init_U=init_U,
          init_b=init_b)

h4 = FullyConnectedLayer(name='h4',
                         parent=['h1', 'h2', 'h3'],
                         nout=nlabel,
                         unit='sigmoid',
                         init_W=init_W,
                         init_b=init_b)

nodes = [h1, h2, h3, h4]
rnn = Net(inputs=inputs, inputs_dim=inputs_dim, nodes=nodes)
y_hat = rnn.build_recurrent_graph(output_args=[h4])[0]
masked_y = y[mask.nonzero()]
masked_y_hat = y_hat[mask.nonzero()]
cost = NllBin(masked_y, masked_y_hat).sum()
nll = NllBin(masked_y, masked_y_hat).mean()
cost.name = 'cost'
nll.name = 'nll'
model.graphs = [rnn]

optimizer = RMSProp(
    lr=0.0001,
    mom=0.95
)

extension = [
    GradientClipping(batch_size=batch_size),
    EpochCount(100),
    Monitoring(freq=10,
               ddout=[cost, nll],
               data=[Iterator(valdata, batch_size)]),
    Picklize(freq=5,
             path=save_path)
]

mainloop = Training(
    name='toy_music',
    data=Iterator(trdata, batch_size),
    model=model,
    optimizer=optimizer,
    cost=cost,
    outputs=[cost],
    extension=extension
)
mainloop.run()
