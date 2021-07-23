import re
from os import path
from setuptools import setup
from io import open as io_open

here = path.abspath(path.dirname(__file__))

with open("requirements.txt") as f:
    dependencies = f.read().splitlines()


def readall(*args):
    with io_open(path.join(here, *args), encoding="utf-8") as fp:
        return fp.read()


setup(
    name='lazyft',
    version='0.0.1',
    packages=['lazyft'],
    # url='https://github.com/raph92/fenparser',
    license="GPLv3",
    author='Raphael N',
    author_email='rtnanje@gmail.com',
    maintainer="Raphael N",
    description='Easily get the latest fork of a Github repo',
    entry_points={
        'console_scripts': [
            'study=easyft.main:study',
            'manage=manage:core',
            'manage2=easyft.manage2:cli',
            'backtest=easyft.main:backtest_cli',
        ],
    },
    install_requires=dependencies,
    platforms=["linux", "linux2"],
)
