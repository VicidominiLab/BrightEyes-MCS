
import os
import sys
# insert root directory into python module search path
sys.path.insert(1, os.getcwd())

from brighteyes_mcs.libs.cython import fastconverter as fc

print("\n\n\n========================================================================")
print(" Try to import brighteyes_mcs.libs.cython.fastconverter")
print(" Result: ",
      "OK INSTALLED" if fc.convertRawDataToCountsDirect.__name__ == 'convertRawDataToCountsDirect' else "NOT INSTALLED!")
print("========================================================================\n\n\n")

def test():
      a=fc
      pass