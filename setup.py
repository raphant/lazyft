from io import open as io_open
from os import path
from pathlib import Path

from setuptools import find_packages, setup

here = path.abspath(path.dirname(__file__))

with open(Path(here, "requirements.txt")) as f:
    dependencies = f.read().splitlines()


def readall(*args):
    with io_open(path.join(here, *args), encoding="utf-8") as fp:
        return fp.read()


setup(
    name="lazyft",
    version="0.1.0",
    packages=find_packages(),
    url="https://github.com/raph92/lazyft",
    license="GPLv3",
    author="Raphael N",
    maintainer="Raphael N",
    description="Easily get the latest fork of a Github repo",
    package_data={"lazyft": ["lazyft/defaults/config.json"]},
    include_package_data=True,
    entry_points={
        "console_scripts": [
            "lft=lazyft.cli.cli:main",
        ],
    },
    install_requires=dependencies,
    platforms=["linux", "linux2"],
)
