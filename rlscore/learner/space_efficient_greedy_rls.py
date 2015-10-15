
import random as pyrandom
import numpy as np
import numpy.linalg as la
import scipy.sparse as sp

from rlscore import predictor

class SpaceEfficientGreedyRLS(object):
    
    def loadResources(self):
        """
        Loads the resources from the previously set resource pool.
        
        @raise Exception: when some of the resources required by the learner is not available in the ResourcePool object.
        """
        X = self.resource_pool['X']
        if isinstance(X, sp.base.spmatrix):
            self.X = X.todense()
        else:
            self.X = X
        self.X = self.X.T
        self.Y = self.resource_pool['Y']
        #Number of training examples
        self.size = self.Y.shape[0]
        if self.resource_pool.has_key('bias'):
            self.bias = float(self.resource_pool['bias'])
        else:
            self.bias = 0.
        if self.resource_pool.has_key('measure'):
            self.measure = None
        #    self.measure = self.resource_pool['measure']
        else:
            self.measure = None
        self.results = {}
    
    
    def train(self):
        regparam = float(self.resource_pool['regparam'])
        self.regparam = regparam
        
        ##The current version works only with the squared error measure
        #self.measure = None
        #self.solve_weak(regparam)
        #return
        #if not self.Y.shape[1] == 1:
        self.solve_bu(regparam)
        #else:
        #    self.solve_tradeoff(regparam)
    
    
    def getModel(self):
        return predictor.LinearPredictor(self.A, self.b)
    
    
    def solve_bu(self, regparam):
        """Trains RLS with the given value of the regularization parameter
        
        @param regparam: value of the regularization parameter
        @type regparam: float
        """
        
        self.regparam = regparam
        X = self.X
        Y = self.Y
        
        if not hasattr(self, "bias"):
            self.bias = 0.
        
        tsize = self.size
        fsize = X.shape[0]
        assert X.shape[1] == tsize
        self.A = np.mat(np.zeros((fsize, Y.shape[1])))
        
        rp = regparam
        rpinv = 1. / rp
        
        if not self.resource_pool.has_key('subsetsize'):
            raise Exception("Parameter 'subsetsize' must be given.")
        desiredfcount = int(self.resource_pool['subsetsize'])
        if not fsize >= desiredfcount:
            raise Exception('The overall number of features ' + str(fsize) + ' is smaller than the desired number ' + str(desiredfcount) + ' of features to be selected.')
        
        #Biaz
        bias_slice = np.sqrt(self.bias)*np.mat(np.ones((1,X.shape[1]),dtype=np.float64))
        cv = bias_slice
        ca = rpinv * (1. / (1. + cv * rpinv * cv.T)) * (cv * rpinv)
        
        self.dualvec = rpinv * Y - cv.T * rpinv * (1. / (1. + cv * rpinv * cv.T)) * (cv * rpinv * Y)
        
        diagG = []
        for i in range(tsize):
            diagGi = rpinv - cv.T[i, 0] * ca[0, i]
            diagG.append(diagGi)
        diagG = np.mat(diagG).T
        
        #listX = []
        #for ci in range(fsize):
        #    listX.append(X[ci])
        
        U, S, VT = la.svd(cv, full_matrices = False)
        U, S, VT = np.mat(U), np.mat(S), np.mat(VT)
        Omega = 1. / (S * S + rp) - rpinv
        
        self.selected = []
        
        currentfcount = 0
        self.performances = []
        while currentfcount < desiredfcount:
            
            if not self.measure == None:
                bestlooperf = None
            else:
                bestlooperf = float('inf')
            
            self.looperf = []
            for ci in range(fsize):
                if ci in self.selected: continue
                #cv = listX[ci]
                cv = X[ci]
                GXT_ci = VT.T * np.multiply(Omega.T, (VT * cv.T)) + rpinv * cv.T #GXT[:, ci]
                ca = GXT_ci * (1. / (1. + cv * GXT_ci))
                updA = self.dualvec - ca * (cv * self.dualvec)
                invupddiagG = 1. / (diagG - np.multiply(ca, GXT_ci))
                
                if not self.measure == None:
                    loopred = Y - np.multiply(invupddiagG, updA)
                    looperf_i = self.measure.multiOutputPerformance(Y, loopred)
                    if bestlooperf == None:
                        bestlooperf = looperf_i
                        bestcind = ci
                    if self.measure.comparePerformances(looperf_i, bestlooperf) > 0:
                        bestcind = ci
                        bestlooperf = looperf_i
                else:
                    #This default squared performance is a bit faster to compute than the one loaded separately.
                    loodiff = np.multiply(invupddiagG, updA)
                    #looperf_i = (loodiff.T * loodiff)[0, 0]
                    looperf_i = np.mean(sum(np.multiply(loodiff, loodiff), axis = 0))
                    if looperf_i < bestlooperf:
                        bestcind = ci
                        bestlooperf = looperf_i
                self.looperf.append(looperf_i)
            self.looperf = np.mat(self.looperf)
            
            self.bestlooperf = bestlooperf
            self.performances.append(bestlooperf)
            #cv = listX[bestcind]
            cv = X[bestcind]
            #GXT_bci = GXT[:, bestcind]
            GXT_bci = VT.T * np.multiply(Omega.T, (VT * cv.T)) + rpinv * cv.T
            ca = GXT_bci * (1. / (1. + cv * GXT_bci))
            self.dualvec = self.dualvec - ca * (cv * self.dualvec)
            diagG = diagG - np.multiply(ca, GXT_bci)
            #GXT = GXT - ca * (cv * GXT)
            self.selected.append(bestcind)
            X_sel = X[self.selected]
            if isinstance(X_sel, sp.base.spmatrix):
                X_sel = X_sel.todense()
            U, S, VT = la.svd(np.vstack([X_sel, bias_slice]), full_matrices = False)
            U, S, VT = np.mat(U), np.mat(S), np.mat(VT)
            Omega = 1. / (np.multiply(S, S) + rp) - rpinv
            #print self.selected
            #print self.performances
            currentfcount += 1
            
            #Linear predictor with bias
            self.A[self.selected] = X[self.selected] * self.dualvec
            self.b = bias_slice * self.dualvec
            
            self.callback()
            #print who(locals())
            if not self.callbackfun == None:
                self.callbackfun.callback(self)
        if not self.callbackfun == None:
            self.callbackfun.finished(self)
        self.A[self.selected] = X[self.selected] * self.dualvec
        self.b = bias_slice * self.dualvec
        self.results['selected_features'] = self.selected
        self.results['GreedyRLS_LOO_performances'] = self.performances
    
    
    def solve_tradeoff(self, regparam):
        """Trains RLS with the given value of the regularization parameter
        
        @param regparam: value of the regularization parameter
        @type regparam: float
        """
        
        self.regparam = regparam
        X = self.X
        Y = self.Y
        
        if not hasattr(self, "bias"):
            self.bias = 0.
        
        tsize = self.size
        fsize = X.shape[0]
        assert X.shape[1] == tsize
        self.A = np.mat(np.zeros((fsize, Y.shape[1])))
        
        rp = regparam
        rpinv = 1. / rp
        
        if not self.resource_pool.has_key('subsetsize'):
            raise Exception("Parameter 'subsetsize' must be given.")
        desiredfcount = int(self.resource_pool['subsetsize'])
        if not fsize >= desiredfcount:
            raise Exception('The overall number of features ' + str(fsize) + ' is smaller than the desired number ' + str(desiredfcount) + ' of features to be selected.')
        
        #Biaz
        bias_slice = np.sqrt(self.bias)*np.mat(np.ones((1,X.shape[1]),dtype=np.float64))
        cv = bias_slice
        ca = rpinv * (1. / (1. + cv * rpinv * cv.T)) * (cv * rpinv)
        
        self.dualvec = rpinv * Y - cv.T * rpinv * (1. / (1. + cv * rpinv * cv.T)) * (cv * rpinv * Y)
        
        diagG = []
        for i in range(tsize):
            diagGi = rpinv - cv.T[i, 0] * ca[0, i]
            diagG.append(diagGi)
        diagG = np.mat(diagG).T
        
        #listX = []
        #for ci in range(fsize):
        #    listX.append(X[ci])
        
        U, S, VT = la.svd(cv, full_matrices = False)
        U, S, VT = np.mat(U), np.mat(S), np.mat(VT)
        Omega = 1. / (S * S + rp) - rpinv
        
        self.selected = []
        
        blocksize = 1000
        blocks = []
        blockcount = 0
        while True:
            startind = blockcount * blocksize
            if (blockcount + 1) * blocksize < fsize:
                print blockcount, fsize, (blockcount + 1) * blocksize
                endind = (blockcount + 1) * blocksize
                blocks.append(range(startind, endind))
                blockcount += 1
            else:
                blocks.append(range(startind, fsize))
                blockcount += 1
                break
        
        
        currentfcount = 0
        self.performances = []
        while currentfcount < desiredfcount:
            
            if not self.measure == None:
                self.bestlooperf = None
            else:
                self.bestlooperf = float('inf')
            
            
            looperf = np.mat(np.zeros((1, fsize)))
            
            for blockind in range(blockcount):
                
                block = blocks[blockind]
                
                tempmatrix = np.mat(np.zeros((tsize, len(block))))
                temp2 = np.mat(np.zeros((tsize, len(block))))
                
                X_block = X[block]
                GXT_block = VT.T * np.multiply(Omega.T, (VT * X_block.T)) + rpinv * X_block.T
                
                np.multiply(X_block.T, GXT_block, tempmatrix)
                XGXTdiag = sum(tempmatrix, axis = 0)
                
                XGXTdiag = 1. / (1. + XGXTdiag)
                np.multiply(GXT_block, XGXTdiag, tempmatrix)
                
                tempvec1 = np.multiply((X_block * self.dualvec).T, XGXTdiag)
                np.multiply(GXT_block, tempvec1, temp2)
                np.subtract(self.dualvec, temp2, temp2)
                
                np.multiply(tempmatrix, GXT_block, tempmatrix)
                np.subtract(diagG, tempmatrix, tempmatrix)
                np.divide(1, tempmatrix, tempmatrix)
                np.multiply(tempmatrix, temp2, tempmatrix)
                
                
                if not self.measure == None:
                    np.subtract(Y, tempmatrix, tempmatrix)
                    np.multiply(temp2, 0, temp2)
                    np.add(temp2, Y, temp2)
                    looperf_block = self.measure.multiTaskPerformance(temp2, tempmatrix)
                    looperf_block = np.mat(looperf_block)
                else:
                    np.multiply(tempmatrix, tempmatrix, tempmatrix)
                    looperf_block = sum(tempmatrix, axis = 0)
                looperf[:, block] = looperf_block
                
            if not self.measure == None:
                if self.measure.isErrorMeasure():
                    looperf[0, self.selected] = float('inf')
                    bestcind = np.argmin(looperf)
                    self.bestlooperf = np.amin(looperf)
                else:
                    looperf[0, self.selected] = - float('inf')
                    bestcind = np.argmax(looperf)
                    self.bestlooperf = np.amax(looperf)
            else:
                looperf[0, self.selected] = float('inf')
                bestcind = np.argmin(looperf)
                self.bestlooperf = np.amin(looperf)
                
            self.looperf = looperf
            
            self.performances.append(self.bestlooperf)
            #cv = listX[bestcind]
            cv = X[bestcind]
            #GXT_bci = GXT[:, bestcind]
            GXT_bci = VT.T * np.multiply(Omega.T, (VT * cv.T)) + rpinv * cv.T
            ca = GXT_bci * (1. / (1. + cv * GXT_bci))
            self.dualvec = self.dualvec - ca * (cv * self.dualvec)
            diagG = diagG - np.multiply(ca, GXT_bci)
            #GXT = GXT - ca * (cv * GXT)
            self.selected.append(bestcind)
            X_sel = X[self.selected]
            if isinstance(X_sel, sp.base.spmatrix):
                X_sel = X_sel.todense()
            U, S, VT = la.svd(np.vstack([X_sel, bias_slice]), full_matrices = False)
            U, S, VT = np.mat(U), np.mat(S), np.mat(VT)
            #print U.shape, S.shape, VT.shape
            Omega = 1. / (np.multiply(S, S) + rp) - rpinv
            #print self.selected
            #print self.performances
            currentfcount += 1
            
            #Linear predictor with bias
            self.A[self.selected] = X[self.selected] * self.dualvec
            self.b = bias_slice * self.dualvec
            
            self.callback()
            #print who(locals())
        self.finished()
        self.A[self.selected] = X[self.selected] * self.dualvec
        self.b = bias_slice * self.dualvec
        self.results['selected_features'] = self.selected
        self.results['GreedyRLS_LOO_performances'] = self.performances
        #self.results['predictor'] = self.getModel()
        self.predictor = predictor.LinearPredictor(self.A, self.b)
    
    
    def solve_weak(self, regparam):
        
        self.regparam = regparam
        X = self.X
        Y = self.Y
        
        if not hasattr(self, "bias"):
            self.bias = 0.
        
        tsize = self.size
        fsize = X.shape[0]
        assert X.shape[1] == tsize
        self.A = np.mat(np.zeros((fsize, Y.shape[1])))
        
        rp = regparam
        rpinv = 1. / rp
        
        if not self.resource_pool.has_key('subsetsize'):
            raise Exception("Parameter 'subsetsize' must be given.")
        desiredfcount = int(self.resource_pool['subsetsize'])
        if not fsize >= desiredfcount:
            raise Exception('The overall number of features ' + str(fsize) + ' is smaller than the desired number ' + str(desiredfcount) + ' of features to be selected.')
        
        #Biaz
        bias_slice = np.sqrt(self.bias)*np.mat(np.ones((1,X.shape[1]),dtype=np.float64))
        cv = bias_slice
        ca = rpinv * (1. / (1. + cv * rpinv * cv.T)) * (cv * rpinv)
        
        self.dualvec = rpinv * Y - cv.T * rpinv * (1. / (1. + cv * rpinv * cv.T)) * (cv * rpinv * Y)
        self.F = cv.T * (cv * self.dualvec)
        
        diagG = []
        for i in range(tsize):
            diagGi = rpinv - cv.T[i, 0] * ca[0, i]
            diagG.append(diagGi)
        diagG = np.mat(diagG).T
        
        #listX = []
        #for ci in range(fsize):
        #    listX.append(X[ci])
        
        U, S, VT = la.svd(cv, full_matrices = False)
        U, S, VT = np.mat(U), np.mat(S), np.mat(VT)
        Omega = 1. / (S * S + rp) - rpinv
        
        self.selected = []
        notselected = set(range(fsize))
        currentfcount = 0
        self.performances = []
        while currentfcount < desiredfcount:
            
            if not self.measure == None:
                bestlooperf = None
            else:
                bestlooperf = float('inf')
            
            X_s = X[self.selected]
            
            self.looperf = []
            sample_60 = pyrandom.sample(notselected, len(notselected))
            sample_60 = sorted(sample_60)
            print sample_60
            #sample_60 = pyrandom.sample(notselected, 1)
            for ci in sample_60:
                cv = X[ci]
                GXT_ci = VT.T * np.multiply(Omega.T, (VT * cv.T)) + rpinv * cv.T #GXT[:, ci]
                ca = GXT_ci * (1. / (1. + cv * GXT_ci))
                updA = self.dualvec - ca * (cv * self.dualvec)
                #updF = self.F - X_s.T * (X_s * (ca * (cv * self.dualvec))) + cv.T * (cv * updA)
                updF = bias_slice.T * (bias_slice * updA) + X_s.T * (X_s * updA) + cv.T * (cv * updA) #PREFITTING (SLOW)
                invupddiagG = 1. / (diagG - np.multiply(ca, GXT_ci))
                
                if not self.measure == None:
                    loopred = Y - np.multiply(invupddiagG, updA)
                    looperf_i = self.measure.multiOutputPerformance(Y, loopred)
                    if bestlooperf == None:
                        bestlooperf = looperf_i
                        bestcind = ci
                    if self.measure.comparePerformances(looperf_i, bestlooperf) > 0:
                        bestcind = ci
                        bestlooperf = looperf_i
                else:
                    #This default squared performance is a bit faster to compute than the one loaded separately.
                    updtrainingerr = updF - self.Y
                    updtrainingerr = np.mean(sum(np.multiply(updtrainingerr, updtrainingerr), axis = 0))
                    looperf_i = updtrainingerr
                    #loodiff = np.multiply(invupddiagG, updA)
                    #looperf_i = np.mean(sum(np.multiply(loodiff, loodiff), axis = 0))
                    if looperf_i < bestlooperf:
                        bestcind = ci
                        bestlooperf = looperf_i
                self.looperf.append(looperf_i)
            self.looperf = np.mat(self.looperf)
            
            self.bestlooperf = bestlooperf
            print bestlooperf
            self.performances.append(bestlooperf)
            #cv = listX[bestcind]
            cv = X[bestcind]
            #GXT_bci = GXT[:, bestcind]
            GXT_bci = VT.T * np.multiply(Omega.T, (VT * cv.T)) + rpinv * cv.T
            ca = GXT_bci * (1. / (1. + cv * GXT_bci))
            self.dualvec = self.dualvec - ca * (cv * self.dualvec)
            diagG = diagG - np.multiply(ca, GXT_bci)
            #self.F = self.F + cv.T * (cv * self.dualvec)
            self.F = X_s.T * (X_s * self.dualvec) + cv.T * (cv * self.dualvec)
            #GXT = GXT - ca * (cv * GXT)
            self.selected.append(bestcind)
            notselected.remove(bestcind)
            X_sel = X[self.selected]
            if isinstance(X_sel, sp.base.spmatrix):
                X_sel = X_sel.todense()
            U, S, VT = la.svd(np.vstack([X_sel, bias_slice]), full_matrices = False)
            U, S, VT = np.mat(U), np.mat(S), np.mat(VT)
            Omega = 1. / (np.multiply(S, S) + rp) - rpinv
            currentfcount += 1
            
            #Linear predictor with bias
            self.A[self.selected] = X[self.selected] * self.dualvec
            self.b = bias_slice * self.dualvec
            
            self.callback()
        self.finished()
        self.A[self.selected] = X[self.selected] * self.dualvec
        self.b = bias_slice * self.dualvec
        self.results['selected_features'] = self.selected
        self.results['GreedyRLS_LOO_performances'] = self.performances
        self.predictor = predictor.LinearPredictor(self.A, self.b)


