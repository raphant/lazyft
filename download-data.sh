#!/usr/bin/env bash
source /home/sage/ftworkdir/.direnv/python-3.10.1/bin/activate
freqtrade download-data -c configs/kucoin_refresh_nov4.json -t 1m --days 7
freqtrade download-data -c configs/binance_refresh_december.json -t 1m --days 7
