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
    name='indicatormix',
    version='0.1.0',
    packages=find_packages(),
    # url='https://github.com/raph92/fenparser',
    license="GPLv3",
    author='Raphael N',
    author_email='rtnanje@gmail.com',
    maintainer="Raphael N",
    description='',
    entry_points={
        'console_scripts': [],
    },
    install_requires=dependencies,
    platforms=["linux", "linux2"],
)
