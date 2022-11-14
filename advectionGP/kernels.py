import numpy as np

class Kernel():
    def __init__(self):
        assert False, "Not implemented" #TODO Turn into an exception
    def generateFeatures(self,N_D,N_feat):
        assert False, "Not implemented" #TODO Turn into an exception
    def computePhi(self):
        assert False, "Not implemented" #TODO Turn into an exception
    def getPhiValues(self,particles):
        assert False, "Not implemented" #TODO Turn into an exception

class EQ(Kernel):
    def __init__(self,l2,sigma2):
        """
        A Exponentiated Quadratic kernel
        Arguments:
            l2 == lengthscale (or lengthscales in a list of the length of the number of dimensions).
            sigma2 == variance of kernel
        """
        self.l2 = l2
        self.sigma2 = sigma2
        self.W = None #need to be set by calling generateFeatures.
        self.b = None 
                
    def generateFeatures(self,N_D,N_feat,boundary):
        """
        Create a random basis for the kernel sampled from the normal distribution.
        Here W is a list of weights for the t,x and y dimentions and b is a linear addition.
        Arguments:
            N_D = number of dimensions
            N_feat = number of features
            boundary = a list of two lists describing the lower and upper corners of the domain [not used by this class]
        """
        if np.isscalar(self.l2):
            self.l2 = np.repeat(self.l2,N_D)
        self.W = np.random.normal(0,1.0,size=(N_feat,N_D))
        self.b = np.random.uniform(0.,2*np.pi,size=N_feat)
        self.N_D = N_D
        self.N_feat = N_feat
        
 
    def getPhi(self,coords):
        """
        Generates a (N_feat,Nt,Nx,Ny) matrix of basis vectors using features from generateFeatures 
        Arguments:
            coords: map of all (t,x,y) points in the grid
        """
        assert self.W is not None, "Need to call generateFeatures before computing phi."
        norm = 1./np.sqrt(self.N_feat)
        
        #We assume that we are using the e^-(1/2 * x^2/l^2) definition of the EQ kernel,
        #(in Mauricio's definition he doesn't use the 1/2 factor - but that's less standard).
        #c=np.sqrt(2.0)/(self.l2)
        ####c=1/(self.l2)
        for w,b in zip(self.W,self.b):
            phi=norm*np.sqrt(2*self.sigma2)*np.cos(np.einsum('i,i...->...',w/self.l2,coords)+ b)
            yield phi                       

    def getPhiValues(self,particles):
        """
        Evaluates all features at location of all particles.
                
        Nearly a duplicate of getPhi, this returns phi for the locations in particles. 
        
        Importantly, particles is of shape N_ObsxN_Particlesx3,
        (typically N_Obs is the number of observations, N_ParticlesPerObs is the number of particles/observation. 3 is the dimensionality of the space).
        
        Returns array (Nfeats, N_ParticlesPerObs, N_Obs)
        
        """
        c=1/(self.l2)
        norm = 1./np.sqrt(self.N_feat)
        return norm*np.sqrt(2*self.sigma2)*np.cos(np.einsum('ij,lkj',self.W/self.l2,particles)+self.b[:,None,None])
  


def meshgridndim(boundary,Nsteps):
    """Returns points in a uniform grid within the boundary
    
    Parameters:
        boundary = a list of two lists describing the lower and upper corners of the domain.
            each list will be of Ndims long.
        Nsteps = number of steps in each dimension.
    Returns:
        Returns a matrix of shape: (Nsteps^Ndims, Ndims)
    """
    Ndims = len(boundary[0])
    g = np.array(np.meshgrid(*[np.linspace(a,b,Nsteps) for a,b in zip(boundary[0],boundary[1])]))
    return g.reshape(Ndims,Nsteps**Ndims).T

from advectionGP.kernels import Kernel
class GaussianBases(Kernel):
    def __init__(self,l2,sigma2,random=False):
        """
        A Exponentiated Quadratic kernel
        Arguments:
            l2 == lengthscale (or lengthscales in a list of the length of the number of dimensions).
            sigma2 == variance of kernel
            random = whether to sample the points randomly or in a uniform grid (default False)
        """
        self.l2 = l2
        self.sigma2 = sigma2
        self.W = None #need to be set by calling generateFeatures.
        self.b = None 
        self.mu= None
        self.random = random
                
    def generateFeatures(self,N_D,N_feat,boundary):
        """
        Create a basis for the kernel, distributed in a grid/random over part of domain defined by 'boundary'.
        
        Arguments:
            N_D = number of dimensions
            N_feat = number of features          
            boundary = a list of two lists describing the lower and upper corners of the domain.
        """    
        assert len(boundary[0])==N_D
        if np.isscalar(self.l2):
            self.l2 = np.repeat(self.l2,N_D)                    
        if self.random:
            self.mu = np.random.uniform(boundary[0],boundary[1],size=(N_feat,N_D))
        else:
            Nsteps = int(np.round(N_feat**(1/N_D))) #e.g. 100 features asked for, 2 dimensions -> 100^(1/2) = 10 steps in each dim.        
            self.mu = meshgridndim(boundary,Nsteps)
            #updated number of features...
            N_feat = len(self.mu)


        self.N_D = N_D
        self.N_feat = N_feat
 
    def getPhi(self,coords):
        """
        Generates a series (of N_feat) matrices, shape (Nt,Nx,Ny) of compact basis vectors using features from generateFeatures 
        Arguments:
            coords: an array of D x [Nt, Nx, Ny, Nz...] coords of points
        Notes:
            uses self.mu, N_feat x D
        """
        norm_const = (1/np.sqrt(np.prod(self.l2)))*(1/(0.5*np.pi)**(0.25*len(self.l2)))
        for centre in self.mu:
            sqrdists = np.sum(((coords.T - centre)/self.l2)**2,-1).T
            phi = norm_const * np.exp(-sqrdists)
            yield phi
            
    def getPhiValues(self,particles):
        """
        Evaluates all features at location of all particles.
        
        
        Nearly a duplicate of getPhi, this returns phi for the locations in particles. 
        
        Importantly, particles is of shape N_ObsxN_Particlesx3,
        (typically N_Obs is the number of observations, N_ParticlesPerObs is the number of particles/observation. 3 is the dimensionality of the space).
        
        Returns array (Nfeats, N_ParticlesPerObs, N_Obs)
        
        """
        mu=self.mu
        coordList=particles
        phi=np.zeros([mu.shape[0],particles.shape[1],particles.shape[0]])
        for i,mus in enumerate(self.mu):
            phi[i,:,:]=((1/np.sqrt(2*self.sigma2*np.pi))*np.exp(-(1/(2*self.l2[0]**2))*((mus[0]-np.array(coordList[:,:,0]))**2))*(1/np.sqrt(2*self.sigma2*np.pi))*np.exp(-(1/(2*self.l2[1]**2))*((mus[1]-np.array(coordList[:,:,1]))**2))*(1/np.sqrt(2*self.sigma2*np.pi))*np.exp(-(1/(2*self.l2[2]**2))*((mus[2]-np.array(coordList[:,:,2]))**2))).T
        return phi
