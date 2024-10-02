"""
Test the brighteyes_mcs.libs.cython libraries.
"""
import os
import sys
# insert root directory into python module search path
sys.path.insert(1, os.getcwd())


from brighteyes_mcs.libs.cython.fastconverter import (
      convertRawDataToCountsDirect,
      convertRawDataToCountsDirect49,
      convertDataFromAnalogFIFO,
)
from brighteyes_mcs.libs.cython.autocorrelator import Autocorrelator
from brighteyes_mcs.libs.cython.timeBinner import timeBinner


def test():
      print("\n\n\n========================================================================")
      print(" Try to import brighteyes_mcs.libs.cython.fastconverter ... ",
            "OK!" if convertRawDataToCountsDirect.__name__ == 'convertRawDataToCountsDirect' else "FAILED!")
      print(" Try to import brighteyes_mcs.libs.cython.autocorrelator ... ",
            "OK!" if Autocorrelator.__name__ == 'Autocorrelator' else "FAILED!")
      print(" Try to import brighteyes_mcs.libs.cython.timeBinner ... ",
            "OK!" if timeBinner.__name__ == 'timeBinner' else "FAILED!")
      print("========================================================================\n\n\n")

if __name__ == '__main__':
      test()