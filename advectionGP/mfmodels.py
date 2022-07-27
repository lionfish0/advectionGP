from advectionGP.models import AdjointAdvectionDiffusionModel
import numpy as np

class MeshFreeAdjointAdvectionDiffusionModel(AdjointAdvectionDiffusionModel):
    def computeAdjoint(self,H):
        assert False, "This isn't used in this child class, as we compute the Phi array in a single step, see computeModelRegressors()."
        
    def computeModelRegressors(self,Nparticles=10):
        """
        Computes the regressor matrix X, using the sensor model and getPhi from the kernel.
        X here is used to infer the distribution of z (and hence the source).
        X is [features x observations]
        
        Nparticles = number of particles PER OBSERVATION.
        
        uses just dt, Nt and boundary[0][0].
        """
        dt,dx,dy,dx2,dy2,Nt,Nx,Ny = self.getGridStepSize() #only bit we use is dt and Nt
        
        scale = Nparticles / dt

        particles = []
        N_obs = len(self.sensormodel.obsLocs)
        
        #Place particles at the observations...
        print("Initialising particles...")
        for obsi in range(N_obs):
            print("%d/%d \r" % (obsi,N_obs),end="")
            locA = self.sensormodel.obsLocs[obsi,[0,2,3]]
            locB = self.sensormodel.obsLocs[obsi,[1,2,3]]
            newparticles = np.repeat(locA[None,:],Nparticles,0).astype(float)
            newparticles[:,0]+=np.random.rand(len(newparticles))*(locB[0]-locA[0])
            particles.append(newparticles)
        particles = np.array(particles)

        X = np.zeros([self.N_feat,N_obs])
        print("Diffusing particles...")
        for nit in range(Nt): 
            print("%d/%d \r" % (nit,Nt),end="")
            wind = self.windmodel.getwind(particles[:,:,1:])*dt #how much each particle moves due to wind [backwards]
            particles[:,:,1:]+=np.random.randn(particles.shape[0],particles.shape[1],2)*np.sqrt(2*dt*self.k_0) - wind
            particles[:,:,0]-=dt

            keep = particles[:,0,0]>self.boundary[0][0] #could extend to be within grid space
            X[:,keep] += np.sum(self.kernel.getPhiValues(particles),axis=(1))[:,keep]
            if np.sum(keep)==0: 
                break
        X = np.array(X)/scale
        self.X = X
        self.particles = particles
        return X
        
    def computeConcentration(self,meanZ,covZ,coords=None,Nsamps=10,Nparticles=30):
        """
        meanZ,covZ = mean and covariance of Z.
        Compute the concentration using the particle approach.
        coords = coordinates to use (default is to use the grid specified in the model
        Nsamps = number of samples to take of Z. If you use just one, it uses the mean.
        Nparticles = number of particles to use
        
        returns mean and variance
        """
        if coords is not None:
            self.coords = coords
            
        dt,dx,dy,dx2,dy2,Nt,Nx,Ny = self.getGridStepSize() #only bit we use is dt and Nt

        #meanZ, covZ = self.computeZDistribution(Y) # Infers z vector mean and covariance using regressor matrix
        sourceInfer = self.computeSourceFromPhi(meanZ) # Generates estimated source using mean of the inferred distribution
        if Nsamps==1:
            Zs = meanZ[None,:]
        else:
            Zs = np.random.multivariate_normal(meanZ,covZ,Nsamps)

        #Place particles at the places of interest...
        print("Initialising particles...")
        particles = self.coords.transpose([1,2,3,0]).copy()
        particles = particles[None,:].repeat(Nparticles,axis=0)

        conc = np.zeros((Nsamps,)+particles.shape[:4]) #SAMPLING FROM Z
        print("Diffusing particles...")
        for nit in range(Nt):
            print("%d/%d \r" % (nit,Nt),end="")
            wind = self.windmodel.getwind(particles[:,:,:,:,1:])*dt #how much each particle moves due to wind [backwards]
            particles[:,:,:,:,1:]+=np.random.randn(particles.shape[0],particles.shape[1],particles.shape[2],particles.shape[3],2)*np.sqrt(2*dt*self.k_0) - wind
            particles[:,:,:,:,0]-=dt

            keep = particles[:,:,:,:,0]>self.boundary[0][0] #could extend to be within grid space
            
            sources = np.array([self.computeSourceFromPhi(z, particles.transpose([4,0,1,2,3])) for z in Zs])
            conc[:,keep] += sources[:,keep] #np.sum(sources)#[:,keep]
            if np.sum(keep)==0: 
                break
            
        conc = np.array(conc) #/scale
        conc = np.mean(conc,axis=1)*dt #average over particles
        return np.mean(conc,axis=0),np.var(conc,axis=0)

