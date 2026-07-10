# BrightEyes SPAD RAW converter

This is a stand-alone command-line extractor of the BrightEyes-MCS RAW-acquisition converter. It rebuilds a standard HDF5 acquisition from a preview-less **SPAD FIFO** metadata HDF5 file and the accompanying `_FIFO.raw` and/or `_FIFOAnalog.raw` file.

It has no BrightEyes-MCS GUI or Python-package dependency. PI23-native RAW streams are not supported.

## Install

Use Python 3.10+ and install the three dependencies:

```powershell
python -m pip install -r requirements.txt
```

## Run

```powershell
python convert_raw_acquisition.py C:\data\scan_only_metadata.h5
python convert_raw_acquisition.py C:\data\scan_only_metadata.h5 --output C:\data\scan_converted.h5
```

When `--output` is omitted, `scan_only_metadata.h5` becomes `scan.h5`; other metadata names receive an `_converted.h5` suffix. The resulting filename is printed to standard output and conversion progress is written to standard error.

The input metadata must include `configurationFPGA`, `configurationGUI`, `rawStreamAcquisition`, and either `configurationSpadFCSmanager` or `configurationMcsManager`. RAW files are located from the metadata attributes first, then from their expected sibling filenames.

This utility remains GPLv3, consistent with BrightEyes-MCS.
