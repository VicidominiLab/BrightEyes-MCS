# Publishing BrightEyes-MCS to PyPI

The repository uses a root package layout: the import package is
`brighteyes_mcs/`, and `pyproject.toml` explicitly limits setuptools discovery
to that package tree. A move to `src/brighteyes_mcs/` is not required for
publication.

The Python package contains application code, default configuration, Qt forms,
the About page, and application icons. FPGA `.lvbitx` firmware, user or lab
configuration, notebooks, logs, installers, and development data are not part
of the distributions.

BrightEyes-MCS intentionally declares no console or GUI script entry point.
This prevents pip from generating `brighteyes-mcs.exe` on Windows. Users launch
the installed package with `python -m brighteyes_mcs`; the optional application
Desktop shortcut targets the selected environment's `pythonw.exe` with those
module arguments. A second optional shortcut opens `cmd.exe` and activates the
same Python environment; it does not install an executable or entry point.

## One-time setup

1. Confirm that Istituto Italiano di Tecnologia and the contributors authorize
   distribution under `GPL-3.0-or-later`.
2. Create a protected GitHub environment named `pypi`. Requiring a maintainer's
   approval before deployment is recommended.
3. In the PyPI account that will own the project, create a pending Trusted
   Publisher with:

   - PyPI project: `brighteyes-mcs`
   - GitHub owner: `VicidominiLab`
   - Repository: `BrightEyes-MCS`
   - Workflow: `release.yml`
   - Environment: `pypi`

The workflow uses OpenID Connect and does not require a stored PyPI API token.

## Preparing a release

Update `brighteyes_mcs.__version__`, add release notes, and run from a clean
checkout:

```powershell
python -m pip install -e ".[dev]"
python -m pytest -q
python -m unittest test.test_channel_delay_skew_plugin -v
python -m build
python -m twine check dist/*
python scripts/check_distribution.py dist
python -m brighteyes_mcs --no-first-run
```

For a TestPyPI rehearsal, upload the same artifacts using a TestPyPI account
and install them while allowing production PyPI to supply dependencies:

```powershell
python -m twine upload --repository testpypi dist/*
python -m pip install --index-url https://test.pypi.org/simple/ `
  --extra-index-url https://pypi.org/simple/ brighteyes-mcs==1.1.1
```

TestPyPI and PyPI do not permit replacing a file with the same project name and
version. Increment the version before retrying an upload whose files were
already accepted.

## Publishing

Commit and merge the release changes, then create and push a version tag that
exactly matches `brighteyes_mcs.__version__`:

```powershell
git tag -a v1.1.1 -m "BrightEyes-MCS 1.1.1"
git push origin v1.1.1
```

The `Publish Python package` workflow builds from the tag, verifies the version,
checks metadata and archive contents, and publishes through the configured
PyPI Trusted Publisher. Never build a release from a working tree containing
uncommitted changes.
