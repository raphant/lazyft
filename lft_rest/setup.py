from io import open as io_open
from os import path

from setuptools import setup, find_packages

here = path.abspath(path.dirname(__file__))

with open("requirements.txt") as f:
    dependencies = f.read().splitlines()


def readall(*args):
    with io_open(path.join(here, *args), encoding="utf-8") as fp:
        return fp.read()


setup(
    name='lft_rest',
    version='0.0.17',
    packages=find_packages(),
    license="GPLv3",
    author='Raphael N',
    author_email='rtnanje@gmail.com',
    maintainer="Raphael N",
    # description='Easily get the latest fork of a Github repo',
    entry_points={
        'console_scripts': [],
    },
    install_requires=dependencies,
    platforms=["linux", "linux2"],
)
