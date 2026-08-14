"""
Script that can be launched directly on the ScriptLauncher.
This script can be used with by using a grid sample
It calculates the distances between the grid cell,
and it is useful to perform calculate the calibration factor
of the positioner (galvo mirror)
"""

import numpy as np
import matplotlib.pyplot as plt
import numpy.fft as ft
import h5py
import os

if filename is None:
    raise ("filename missing")

data = h5py.File(filename)


plt.close("all")

# %%


calib_x = data["configurationGUI"].attrs["calib_x"]  # um/V
calib_y = data["configurationGUI"].attrs["calib_y"]  # um/V


range_x = data["configurationGUI"].attrs["range_x"]
range_y = data["configurationGUI"].attrs["range_y"]


nx = data["configurationGUI"].attrs["nx"]
ny = data["configurationGUI"].attrs["ny"]


pxsize_x = range_x / nx
pxsize_y = range_y / ny


calib_Vx = calib_x / pxsize_x  # px/V
calib_Vy = calib_y / pxsize_y  # px/V

img = np.sum(data["data"], axis=(0, 1, 4, 5))

# %%

plt.figure()
plt.imshow(img)

pad_width = 0  # 2000
img_pad = np.pad(img, pad_width)

f_ax = ft.fftshift(ft.fftfreq(pad_width + nx))

imgF = ft.fftshift(ft.fft2(img_pad))

F = np.abs(imgF)

idx_max = np.unravel_index(np.argmax(F), np.array(F).shape)

# %%

from skimage.feature import peak_local_max

peak_idx = peak_local_max(F, threshold_rel=0.2)

fig = plt.figure()
plt.xlim(950, 1050)
plt.ylim(950, 1050)
plt.imshow(F)
plt.plot(peak_idx[:, 0], peak_idx[:, 1], "r.")

rel_peak = peak_idx - idx_max

peak_x = np.abs(rel_peak[:, 0])

peak_y = np.abs(rel_peak[:, 1])

dfx = 1 / nx

dfy = 1 / ny

X = 1 / (np.min(peak_x[np.nonzero(peak_x)]) * dfx)

Y = 1 / (np.min(peak_y[np.nonzero(peak_y)]) * dfy)

# %%

T = 10  # um

px_x = T / X

px_y = T / Y


c_x = calib_Vx * px_x
c_y = calib_Vy * px_y

print("c_x", c_x)
print("c_y", c_y)
