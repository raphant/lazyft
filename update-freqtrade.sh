#!/usr/bin/env bash
cd ../freqtrade && git pull && cd ../ftworkdir && pip install -r ../freqtrade/requirements-hyperopt.txt -U \
  -r ../freqtrade/requirements-plot.txt -U
