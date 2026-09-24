# BrightEyes-MCS documentation

These guides are maintained with the code. Use the documentation from the same
checkout or release as your application. The Wiki is an entry point, not a second
copy of the installation or developer instructions.

## User guides

- [Installation and first launch](../README.md)
- [Statistics and ETA](statistics.md)
- [PI23 time-tag recording](pi23-timetagging.md)
- [Configuration, runtime paths, and RAW conversion](current-architecture.md)

## Developer guides

- [Contributing, tests, and Qt UI generation](../CONTRIBUTING.md)
- [Current architecture and repository map](current-architecture.md)
- [Refactoring boundaries and compatibility](refactoring-architecture.md)
- [Plug-in API](../brighteyes_mcs/plugins/README.md)
- [Build and release procedure (publishing disabled)](pypi-release.md)
- [Wiki landing-page draft](wiki-home.md)

## Technical references

- [HDF5 schema 0.0.1](h5_mcs_scheme_v0_0_1.md)
- [Low-level firmware registers](BrightEyes-MCSLL-registers.md)
- [Lifetime estimation](lifetime_estimation_explanation.txt)

The architecture guide contains the maintained software diagram. The images in
`docs/img/` are historical illustrations; in particular, the older Draw.io diagram
shows the former `main.py` entry point. Current startup uses
`python -m brighteyes_mcs`. Do not use those images as an API or package map.

## Keeping these guides current

Update the relevant guide with each behavior change. Record firmware applicability
on hardware references and keep historical format information when readers still
need it. Run `python scripts/check_docs.py` before submitting documentation edits.
External links can be checked separately with `python scripts/check_docs.py --external`;
network failures are reported but do not block local validation.
