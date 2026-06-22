"""Test the compiled brighteyes_mcs_cylibs package."""
import os
import sys

# Insert root directory into python module search path.
sys.path.insert(1, os.getcwd())


from brighteyes_mcs_cylibs.fastconverter import (
      convertRawDataToCountsDirect,
      convertRawDataToCountsDirect49,
      convertDataFromAnalogFIFO,
)
from brighteyes_mcs_cylibs.autocorrelator import Autocorrelator
from brighteyes_mcs_cylibs.timeBinner import timeBinner


def test():
      print("\n\n\n========================================================================")
      print(" Try to import brighteyes_mcs_cylibs.fastconverter ... ",
            "OK!" if convertRawDataToCountsDirect.__name__ == 'convertRawDataToCountsDirect' else "FAILED!")
      print(" Try to import brighteyes_mcs_cylibs.autocorrelator ... ",
            "OK!" if Autocorrelator.__name__ == 'Autocorrelator' else "FAILED!")
      print(" Try to import brighteyes_mcs_cylibs.timeBinner ... ",
            "OK!" if timeBinner.__name__ == 'timeBinner' else "FAILED!")
      print("========================================================================\n\n\n")


if __name__ == '__main__':
      test()
