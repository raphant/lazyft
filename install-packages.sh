#!/usr/bin/env bash

sh update-freqtrade.sh
pip install jupyterlab
pip install -e lazyft_pkg -e indicatormix -e coin_based_strategy -e lft_rest -e ../freqtrade

