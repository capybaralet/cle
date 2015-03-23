import ipdb
import numpy as np
import theano.tensor as T

from cle.cle.layers import InitCell, StemCell
from cle.cle.layers.feedforward import FullyConnectedLayer
from cle.cle.layers.recurrent import RecurrentLayer
from itertools import izip


def batched_dot(A, B):     
    """Batched version of dot-product.     
       
    For A[dim_1, dim_2, dim_3] and B[dim_1, dim_3, dim_4] this         
    is \approx equal to:       
               
    for i in range(dim_1):     
        C[i] = tensor.dot(A, B)        
       
    Returns        
    -------        
        C : shape (dim_1 \times dim_2 \times dim_4)        
    """
    C = A.dimshuffle([0,1,2,'x']) * B.dimshuffle([0,'x',1,2])      
    return C.sum(axis=-2)


class ReadLayer(RecurrentLayer):
    """
    Draw read layer

    Parameters
    ----------
    h_dec   : Linear
    x       : TensorVariable
    \hat{x} : Transformed TensorVariable
    """
    def __init__(self,
                 glimpse_shape=None,
                 input_shape=None,
                 **kwargs):
        super(ReadLayer, self).__init__(self_recurrent=0,
                                        **kwargs)
        self.glimpse_shape = glimpse_shape
        self.input_shape = input_shape

    def fprop(self, XH):
        X, H = XH
        x = X[0]
        x_hat = X[1]
        z = T.zeros((self.batch_size, 5))
        for h, (recname, recout) in izip(H, self.recurrent.items()):
            U = self.params['U_'+recname+self.name]
            z += T.dot(h[:, :recout], U)
        z += self.params['b_'+self.name]
        batch_size, num_channel, height, width = self.input_shape
        x = x.reshape((batch_size*num_channel, height, width))
        x_hat = x_hat.reshape((batch_size*num_channel, height, width))

        centex = z[:, 0]
        centey = z[:, 1]
        logvar = z[:, 2]
        logdel = z[:, 3]
        loggam = z[:, 4]

        centy = (self.input_shape[2] + 1) * (centey + 1) / 2.
        centx = (self.input_shape[3] + 1) * (centex + 1) / 2.
        sigma = T.exp(0.5 * logvar)
        gamma = T.exp(loggam).dimshuffle(0, 'x', 'x')
        delta = T.exp(logdel)
        delta = (max(self.input_shape[2], self.input_shape[3]) - 1) * delta / (max(self.glimpse_shape[2], self.glimpse_shape[3]) - 1)

        Fx, Fy = self.filter_bank(centx, centy, delta, sigma)
        x = batched_dot(batched_dot(Fy, x), Fx.transpose(0, 2, 1))
        x_hat = batched_dot(batched_dot(Fy, x_hat), Fx.transpose(0, 2, 1))
        x = x * gamma
        x_hat = x_hat * gamma
        reshape_shape = (batch_size, num_channel*self.glimpse_shape[2]*self.glimpse_shape[3])
        return T.concatenate([x.reshape(reshape_shape), x_hat.reshape(reshape_shape)], axis=1)

    def filter_bank(self, c_x, c_y, delta, sigma):
        tol = 1e-4
        y_mesh = T.arange(self.glimpse_shape[2]) - (0.5 * self.glimpse_shape[2]) - 0.5
        x_mesh = T.arange(self.glimpse_shape[3]) - (0.5 * self.glimpse_shape[3]) - 0.5

        a = T.arange(self.input_shape[2])
        b = T.arange(self.input_shape[3])
        mu_x = c_x.dimshuffle(0, 'x') + delta.dimshuffle(0, 'x') * x_mesh
        mu_y = c_y.dimshuffle(0, 'x') + delta.dimshuffle(0, 'x') * y_mesh

        Fy = T.exp(-(a - mu_y.dimshuffle(0, 1, 'x'))**2) / (2. * (sigma.dimshuffle(0, 'x', 'x') + tol)**2)
        Fx = T.exp(-(b - mu_x.dimshuffle(0, 1, 'x'))**2) / (2. * (sigma.dimshuffle(0, 'x', 'x') + tol)**2)

        Fy = Fy / Fy.sum(axis=-1).dimshuffle(0, 1, 'x')
        Fx = Fx / Fx.sum(axis=-1).dimshuffle(0, 1, 'x')
        return Fx, Fy

    def initialize(self):
        for recname, recout in self.recurrent.items():
            U_shape = (recout, 5)
            U_name = 'U_'+recname+self.name
            self.alloc(self.init_U.get(U_shape, U_name))
        self.alloc(self.init_b.get(5, 'b_'+self.name))


class WriteLayer(StemCell):
    """
    Draw write layer

    Parameters
    ----------
    .. todo::
    """
    def __init__(self,
                 glimpse_shape=None,
                 input_shape=None,
                 **kwargs):
        super(WriteLayer, self).__init__(**kwargs)
        self.glimpse_shape = glimpse_shape
        self.input_shape = input_shape

    def fprop(self, X):
        w, X = X[0], X[1:] 
        z = T.zeros((w.shape[0], 5))
        for x, (parname, parout) in izip(X, self.parent.items()[1:]):
            W = self.params['W_'+parname+self.name]
            z += T.dot(x[:, :parout], W)
        z += self.params['b_'+self.name]
        batch_size, num_channel, height, width = self.glimpse_shape
        w = w.reshape((batch_size*num_channel, height, width))
       
        centex = z[:, 0]
        centey = z[:, 1]
        logvar = z[:, 2]
        logdel = z[:, 3]
        loggam = z[:, 4]

        centx = (self.input_shape[3] + 1) * (centex + 1) / 2.
        centy = (self.input_shape[2] + 1) * (centey + 1) / 2.
        sigma = T.exp(0.5 * logvar)
        gamma = T.exp(loggam).dimshuffle(0, 'x', 'x')
        delta = T.exp(logdel)
        delta = (max(self.input_shape[2], self.input_shape[3]) - 1) * delta / (max(self.glimpse_shape[2], self.glimpse_shape[3]) - 1)

        Fx, Fy = self.filter_bank(centx, centy, delta, sigma)
        w = batched_dot(batched_dot(Fy.transpose(0, 2, 1), w), Fx)
        w = w / gamma
        reshape_shape = (batch_size, num_channel*self.input_shape[2]*self.input_shape[3])
        return w.reshape((reshape_shape))

    def filter_bank(self, c_x, c_y, delta, sigma):
        tol = 1e-4
        y_mesh = T.arange(self.glimpse_shape[2]) - (0.5 * self.glimpse_shape[2]) - 0.5
        x_mesh = T.arange(self.glimpse_shape[3]) - (0.5 * self.glimpse_shape[3]) - 0.5

        a = T.arange(self.input_shape[2])
        b = T.arange(self.input_shape[3])
        mu_x = c_x.dimshuffle(0, 'x') + delta.dimshuffle(0, 'x') * x_mesh
        mu_y = c_y.dimshuffle(0, 'x') + delta.dimshuffle(0, 'x') * y_mesh

        Fy = T.exp(-(a - mu_y.dimshuffle(0, 1, 'x'))**2) / (2. * (sigma.dimshuffle(0, 'x', 'x') + tol)**2)
        Fx = T.exp(-(b - mu_x.dimshuffle(0, 1, 'x'))**2) / (2. * (sigma.dimshuffle(0, 'x', 'x') + tol)**2)

        Fy = Fy / Fy.sum(axis=-1).dimshuffle(0, 1, 'x')
        Fx = Fx / Fx.sum(axis=-1).dimshuffle(0, 1, 'x')
        return Fx, Fy

    def initialize(self):
        for parname, parout in self.parent.items()[1:]:
            W_shape = (parout, 5)
            W_name = 'W_'+parname+self.name
            self.alloc(self.init_W.get(W_shape, W_name))
        self.alloc(self.init_b.get(5, 'b_'+self.name))


class CanvasLayer(RecurrentLayer):
    """
    Canvas layer

    Parameters
    ----------
    .. todo::
    """
    def fprop(self, XH):
        X, H = XH
        c_t = X[0]
        c_tm1 = H[0]
        z = c_tm1 + c_t
        z.name = self.name
        return z

    def initialize(self):
        pass


class ErrorLayer(RecurrentLayer):
    """
    Error layer

    Parameters
    ----------
    .. todo::
    """
    def __init__(self,
                 is_binary=0,
                 is_gaussian=0,
                 is_gaussian_mixture=0,
                 **kwargs):
        super(ErrorLayer, self).__init__(self_recurrent=0,
                                         **kwargs)
        self.is_binary = is_binary
        self.is_gaussian = is_gaussian
        self.is_gaussian_mixture = is_gaussian_mixture
        if self.is_binary:
            self.dist = self.which_method('binary')
        elif self.is_gaussian:
            self.dist = self.which_method('gaussian')
        elif self.is_gaussian_mixture:
            self.dist = self.which_method('gaussian_mixture')

    def which_method(self, which):
        return getattr(self, which)

    def fprop(self, XH):
        X, H = XH
        x = X[0]
        z = x - self.dist(H)
        z.name = self.name
        return z

    def binary(self, X):
        x = X[0]
        z = T.nnet.sigmoid(x)
        return z

    def gaussian(self, X):
        mu = X[0]
        logvar = X[1]
        epsilon = self.theano_rng.normal(size=mu.shape,
                                         avg=0., std=1.,
                                         dtype=mu.dtype)
        z = mu + T.sqrt(T.exp(logvar)) * epsilon
        return z

    def gaussian_mixture(self, X):
        mu = X[0]
        logvar = X[1]
        coeff = X[2]
        mu = mu.reshape((mu.shape[0],
                         mu.shape[1]/coeff.shape[-1],
                         coeff.shape[-1]))
        logvar = logvar.reshape((logvar.shape[0],
                                 logvar.shape[1]/coeff.shape[-1],
                                 coeff.shape[-1]))
        idx = predict(
            self.theano_rng.multinomial(
                pvals=coeff,
                dtype=coeff.dtype
            ),
            axis=1
        )
        mu = mu[T.arange(mu.shape[0]), :, idx]
        sig = T.sqrt(T.exp(logvar[T.arange(logvar.shape[0]), :, idx]))
        sample = self.theano_rng.normal(size=mu.shape,
                                        avg=mu, std=sig,
                                        dtype=mu.dtype)
        return sample

    def __getstate__(self):
        dic = self.__dict__.copy()
        dic.pop('sample')
        return dic
    
    def __setstate__(self, state):
        self.__dict__.update(state)
        if self.is_binary:
            self.dist = self.which_method('binary')
        elif self.is_gaussian:
            self.dist = self.which_method('gaussian')
        elif self.is_gmm:
            self.dist = self.which_method('gaussian_mixture')

    def initialize(self):
        pass       
