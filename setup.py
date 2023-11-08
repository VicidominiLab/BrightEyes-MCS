from setuptools import find_packages, setup
from setuptools.extension import Extension
from Cython.Build import cythonize
from Cython.Distutils import build_ext
import numpy as np


# COMMAND TO COMPILE:
# with Visual Studio Installed
# python setup.py build_ext --inplace

# with Msys2 with pacman -S mingw-w64-ucrt-x86_64-gcc
# add to path the msys2 path
#
# $env:Path += ';C:\msys64\usr\bin'
# $env:Path += ';C:\msys64\ucrt64\bin'
# python setup.py build_ext --inplace --compiler=mingw32 -DMS_WIN64

setup(
    ext_modules=cythonize(
        [
            Extension(
                "brighteyes_mcs.libs.cython.fastconverter",
                ["brighteyes_mcs/libs/cython/fastconverter.pyx"],
            ),
            Extension(
                "brighteyes_mcs.libs.cython.autocorrelator",
                ["brighteyes_mcs/libs/cython/autocorrelator.pyx"],
            ),
            Extension(
                "brighteyes_mcs.libs.cython.timeBinner",
                ["brighteyes_mcs/libs/cython/timeBinner.pyx"],
            ),
        ],
        language_level=3,
        annotate=True,
    ),
    include_dirs=[np.get_include()],
    packages=find_packages(),
)
