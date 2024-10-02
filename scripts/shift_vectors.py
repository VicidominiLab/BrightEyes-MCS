"""
Script that can be launched directly on the ScriptLauncher.
This script calculate and shows the shift vector of the last ascquired image.
"""

import brighteyes_ism.dataio.mcs as mcs
import brighteyes_ism.analysis.APR_lib as apr
import brighteyes_ism.analysis.Tools_lib as tools
import brighteyes_ism.simulation.PSF_sim as psf
import numpy as np
import os

# %%
#
# path = r'C:\Users\MYUSER\myfolder'
#
# file = r'data-16-12-2022-18-22-36.h5'
#
# fullpath = os.path.join(path, file)
print("Calculating shift-vector ", filename)
data, meta = mcs.load(filename)

# %%

dset = data[0, 0]  # np.squeeze(data)
dset = dset.sum(axis=-2)

# %%
usf = 50
ref = dset.shape[-1] // 2
sv = apr.ShiftVectors(dset, usf, ref, pxsize=meta.dx)[0]

# %%

fingerprint = psf.Fingerprint(dset)

try:
    main_window.script_plot_shiftvector(sv)
except:
    tools.PlotShiftVectors(sv, color=fingerprint)


time = int(meta.pxdwelltime)
clabel = f"Counts /  {time} $\mu s$"

try:
    main_window.script_plot_fingerprint(fingerprint)
except:
    tools.ShowFingerprint(dset, colorbar=True, clabel=clabel)
