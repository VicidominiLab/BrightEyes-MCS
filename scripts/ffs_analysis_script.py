from spad_ffs_eli.FCS.FCS2Corr import (
    FCSLoadAndCorrSplit,
    FCSCrossCenterAv,
    FCSSpatialCorrAv,
)
from spad_ffs_eli.FCS.FCSfit import FCSfit, G2globalFitStruct, FCSfitDualFocus
from spad_ffs_eli.FCS.plotAiry import plotAiry
import numpy as np
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import axes3d
from spad_ffs_eli.Tools.fitGauss2D import fitGauss2D
from spad_ffs_eli.Tools.findNearest import findNearest
from spad_ffs_eli.FCS.FCSLoadG import FCSLoadG
from spad_ffs_eli.FCS.binFile2Data import binFile2Data
from spad_ffs_eli.FCS.plotIntensityTraces import plotIntensityTraces
from spad_ffs_eli.Tools.StokesEinstein import StokesEinstein
import h5py
from spad_ffs_eli.Tools.np2hdf5 import hdf5Read

plt.style.use("default")
fname = filename

listOfCorrelations = ["central", "sum3", "sum5"]
chunksize = 10  # s
corRes = 10  # 'resolution' of the correlation function: the higher this number, the more lag times are used

[G, data] = FCSLoadAndCorrSplit(
    fname, listOfCorrelations, corRes, chunksize, timeTrace=True
)

# plot time trace
Nchunks = int((len(G.__dict__.keys()) - 4) / 3)
dt = Nchunks * chunksize / len(data)
time = np.arange(0, Nchunks * chunksize, dt)
pcr = data / dt / 1000
plt.figure()
for i in range(25):
    plt.plot(time, pcr[:, i])
plt.ylabel("Photon count rate (kHz)")
plt.xlim([0, time[-1]])
plt.ylim([0, np.max(pcr) * 1.05])
dummy = plt.xlabel("Time (s)")

# plot individiual chunks
fig = plt.figure(figsize=(15, 10))
for i in range(Nchunks):
    # central
    Gtemp = getattr(G, "central_chunk" + str(i))
    col = np.mod(i, 5)
    row = int(np.floor(i / 5))
    ax = fig.add_subplot(2, 5, i + 1)
    ax.plot(Gtemp[1:, 0], Gtemp[1:, 1])
    # sum3
    Gtemp = getattr(G, "sum3_chunk" + str(i))
    ax.plot(Gtemp[1:, 0], Gtemp[1:, 1])
    # sum5
    Gtemp = getattr(G, "sum5_chunk" + str(i))
    ax.plot(Gtemp[1:, 0], Gtemp[1:, 1])
    plt.title("Chunk " + str(i))
    plt.xscale("log")

goodChunks = list(range(Nchunks))

G.central_average *= 0
G.sum3_average *= 0
G.sum5_average *= 0

for chunk in goodChunks:
    G.central_average += getattr(G, "central_chunk" + str(chunk))
    G.sum3_average += getattr(G, "sum3_chunk" + str(chunk))
    G.sum5_average += getattr(G, "sum5_chunk" + str(chunk))

G.central_average /= len(goodChunks)
G.sum3_average /= len(goodChunks)
G.sum5_average /= len(goodChunks)


plt.figure()
plt.plot(G.central_average[1:, 0], G.central_average[1:, 1])
plt.plot(G.sum3_average[1:, 0], G.sum3_average[1:, 1])
plt.plot(G.sum5_average[1:, 0], G.sum5_average[1:, 1])
plt.xscale("log")
plt.xlabel("Tau (s)")
dummy = plt.ylabel("G")


# fit correlations
start = 1  # start index to fit the data, set to 15-30 to remove the afterpulse component at short lag times
fitarray = np.array([1, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0])  # parameters to fit
minBound = np.array(
    [0, 5e-2, 5e-2, 0, 0, 0, 0, 0, 0, 0, 0]
)  # minimum values for the parameters
maxBound = np.array(
    [1e6, 10, 10, 1, 1e6, 1e6, 1e6, 1e6, 1e6, 1e6, 1e6]
)  # maximum values for the parameters

# ---------- central element ----------
SF = 4.5  # shape factor, i.e. z0/w0 with z0 the height of the PSF and w0 the width (1/e^2 radius of the intensity)
startValues = np.array(
    [70, 0.4, 0.8e-10, 1, 1, 0, 1e-6, SF, 0, 0, 1.05]
)  # start values for the fit
plotInfo = "central"  # used for the color of the output plot
Gexp = G.central_average[:, 1]
tau = G.central_average[:, 0]
fitresult1 = FCSfit(
    Gexp[start:],
    tau[start:],
    "fitfun2C",
    fitarray,
    startValues,
    minBound,
    maxBound,
    plotInfo,
    0,
    0,
)

# ---------- sum3x3 ----------
SF = 4.1
startValues = np.array(
    [70, 0.4, 0.8e-10, 1, 1, 0, 1e-6, SF, 0, 0, 1.05]
)  # start values for the fit
plotInfo = "sum3"
Gexp = G.sum3_average[:, 1]
tau = G.sum3_average[:, 0]
fitresult3 = FCSfit(
    Gexp[start:],
    tau[start:],
    "fitfun2C",
    fitarray,
    startValues,
    minBound,
    maxBound,
    plotInfo,
    0,
    0,
)

# ---------- sum5x5 ----------
SF = 4.1
startValues = np.array(
    [70, 0.4, 0.8e-10, 1, 1, 0, 1e-6, SF, 0, 0, 1.05]
)  # start values for the fit
plotInfo = "sum5"
Gexp = G.sum5_average[:, 1]
tau = G.sum5_average[:, 0]
fitresult5 = FCSfit(
    Gexp[start:],
    tau[start:],
    "fitfun2C",
    fitarray,
    startValues,
    minBound,
    maxBound,
    plotInfo,
    0,
    0,
)


w0 = np.array([213e-9, 251e-9, 289e-9])  # from circFCS 2021-11-25
# w0 = np.array([230e-9,280e-9,350e-9])
tau = 1e-3 * np.array([fitresult1.x[1], fitresult3.x[1], fitresult5.x[1]])
D = w0**2 / 4 / tau

for i in range(3):
    d = D[i]
    print("D = " + "{:.3}".format(1e12 * d) + "µm^2/s")
    print("Particle diameter: " + "{:.3}".format(1e9 * StokesEinstein(d)) + " nm \n")

fitresult = np.polyfit(w0**2, tau, 1)
a = fitresult[0]
b = fitresult[1]


w02 = 1e12 * w0**2
taums = 1e3 * tau
taumax = np.max(taums) * 1.1
w02max = np.max(w02) * 1.1
plt.figure()
for i in range(3):
    plt.scatter(w02[i], taums[i])
plt.plot(
    [0, w02max], [1000 * b, 1000 * a * w02max * 1e-12 + 1000 * b], "-k", linewidth=0.2
)
plt.xlim([0, w02max])
plt.ylim([0, taumax])
plt.title("Diffusion law")
plt.xlabel("w0^2 (µm^2)")
dummy = plt.ylabel("tau (ms)")

# diffusion coefficient from slope
print("D = " + "{:.3}".format(1e12 * 1 / 4 / a) + " µm^2/s")
# diameter from Stokes-Einstein
print("Diameter = " + "{:.3}".format(1e9 * StokesEinstein(1 / 4 / a)) + " nm")
