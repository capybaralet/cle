import ipdb
import logging
import theano
import theano.tensor as T

from theano.compat.python2x import OrderedDict
from cle.cle.utils import sharedX


logger = logging.getLogger(__name__)


class Optimizer(object):
    def __init__(self, lr, lr_scalers=None):
        """
        .. todo::

            WRITEME
        """
        self.lr = sharedX(lr)
        if lr_scalers is not None:
            self.lr_scalers = lr_scalers
        else:
            self.lr_scalers = OrderedDict()

    def get_updates(self):
        """
        .. todo::

            WRITEME
        """
        pass

    def monitor(self):
        """
        .. todo::

            WRITEME
        """
        pass


class Momentum(Optimizer):
    """
    .. todo::

        WRITEME
    """
    def __init__(self,
                 mom=0.9,
                 nesterov=False,
                 **kwargs):
        self.__dict__.update(locals())
        del self.self
        super(Momentum, self).__init__(**kwargs)

    def get_updates(self, grads):
        """
        .. todo::

            WRITEME
        """
        updates = OrderedDict()
        for p, g in grads.items():
            lr_scaler = self.lr_scalers.get(str(p), 1.)
            u = sharedX(p.get_value() * 0.)
            u_t = self.mom * u - self.lr * g
            if self.nesterov:
                u_t = self.mom * u_t - lr_scaler * self.lr * g
            p_t = p + u_t
            updates[u] = u_t
            updates[p] = p_t
        return updates

    def monitor(self):
        logger.info("\tLearning rate: %f" % self.lr.get_value())
        logger.info("\tMomentum: %f" % self.mom)


class RMSProp(Optimizer):
    """
    .. todo::

        WRITEME
    """
    def __init__(self, mom=0.9, sec_mom=0.95, e=1e-4, **kwargs):
        self.__dict__.update(locals())
        del self.self
        super(RMSProp, self).__init__(**kwargs)

    def get_updates(self, grads):
        """
        .. todo::

            WRITEME
        """
        updates = OrderedDict()
        for p, g in grads.items():
            lr_scaler = self.lr_scalers.get(str(p), 1.)
            u = sharedX(p.get_value() * 0.)
            avg_grad = sharedX(p.get_value() * 0.)
            sqr_grad = sharedX(p.get_value() * 0.)
            avg_grad_t = self.sec_mom * avg_grad + (1 - self.sec_mom) * g
            sqr_grad_t = self.sec_mom * sqr_grad + (1 - self.sec_mom) * g**2
            g_t = g / T.sqrt(sqr_grad_t - avg_grad_t**2 + self.e)
            u_t = self.mom * u - lr_scaler * self.lr * g_t
            p_t = p + u_t
            updates[avg_grad] = avg_grad_t
            updates[sqr_grad] = sqr_grad_t
            updates[u] = u_t
            updates[p] = p_t
        return updates

    def monitor(self):
        logger.info("\tLearning rate: %f" % self.lr.get_value())
        logger.info("\tMomentum: %f" % self.mom)
        logger.info("\tSecond Momentum: %f" % self.sec_mom)


class Adam(Optimizer):
    """
    .. todo::

        WRITEME
    """
    def __init__(self, b1=0.9, b2=0.999, lambd=1-1e-8, e=1e-8, **kwargs):
        self.__dict__.update(locals())
        del self.self
        super(Adam, self).__init__(**kwargs)
        if theano.config.floatX == 'float16':
            self.lambd = 1 - 1e-7
            self.e = 1e-7

    def get_updates(self, grads):
        """
        .. todo::

            WRITEME
        """
        updates = OrderedDict()
        cnt = sharedX(0, 'counter')
        for p, g in grads.items():
            lr_scaler = self.lr_scalers.get(str(p), 1.)
            m = sharedX(p.get_value() * 0.)
            v = sharedX(p.get_value() * 0.)
            b1 = self.b1 * self.lambd**cnt
            m_t = b1 * m + (1 - b1) * g
            v_t = self.b2 * v + (1 - self.b2) * g**2
            m_t_hat = m_t / (1. - self.b1**(cnt + 1))
            v_t_hat = v_t / (1. - self.b2**(cnt + 1))
            g_t = m_t_hat / (T.sqrt(v_t_hat) + self.e)
            p_t = p - lr_scaler * self.lr * g_t
            updates[m] = m_t
            updates[v] = v_t
            updates[p] = p_t
        updates[cnt] = cnt + 1
        return updates

    def monitor(self):
        logger.info("\tLearning rate: %f" % self.lr.get_value())
        logger.info("\tBeta_1: %f" % self.b1)
        logger.info("\tBeta_2: %f" % self.b2)
