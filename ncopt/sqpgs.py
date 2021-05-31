import numpy as np
import cvxopt as cx

    
def sample_points(x, eps, N):
    """
    sample N points uniformly distributed in eps-ball around x
    """
    dim = len(x)
    U = np.random.randn(N, dim)
    norm_U = np.linalg.norm(U, axis = 1)
    R = np.random.rand(N)**(1/dim)
    
    Z = eps * (R/norm_U)[:,np.newaxis] * U
    
    return x + Z


def q_rho(d, rho, H, f_k, gI_k, gE_k, D_f, D_gI, D_gE):
    term1 = rho* (f_k + np.max(D_f @ d))
    
    term2 = 0
    for j in np.arange(len(D_gI)):
        term2 += np.maximum(gI_k[j] + D_gI[j] @ d, 0).max()
    
    term3 = 0
    for l in np.arange(len(D_gE)):
        term2 += np.abs(gE_k[l] + D_gE[l] @ d).max()
    
    term4 = 0.5 * d@H@d
    
    return term1+term2+term3+term4

def phi_rho(x, f, gI, gE, rho):
    term1 = rho*f.eval(x)
    
    term2 = np.sum([np.maximum(gI[j].eval(x), 0) for j in range(len(gI))])
    term3 = np.sum([np.abs(gE[l].eval(x)) for l in range(len(gE))])
    
    return term1+term2+term3

def stop_criterion(gI, gE, g_k, SP, gI_k, gE_k, B_gI, B_gE, nI, nE, pI, pE):
    
    val1 = np.linalg.norm(g_k, np.inf)
    
    # as gI or gE could be empty, we need a max value for empty arrays --> initial argument
    val2 = np.max(gI_k, initial = -np.inf)
    val3 = np.max(np.abs(gE_k), initial = -np.inf)
    
    gI_vals = [np.array([gI[j].eval(B_gI[j][i,:]) for i in np.arange(pI[j]+1)]) for j in np.arange(nI)]
    val4 = -np.inf
    for j in np.arange(nI):
        val4 = np.maximum(val4, np.max(SP.lambda_gI[j] * gI_vals[j]))
    
    gE_vals = [np.array([gE[j].eval(B_gE[j][i,:]) for i in np.arange(pE[j]+1)]) for j in np.arange(nE)]
    val5 = -np.inf
    for j in np.arange(nE):
        val5 = np.maximum(val5, np.max(SP.lambda_gE[j] * gE_vals[j]))
    
    return np.max(np.array([val1, val2, val3, val4, val5]))
 

def compute_gradients(fun, X):
    """ computes gradients of function object f at all rows of array X
    """
    (N, dim) = X.shape
        
    D = np.zeros(X.shape)
    for i in np.arange(N):
        D[i,:] = fun.grad(X[i,:])
            
    return D   

def SQP_GS(f, gI, gE, tol = 1e-8, verbose = True):
    
    eps = 1e-1
    rho = 1e-1
    theta = 1e-1
    
    dim = f.dim
    nI = len(gI)
    nE = len(gE)
    
    p0 = 2 
    pI = 3 *np.ones(nI, dtype = int)
    pE = 4 *np.ones(nE, dtype = int)
    
    eta = 1e-8
    gamma = 0.5
    beta_eps = 0.5
    beta_rho = 0.5
    beta_theta = 0.8
    nu = 10
    xi_s = 1e3
    xi_y = 1e3
    xi_sy = 1e-6
    
    # initialize subproblem object
    SP = Subproblem(dim, nI, nE, p0, pI, pE)
    
    x_k = 2*np.random.randn(dim)
    iter_H = 10
    E_k = np.inf
    max_iter = 100
    
    x_hist = list()
    x_kmin1 = None; g_kmin1 = None;
    s_hist = np.zeros((dim, iter_H))
    y_hist = np.zeros((dim, iter_H))
    
    H = np.eye(dim)
    
    status = 'not optimal'; step = np.nan
    
    hdr_fmt = "%4s\t%10s\t%5s\t%5s\t%10s"
    out_fmt = "%4d\t%10.4g\t%10.4g\t%10.4g\t%10.4g"
    if verbose:
        print(hdr_fmt % ("iter", "f(x_k)", "max(g_j(x_k))", "E_k", "step"))
    
    ##############################################
    # START OF LOOP
    ##############################################
    
    for iter_k in range(max_iter):
        
        if E_k <= tol:
            status = 'optimal'
            break
        
        ##############################################
        # SAMPLING
        ##############################################
        B_f = sample_points(x_k, eps, p0)
        B_f = np.vstack((x_k, B_f))
        
        B_gI = list()
        for j in np.arange(nI):
            B_j = sample_points(x_k, eps, pI[j])
            B_j = np.vstack((x_k, B_j))
            B_gI.append(B_j)
            
        B_gE = list()
        for j in np.arange(nE):
            B_j = sample_points(x_k, eps, pE[j])
            B_j = np.vstack((x_k, B_j))
            B_gE.append(B_j)
            
        # compute gradients for objective+inequality+equality constraints
        D_f = compute_gradients(f, B_f) 
        
        D_gI = list()
        for j in np.arange(nI):
            D_gI.append(compute_gradients(gI[j], B_gI[j]))
 
        D_gE = list()
        for j in np.arange(nE):
            D_gE.append(compute_gradients(gE[j], B_gE[j]))
 
        f_k = f.eval(x_k)
        gI_k = np.array([gI[j].eval(x_k) for j in range(nI)])
        gE_k = np.array([gE[j].eval(x_k) for j in range(nE)])
        
        ##############################################
        # SUBPROBLEM
        ##############################################
        #print("H EIGVALS", np.linalg.eigh(H)[0])

        SP.update(H, rho, D_f, D_gI, D_gE, f_k, gI_k, gE_k)
        
        SP.solve()
        
        d_k = SP.d.copy()
        # compute g_k from paper 
        g_k = SP.lambda_f @ D_f + np.sum([SP.lambda_gI[j] @ D_gI[j] for j in range(nI)], axis = 0)  \
                             +  np.sum([SP.lambda_gE[j] @ D_gE[j] for j in range(nE)], axis = 0)
                                
        
        # evaluate v(x) at x=x_k
        v_k = np.maximum(gI_k, 0).sum() + np.sum(np.abs(gE_k))
        phi_k = rho*f_k + v_k
        
        delta_q = phi_k - q_rho(d_k, rho, H, f_k, gI_k, gE_k, D_f, D_gI, D_gE) 
        
        assert delta_q >= -1e-5
        assert np.abs(SP.lambda_f.sum() - rho) <= 1e-6, f"{np.abs(SP.lambda_f.sum() - rho)}"
        

        if verbose:
            print(out_fmt % (iter_k, f_k, np.max(gI_k), E_k, step))
        
        new_E_k = stop_criterion(gI, gE, g_k, SP, gI_k, gE_k, B_gI, B_gE, nI, nE, pI, pE)
        E_k = min(E_k, new_E_k)
        ##############################################
        # STEP
        ##############################################
        step = delta_q > nu*eps**2 
        if step:
            alpha = 1.
            phi_new = phi_rho(x_k + alpha*d_k, f, gI, gE, rho)
            
            # Armijo step size rule
            while phi_new > phi_k - eta*alpha*delta_q:                
                alpha *= gamma
                phi_new = phi_rho(x_k + alpha*d_k, f, gI, gE, rho)
                
            # update Hessian
            if x_kmin1 is not None:
                s_k = x_k - x_kmin1
                s_hist = np.roll(s_hist, 1, axis = 1)
                s_hist[:,0] = s_k
                
                y_k = g_k - g_kmin1
                y_hist = np.roll(y_hist, 1, axis = 1)
                y_hist[:,0] = y_k
                                
                hH = np.eye(dim)
                for l in np.arange(iter_H):
                    sl = s_hist[:,l]
                    yl = y_hist[:,l]
                    
                    cond = (np.linalg.norm(sl) <= xi_s*eps) and (np.linalg.norm(yl) <= xi_y*eps) and (np.inner(sl,yl) >= xi_sy*eps**2)
                    
                    if cond:
                        Hs = hH@sl
                        hH = hH - np.outer(Hs,Hs)/(sl @ Hs + 1e-16) + np.outer(yl,yl)/(yl @ sl + 1e-16)
                    
                assert np.all(np.abs(hH - hH.T) <= 1e-8), f"{H}"
                
                H = hH.copy()
                
            ####################################
            # ACTUAL STEP
            ###################################
            x_kmin1 = x_k.copy()
            g_kmin1 = g_k.copy()
            
            x_k = x_k + alpha*d_k
                    
        ##############################################
        # NO STEP
        ##############################################
        else:
            if v_k <= theta:
                theta *= beta_theta
            else:
                rho *= beta_rho
            
            eps *= beta_eps
        
        
        x_hist.append(x_k)
            
    ##############################################
    # END OF LOOP
    ##############################################
    x_hist = np.vstack(x_hist)
    
    if E_k > tol:
        status = 'max iterations reached'
    
    print(f"SQP GS terminate with status {status}")
    
    return x_k, x_hist, SP

#%%

class Subproblem:
    def __init__(self, dim, nI, nE, p0, pI, pE):
        """
        dim : solution space dimension
        nI : number of inequality constraints
        nE : number of equality constraints
        p0 : number of sample points for f (excluding x_k itself)
        pI : array, number of sample points for inequality constraint (excluding x_k itself)
        pE : array, number of sample points for equality constraint (excluding x_k itself)
        """
        
        self.dim = dim
        self.nI = nI
        self.nE = nE
        self.p0 = p0
        self.pI = pI
        self.pE = pE
        
        self.P, self.q, self.inG, self.inh, self.nonnegG, self.nonnegh = self.initialize()
        
    
    def solve(self):
        """
        This solves the quadratic program. In every iteration, you should call self.update() before solving in order to have the correct subproblem data.
        
        self.d: array
            search direction
            
        self.lambda_f: array
            KKT multipier for objective.
            
        self.lambda_gE: list
            KKT multipier for equality constraints. 
        
        self.lambda_gI: list
            KKT multipier for inequality constraints.    

        """
        cx.solvers.options['show_progress'] = False
        
        iG = np.vstack((self.inG, self.nonnegG))
        ih = np.hstack((self.inh, self.nonnegh))
        
        qp = cx.solvers.qp(P = cx.matrix(self.P), q = cx.matrix(self.q), G = cx.matrix(iG), h = cx.matrix(ih))
        
        self.cvx_sol_x = np.array(qp['x']).squeeze()
        
        self.d = self.cvx_sol_x[:self.dim]
        self.z = self.cvx_sol_x[self.dim]

        self.rI = self.cvx_sol_x[self.dim +1          : self.dim +1 +self.nI]
        self.rE = self.cvx_sol_x[self.dim +1 + self.nI : ]
        

        assert len(self.rE) == self.nE
        assert np.all(self.rI >= -1e-5) , f"{self.rI}"
        assert np.all(self.rE >= -1e-5), f"{self.rE}"
        
        # extract dual variables = KKT multipliers
        self.cvx_sol_z = np.array(qp['z']).squeeze()
        lambda_f = self.cvx_sol_z[:self.p0+1]
        
        lambda_gI = list()
        for j in np.arange(self.nI):
            start_ix = self.p0+1+(1+self.pI)[:j].sum()
            lambda_gI.append( self.cvx_sol_z[start_ix : start_ix + 1+self.pI[j]]  )
        
        lambda_gE = list()
        for j in np.arange(self.nE):
            start_ix = self.p0+1+(1+self.pI).sum()+(1+self.pE)[:j].sum()
            
            # from ineq with +
            vec1 = self.cvx_sol_z[start_ix : start_ix + 1+self.pE[j]]
            
            # from ineq with -
            vec2 = self.cvx_sol_z[start_ix+(1+self.pE).sum() : start_ix + (1+self.pE).sum() + 1+self.pE[j]]
            
            # see Direction.m line 620
            lambda_gE.append(vec1-vec2)
     
        self.lambda_f = lambda_f.copy()
        self.lambda_gI = lambda_gI.copy()
        self.lambda_gE = lambda_gE.copy()
        
        return 
        
        
    def initialize(self):
        """
        The quadratic subrpoblem we solve in every iteration is of the form:
        
        min_y 1/2* yPy + q*y subject to Gy <= h
        
        variable structure: y=(d,z,rI,rE) with
        d = search direction
        z = helper variable for objective
        rI = helper variable for inequality constraints
        rI = helper variable for equality constraints
        
        This function initializes the variables P,q,G,h. The entries which change in every iteration are then updated in self.update()
        
        G and h consist of two parts:
            1) inG, inh: the inequalities from the paper
            2) nonnegG, nonnegh: nonnegativity bounds rI >= 0, rE >= 0
        """
        
        dimQP = self.dim+1+self.nI+self.nE
        
        P = np.zeros((dimQP,dimQP))
        q = np.zeros(dimQP)
        
        inG = np.zeros((1+self.p0+np.sum(1+self.pI)+2*np.sum(1+self.pE),dimQP))
        inh = np.zeros(1+self.p0+np.sum(1+self.pI)+2*np.sum(1+self.pE))
        
        # structure of inG (p0+1, sum(1+pI), sum(1+pE), sum(1+pE))
        inG[:self.p0+1, self.dim] = -1
        
        for j in range(self.nI):
            inG[self.p0+1+(1+self.pI)[:j].sum()         :  self.p0+1+(1+self.pI)[:j].sum()         + self.pI[j]+1, self.dim+1+j]    = -1
            
            
        for j in range(self.nE):
            inG[self.p0+1+(1+self.pI).sum()+(1+self.pE)[:j].sum()  :  self.p0+1+(1+self.pI).sum()+(1+self.pE)[:j].sum()     + self.pE[j]+1, self.dim+1+self.nI+j] = -1
            inG[self.p0+1+(1+self.pI).sum()+(1+self.pE).sum()+(1+self.pE)[:j].sum() :  self.p0+1+(1+self.pI).sum()+(1+self.pE).sum()+(1+self.pE)[:j].sum() + self.pE[j]+1, self.dim+1+self.nI+j] = -1
            
        
        # we have nI+nE r-variables
        nonnegG = np.hstack((np.zeros((self.nI+self.nE,self.dim+1)), -np.eye(self.nI+self.nE)))
        nonnegh = np.zeros(self.nI+self.nE)
     
        return P,q,inG,inh,nonnegG,nonnegh


    def update(self, H, rho, D_f, D_gI, D_gE, f_k, gI_k, gE_k):
        """

        Parameters
        ----------
        H : array
            Hessian approximation
        rho : float
            parameter
        D_f : array
            gradient of f at the sampled points
        D_gI : list
            j-th element is the gradient array of c^j at the sampled points.
        D_gE : list
            j-th element is the gradient array of h^j at the sampled points.
        f_k : float
            evaluation of f at x_k.
        gI_k : array
            evaluation of inequality constraints at x_k.
        gE_k : array
            evaluation of equality constraints at x_k.
        
        Returns
        -------
        None.

        """
        self.P[:self.dim, :self.dim] = H
        self.q = np.hstack((np.zeros(self.dim), rho, np.ones(self.nI), np.ones(self.nE))) 
        
        
        self.inG[:self.p0+1, :self.dim] = D_f
        self.inh[:self.p0+1] = -f_k
        
        for j in range(self.nI):
            self.inG[self.p0+1+(1+self.pI)[:j].sum()        :  self.p0+1+(1+self.pI)[:j].sum()        + self.pI[j]+1, :self.dim]    = D_gI[j]
            self.inh[self.p0+1+(1+self.pI)[:j].sum()        :  self.p0+1+(1+self.pI)[:j].sum()        + self.pI[j]+1]          = -gI_k[j] 
            
        for j in range(self.nE):
            self.inG[self.p0+1+(1+self.pI).sum()+(1+self.pE)[:j].sum()              :  self.p0+1+(1+self.pI).sum()+(1+self.pE)[:j].sum()              + self.pE[j]+1, :self.dim] = D_gE[j]
            self.inG[self.p0+1+(1+self.pI).sum()+(1+self.pE).sum()+(1+self.pE)[:j].sum() :  self.p0+1+(1+self.pI).sum()+(1+self.pE).sum()+(1+self.pE)[:j].sum() + self.pE[j]+1, :self.dim] = -D_gE[j]
            
            self.inh[self.p0+1+(1+self.pI).sum()+(1+self.pE)[:j].sum()              :  self.p0+1+(1+self.pI).sum()+(1+self.pE)[:j].sum()              + self.pE[j]+1] = -gE_k[j]
            self.inh[self.p0+1+(1+self.pI).sum()+(1+self.pE).sum()+(1+self.pE)[:j].sum() :  self.p0+1+(1+self.pI).sum()+(1+self.pE).sum()+(1+self.pE)[:j].sum() + self.pE[j]+1] = gE_k[j]
            
       
        return        
    

