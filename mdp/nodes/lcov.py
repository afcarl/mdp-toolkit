import mdp

# import numeric module (scipy, Numeric or numarray)
numx = mdp.numx

utils = mdp.utils
mult = utils.mult
tr = numx.transpose

# precision warning parameters
_limits = { 'd' : 1e13, 'f' : 1e5}

def _check_roundoff(t, type):
    """Check if t is so large that t+1 == t up to 2 precision digits"""   
    if _limits.has_key(type):
        if int(t) >= _limits[type]:
            wr = 'You have summed %e entries in the covariance matrix.'%t+\
                 '\nAs you are using typecode \'%s\', you are '%type+\
                 'probably getting severe round off'+\
                 '\nerrors. See CovarianceMatrix docstring for more'+\
                 ' information.'
            raise mdp.MDPWarning, wr

class CovarianceMatrix(object):
    """This class stores an empirical covariance matrix that can be updated
    incrementally. A call to the function 'fix' returns the current state of
    the covariance matrix, the average and the number of observations, and
    resets the internal data.

    Note that the internal sum is a standard __add__ operation. We are not
    using any of the fancy sum algorithms to avoid round off errors when
    adding many numbers. If you want to contribute a CovarianceMatrix class
    that uses such algorithms we would be happy to include it in MDP.
    For a start see the Python recipe by Raymond Hettinger at
    http://aspn.activestate.com/ASPN/Cookbook/Python/Recipe/393090
    For a review about floating point arithmetic and its pitfalls see
    http://docs.sun.com/source/806-3568/ncg_goldberg.html
    """

    def __init__(self, typecode = None):
        """If typecode is not defined, it will be inherited from the first
        data bunch received by 'update'.
        All the matrices in this class are set up with the given typecode and
        no upcast is possible.
        """
        
        self._typecode = typecode

        # covariance matrix, updated during the training phase
        self._cov_mtx = None
        # average, updated during the training phase
        self._avg = None
         # number of observation so far during the training phase
        self._tlen = 0

    def _init_internals(self, x):
        """Inits some internals structures. The reason this is not done in
        the constructor is that we want to be able to derive the input
        dimension and the typecode directly from the data this class receives.
        """
        
        # init typecode
        if not self._typecode:
            self._typecode = x.typecode()
        dim = x.shape[1]
        self._input_dim = dim
        type = self._typecode
        # init covariance matrix
        self._cov_mtx = numx.zeros((dim,dim), type)
        # init average
        self._avg = numx.zeros(dim, type)

    def update(self, x):
        if self._cov_mtx is None:
            self._init_internals(x)
            
        #?? check the input dimension

        # cast input
        x = utils.refcast(x, self._typecode)
        
        # update the covariance matrix, the average and the number of
        # observations (try to do everything inplace)
        self._cov_mtx += mult(tr(x), x)
        self._avg += numx.sum(x, 0)
        self._tlen += x.shape[0]

    def fix(self):
        """Returns a triple containing the covariance matrix, the average and
        the number of observations. The covariance matrix is then reset to
        a zero-state."""
        # local variables
        type = self._typecode
        tlen = utils.scast(self._tlen, type)
        _check_roundoff(tlen, type)
        avg = self._avg
        cov_mtx = self._cov_mtx

        ##### fix the training variables
        # fix the covariance matrix (try to do everything inplace)
        avg_mtx = numx.outerproduct(avg,avg)
        avg_mtx /= tlen*(tlen - utils.scast(1, type))
        cov_mtx /= tlen - utils.scast(1, type)
        cov_mtx -= avg_mtx
        # fix the average
        avg /= tlen

        ##### clean up
        # covariance matrix, updated during the training phase
        self._cov_mtx = None
        # average, updated during the training phase
        self._avg = None
         # number of observation so far during the training phase
        self._tlen = 0

        return cov_mtx, avg, tlen


class DelayCovarianceMatrix(object):    
    """This class stores an empirical covariance matrix between the signal and
    time delayed signal that can be updated incrementally.

    Note that the internal sum is a standard __add__ operation. We are not
    using any of the fancy sum algorithms to avoid round off errors when
    adding many numbers. If you want to contribute a CovarianceMatrix class
    that uses such algorithms we would be happy to include it in MDP.
    For a start see the Python recipe by Raymond Hettinger at
    http://aspn.activestate.com/ASPN/Cookbook/Python/Recipe/393090
    For a review about floating point arithmetic and its pitfalls see
    http://docs.sun.com/source/806-3568/ncg_goldberg.html
    """

    def __init__(self, dt, typecode = None):
        """dt is the time delay. If dt==0, DelayCovarianceMatrix equals
        CovarianceMatrix. If typecode is not defined, it will be inherited from
        the first data bunch received by 'update'.
        All the matrices in this class are set up with the given typecode and
        no upcast is possible.
        """

        # time delay
        self._dt = int(dt)
        
        self._typecode = typecode

        # clean up variables to spare on space
        self._cov_mtx = None
        self._avg = None
        self._avg_dt = None
        self._tlen = 0

    def _init_internals(self, x):
        """Inits some internals structures. The reason this is not done in
        the constructor is that we want to be able to derive the input
        dimension and the typecode directly from the data this class receives.
        """
        
        # init typecode
        if not self._typecode:
            self._typecode = x.typecode()
        dim = x.shape[1]
        self._input_dim = dim
        # init covariance matrix
        self._cov_mtx = numx.zeros((dim,dim), self._typecode)
        # init averages
        self._avg = numx.zeros(dim, self._typecode)
        self._avg_dt = numx.zeros(dim, self._typecode)

    def update(self, x):
        if self._cov_mtx is None:
            self._init_internals(x)

        # cast input
        x = utils.refcast(x, self._typecode)

        dt = self._dt

        # the number of data points in each block should be at least dt+1
        tlen = x.shape[0]
        if tlen < (dt+1):
            errstr = 'Block length is %d, should be at least %d.' % (tlen,dt+1)
            raise mdp.MDPException, errstr
        
        # update the covariance matrix, the average and the number of
        # observations (try to do everything inplace)
        self._cov_mtx += mult(tr(x[:tlen-dt,:]), x[dt:tlen,:])
        totalsum = numx.sum(x, 0)
        self._avg += totalsum - numx.sum(x[tlen-dt:,:], 0)
        self._avg_dt += totalsum - numx.sum(x[:dt,:], 0)
        self._tlen += tlen-dt

    def fix(self, A=None):
        """The collected data is adjusted to compute the covariance matrix of
        the signal x(1)...x(N-dt) and the delayed signal x(dt)...x(N),
        which is defined as <(x(t)-<x(t)>)*(x(t+dt)-<x(t+dt)>)> .
        The function returns a tuple containing the covariance matrix,
        the average <x(t)> over the first N-dt points, the average of the
        delayed signal <x(t+dt)> and the number of observations. The internal
        data is then reset to a zero-state.
        
        If A is defined, the covariance matrix is transformed by the linear
        transformation Ax . E.g. to whiten the data, A is the whitening matrix.
        """
        
        # local variables
        type = self._typecode
        tlen = utils.scast(self._tlen, type)
        _check_roundoff(tlen, type)
        avg = self._avg
        avg_dt = self._avg_dt
        cov_mtx = self._cov_mtx

        ##### fix the training variables
        # fix the covariance matrix (try to do everything inplace)
        avg_mtx = numx.outerproduct(avg, avg_dt)
        avg_mtx /= tlen
                 
        cov_mtx -= avg_mtx
        cov_mtx /= tlen - utils.scast(1, type)

        if A is not None:
            cov_mtx = mult(A,mult(cov_mtx, tr(A)))
        
        # fix the average
        avg /= tlen
        avg_dt /= tlen

        ##### clean up variables to spare on space
        self._cov_mtx = None
        self._avg = None
        self._avg_dt = None
        self._tlen = 0

        return cov_mtx, avg, avg_dt, tlen