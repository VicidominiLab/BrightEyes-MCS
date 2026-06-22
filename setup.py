from pathlib import Path

from setuptools import find_packages, setup


def read_requirements():
    requirements = []
    for line in Path("requirements.txt").read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            requirements.append(line)
    return requirements


setup(
    name="brighteyes-mcs",
    version="0.0.0",
    packages=find_packages(),
    install_requires=read_requirements(),
)
