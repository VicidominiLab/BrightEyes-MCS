from setuptools import find_packages, setup
from distutils.extension import Extension
from distutils.core import setup
from Cython.Build import cythonize
from Cython.Distutils import build_ext
import numpy as np

# COMMAND TO COMPILE: python setup.py build_ext --inplace

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
