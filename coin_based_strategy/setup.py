from io import open as io_open
from os import path

from setuptools import setup

here = path.abspath(path.dirname(__file__))

with open("requirements.txt") as f:
    dependencies = f.read().splitlines()


def readall(*args):
    with io_open(path.join(here, *args), encoding="utf-8") as fp:
        return fp.read()


setup(
    name='cbs',
    version='0.0.1',
    packages=['cbs'],
    # url='https://github.com/raph92/fenparser',
    license="GPLv3",
    author='Raphael N',
    author_email='rtnanje@gmail.com',
    maintainer="Raphael N",
    description='A library for FreqTrade that allows you to use multiple strategies based on the '
    'pair.',
    entry_points={
        'console_scripts': [],
    },
    install_requires=dependencies,
    platforms=["linux", "linux2"],
)
