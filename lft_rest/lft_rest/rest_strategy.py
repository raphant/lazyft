import logging
import os
import time
from abc import ABCMeta
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta
from json import JSONDecodeError
from pathlib import Path
from threading import Thread
from typing import List, Dict, Optional, Union

import rapidjson
import requests
from freqtrade.optimize.hyperopt_tools import HyperoptTools
from freqtrade.persistence import Trade
from freqtrade.resolvers import StrategyResolver
from freqtrade.strategy import IStrategy
from freqtrade.strategy.interface import SellCheckTuple
from pandas import DataFrame
from tenacity import retry, stop_after_attempt, wait_fixed

from lazyft import paths

logger = logging.getLogger(__name__)
cached_strategies = {}

ip = os.getenv('LFT_REST_IP', 'sage-server1.local')


class BaseRestStrategy(IStrategy, metaclass=ABCMeta):
    _pending_pair_confirmations: set[str] = set()
    _pair_custom_whitelist: dict[str, dict] = {}

    backtest_days = 7
    hyperopt_days = 7
    min_backtest_trades = 2
    min_hyperopt_trades = 7
    hyperopt_epochs = 100
    min_avg_profit = 0.01
    min_win_ratio = 0.40
    request_hyperopt = False
    timeframe_detail = None

    invalid_lock_duration = timedelta(hours=12)
    refresh_interval = timedelta(days=1)
    validation_interval = timedelta(minutes=1)
    disable_duration = timedelta(days=1)
    wait_pending_duration = timedelta(minutes=5)

    # rest_strategy_name = ''
    base_rest_url = f'http://{ip}:8000'
    backtest_url = f'{base_rest_url}/pair/backtest'
    hyperopt_url = f'{base_rest_url}/pair/hyperopt'

    _backtest_list = set()
    _hyperopt_list = set()

    _last_validation_time = None

    def __init__(self, config: dict) -> None:
        super().__init__(config)
        self.last_refresh_date = datetime.now()
        self.hyperopt_worker_running = False
        # if self.is_live_or_dry:
        #     Thread(target=self.hyperopt_worker, daemon=True).start()

    @property
    def is_live_or_dry(self):
        return self.config["runmode"].value in ("live", "dry_run")

    @property
    def rest_strategy_name(self):
        return self.__class__.__mro__[2].__name__

    def bot_loop_start(self, **kwargs) -> None:
        if self.is_live_or_dry:
            trades = Trade.get_open_trades()
            for pair in [t.pair for t in trades]:
                if pair not in self._pair_custom_whitelist and pair not in self._backtest_list:
                    self.init_pair(pair)
                    self._backtest_list.add(pair)
            # if last_refresh_date is older than allotted days, clear pair_custom_whitelist
            if (datetime.now() - self.last_refresh_date) > self.refresh_interval:
                pairs_in_trades = [trade.pair for trade in Trade.get_open_trades()]

                # if pair is not in trades, remove it from pair_custom_whitelist
                for pair in list(self._pair_custom_whitelist.keys()).copy():
                    if pair not in pairs_in_trades:
                        del self._pair_custom_whitelist[pair]
                self.last_refresh_date = datetime.now()

    def analyze(self, pairs: List[str]) -> None:
        # only validate every validation_interval
        try:
            if (
                not self._last_validation_time
                or (datetime.now() - self._last_validation_time).total_seconds()
                < self.validation_interval.total_seconds()
            ):
                self.validate_all_pairs(pairs)
                self._last_validation_time = datetime.now()
        except KeyboardInterrupt:
            # request /shutdown
            requests.get(f'{self.base_rest_url}/shutdown')
        super().analyze(pairs)

    def advise_all_indicators(self, data: Dict[str, DataFrame]) -> Dict[str, DataFrame]:
        try:
            self.validate_all_pairs(list(data.keys()))
        except KeyboardInterrupt:
            # request /shutdown
            requests.get(f'{self.base_rest_url}/shutdown')
        return super().advise_all_indicators(data)

    def validate_all_pairs(self, pairs):
        # logger.info('Validating pairs...')
        for pair in pairs:
            if pair not in self._pair_custom_whitelist:
                self.init_pair(pair)
                self._backtest_list.add(pair)
        # for trade in Trade.get_open_trades():
        #     self.init_pair(trade.pair)
        while any(self._backtest_list) or (not self.is_live_or_dry and any(self._hyperopt_list)):
            if any(self._backtest_list):
                pairs_backtest = self.request_backtest_info(self._backtest_list)
                for pair, info in pairs_backtest.items():
                    self.backtest_validation(pair, info)
            if not self.is_live_or_dry and any(self._hyperopt_list):
                pairs_hyperopt = self.request_hyperopt_info(self._hyperopt_list)
                for pair, info in pairs_hyperopt.items():
                    self.hyperopt_validation(pair, info)
            if any(self._backtest_list) or (not self.is_live_or_dry and any(self._hyperopt_list)):
                time.sleep(10)
        if not self.hyperopt_worker_running and self.is_live_or_dry and any(self._hyperopt_list):
            Thread(target=self.hyperopt_worker, daemon=True).start()

    def confirm_trade_entry(
        self,
        pair: str,
        order_type: str,
        amount: float,
        rate: float,
        time_in_force: str,
        current_time: datetime,
        **kwargs,
    ) -> bool:
        if self._pair_custom_whitelist[pair].get('valid') == 0:
            if self.is_live_or_dry:
                self.lock_pair(pair, until=current_time + self.disable_duration, reason='disabled')
                logger.info(f'{pair} is invalid, disabling pair for {self.disable_duration}')
            return False
        if self._pair_custom_whitelist[pair].get('valid') == -1:
            if self.is_live_or_dry:
                self.lock_pair(
                    pair, until=current_time + self.wait_pending_duration, reason='pending'
                )
                logger.info(f'{pair} is pending, disabling pair for {self.wait_pending_duration}')
            return False
        # if pair has a valid hyperopt, call it's confirm_trade_entry
        if self._pair_custom_whitelist[pair].get('hyperopt') == 1:
            return self._pair_custom_whitelist[pair]['strategy'].confirm_trade_entry(
                pair,
                order_type,
                amount,
                rate,
                time_in_force,
                current_time,
                **kwargs,
            )
        if self._pair_custom_whitelist[pair].get('valid') == 1:
            return True

        return False

    def backtest_validation(self, pair: str, backtest_result) -> int:
        """
        Requests validation from the validation server.

        :param pair: pair to validate
        :param backtest_result: result of backtest
        :return: True if the pair is valid, False otherwise
        """
        if pair in self._pair_custom_whitelist and self._pair_custom_whitelist[pair]['valid'] != -1:
            return 1 if self._pair_custom_whitelist[pair].get('backtest') == 1 else 0
        # request a backtest for pair
        status = backtest_result['status']
        ret = -1
        # check to see if the backtest has been queued, is pending, or is done
        if status == 'queued':
            self._pending_pair_confirmations.add(pair)
        elif status == 'pending':
            # we wait
            pass
        else:
            # we have a result
            self._pair_custom_whitelist[pair]['backtest'] = 1 if status is True else 0
            if pair in self._pending_pair_confirmations:
                self._pending_pair_confirmations.remove(pair)
            if status is False:
                # failure
                if self.request_hyperopt:
                    # we prepare the pair for hyperopt
                    self._hyperopt_list.add(pair)
                    logger.debug(
                        f'{pair} failed backtest validation. Adding to hyperopt list.'
                        f'({len(self._backtest_list) - 1} pairs left to backtest.)'
                    )
                else:
                    # lock pair for self.invalid_lock_duration days
                    self.lock_pair(
                        pair,
                        datetime.now() + self.invalid_lock_duration,
                        'Failed validation',
                    )
                    logger.debug(
                        f'Locking "{pair}" due to failed backtest validation.'
                        f'({len(self._backtest_list) - 1} pairs left to backtest.)'
                    )
            else:
                # success
                logger.info(
                    f'{pair} validated. Info: {backtest_result.get("info")} '
                    f'({len(self._backtest_list) - 1} pairs left to backtest.)'
                )
                self._pair_custom_whitelist[pair]['valid'] = 1
                ret = 1
            self._backtest_list.remove(pair)

        return ret

    def hyperopt_validation(self, pair: str, result: dict[str, dict]) -> int:
        if pair in self._pair_custom_whitelist and self._pair_custom_whitelist[pair]['valid'] != -1:
            return self._pair_custom_whitelist[pair].get('valid') == 1
        # request a backtest for pair
        status = result['status']
        ret = -1
        # check to see if the backtest has been queued, is pending, or is done
        if status == 'queued':
            # init the pair
            self._pending_pair_confirmations.add(pair)
            self._pair_custom_whitelist[pair]['hyperopt_count'] += 1
            # self.init_pair(pair)
            return ret
        elif status == 'pending':
            # we wait
            return ret
        else:
            # we have a result
            ret = 1 if status is True else 0
            self._pair_custom_whitelist[pair]['hyperopt'] = ret
            if pair in self._pending_pair_confirmations:
                self._pending_pair_confirmations.remove(pair)
            if status is False:
                logger.info(
                    f'{pair} failed hyperopt validation {result}. Disabling pair. '
                    f'({len(self._hyperopt_list) - 1} hyperopts left)'
                )
                ret = 0
            else:
                logger.info(
                    f'{pair} hyperopt validated. Info: {result.get("info")} '
                    f'({len(self._hyperopt_list) - 1} hyperopts left)'
                )
                self._pair_custom_whitelist[pair]['params'] = result['info']['params']
                if not self.is_live_or_dry:
                    self.finalize_hyperopt(pair)
                ret = 1
            try:
                self._hyperopt_list.remove(pair)
            except KeyError:
                pass
            return ret

    def get_backtest_status(self, pair) -> dict:
        # intervals = ' '.join(set([tf for pair, tf in self.informative_pairs()]))
        res = requests.get(
            self.backtest_url,
            params={
                'pair': pair,
                'strategy': self.rest_strategy_name,
                'exchange': self.config['exchange']['name'],
                # 'inf_intervals': intervals,
                'min_avg_profit': self.min_avg_profit,
                'min_win_ratio': self.min_win_ratio,
                'days': self.backtest_days,
                'timeframe': self.timeframe,
            },
        )
        logger.debug(f'{pair} {res.json()}')
        return res.json()

    @retry(stop=stop_after_attempt(5), wait=wait_fixed(10))
    def request_backtest_info(self, pairs: set[str]) -> dict[str, dict]:
        """
        Request the status of the pairs.

        :param pairs: pairs to request
        :return: dict of pairs and their status
        """
        for pair in pairs.copy():
            if (
                pair in self._pair_custom_whitelist
                and self._pair_custom_whitelist[pair]['valid'] != -1
            ):
                pairs.remove(pair)
        csv_pairs = ','.join(pairs)
        res = requests.get(
            self.backtest_url,
            params={
                'pairs': csv_pairs,
                'strategy': self.rest_strategy_name,
                'exchange': self.config['exchange']['name'],
                'min_avg_profit': self.min_avg_profit,
                'min_win_ratio': self.min_win_ratio,
                'days': self.backtest_days,
                'timeframe': self.timeframe,
                'timeframe_detail': self.timeframe_detail,
            },
        )
        try:
            return res.json()
        except JSONDecodeError as e:
            raise Exception(f'{res.text} {res.status_code} {res.url}') from e

    @retry(stop=stop_after_attempt(5), wait=wait_fixed(10))
    def request_hyperopt_info(self, pairs: set[str]) -> dict[str, dict]:
        """
        Request the hyperopt results of the pairs.

        :param pairs: pairs to request
        :return: dict of pairs and their status
        """
        for pair in pairs.copy():
            assert (
                pair in self._pair_custom_whitelist
                and self._pair_custom_whitelist[pair]['valid'] == -1
            ), f'{pair} does should not be in hyperopt list'

        csv_pairs = ','.join(pairs)
        res = requests.get(
            self.hyperopt_url,
            params={
                'pairs': csv_pairs,
                'strategy': self.rest_strategy_name,
                'exchange': self.config['exchange']['name'],
                'min_avg_profit': self.min_avg_profit,
                'days': self.hyperopt_days,
                'timeframe': self.timeframe,
                'epochs': self.hyperopt_epochs,
                'min_trades': self.min_hyperopt_trades,
                'timeframe_detail': self.timeframe_detail,
            },
        )
        return res.json()

    def init_pair(self, pair):
        self._pair_custom_whitelist[pair] = {
            'valid': -1,
            'backtest': -1,
            'hyperopt': -1,
            'strategy': None,
            'params': {},
            'hyperopt_count': 0,
        }

    def hyperopt_worker(self):
        self.hyperopt_worker_running = True
        while any(self._hyperopt_list):
            results = self.request_hyperopt_info(self._hyperopt_list)
            for pair, info in results.items():
                try:
                    valid = self.hyperopt_validation(pair, info)
                    if valid == 1:
                        self.finalize_hyperopt(pair)
                except Exception as e:
                    logger.exception(
                        f'Error validating {pair}'
                        f' Disabling for {self.disable_duration} minutes',
                        e,
                    )
                    self.lock_pair(
                        pair,
                        until=datetime.utcnow() + self.disable_duration,
                        reason='hyperopt validation error',
                    )
            time.sleep(self.validation_interval.total_seconds())
        self.hyperopt_worker_running = False

    def finalize_hyperopt(self, pair):
        logger.info(f'Finalizing hyperopt for {pair}')
        strategy = DynamicStrategy(
            strategy_name=self.rest_strategy_name,
            pair=pair,
            params=self._pair_custom_whitelist[pair]['params'],
            config=self.config,
        )
        self.load_strategy(strategy)
        self._pair_custom_whitelist[pair]['valid'] = 1

    def load_strategy(
        self,
        dynamic_strategy: 'DynamicStrategy',
    ) -> IStrategy:
        #
        if dynamic_strategy.joined_name in cached_strategies:
            logger.debug(f"Using cached strategy {dynamic_strategy.joined_name}")
            strategy = cached_strategies[dynamic_strategy.joined_name]
            strategy.dp = self.dp
            strategy.wallets = self.wallets
            return strategy
        dynamic_strategy.copy_strategy()
        dynamic_strategy.copy_params()
        strategy_dir = dynamic_strategy.tmp_path
        config = self.config
        config['strategy_path'] = strategy_dir
        config['user_data_dir'] = strategy_dir
        config['data_dir'] = paths.USER_DATA_DIR / 'data'
        config = config.copy()
        config["strategy"] = dynamic_strategy.strategy_name
        # for k in keys_to_delete:
        #     try:
        #         del config[k]
        #     except KeyError:
        #         pass
        strategy = StrategyResolver.load_strategy(config)
        strategy.dp = self.dp
        self.startup_candle_count = max(self.startup_candle_count, strategy.startup_candle_count)

        strategy.dp = self.dp
        strategy.wallets = self.wallets
        cached_strategies[dynamic_strategy.joined_name] = strategy
        self._pair_custom_whitelist[dynamic_strategy.pair]['strategy'] = strategy

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        pair = metadata['pair']
        if self._pair_custom_whitelist[pair].get('strategy') is None:
            return super().populate_indicators(dataframe, metadata)
        return self._pair_custom_whitelist[pair]['strategy'].populate_indicators(
            dataframe, metadata
        )

    def populate_buy_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        pair = metadata['pair']
        if self._pair_custom_whitelist[pair].get('strategy') is None:
            return super().populate_buy_trend(dataframe, metadata)
        return self._pair_custom_whitelist[pair]['strategy'].populate_buy_trend(dataframe, metadata)

    def populate_sell_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        pair = metadata['pair']
        if self._pair_custom_whitelist[pair].get('strategy') is None:
            return super().populate_sell_trend(dataframe, metadata)
        return self._pair_custom_whitelist[pair]['strategy'].populate_sell_trend(
            dataframe, metadata
        )

    def should_sell(
        self,
        trade: Trade,
        rate: float,
        date: datetime,
        buy: bool,
        sell: bool,
        low: float = None,
        high: float = None,
        force_stoploss: float = 0,
    ) -> SellCheckTuple:
        if (
            trade.pair in self._pair_custom_whitelist
            and self._pair_custom_whitelist[trade.pair]['hyperopt'] == 1
        ):
            return self._pair_custom_whitelist[trade.pair]['strategy'].should_sell(
                trade, rate, date, buy, sell, low, high, force_stoploss
            )
        return super().should_sell(trade, rate, date, buy, sell, low, high, force_stoploss)

    def custom_stoploss(
        self,
        pair: str,
        *args,
        **kwargs,
    ) -> float:
        if self._pair_custom_whitelist[pair].get('hyperopt') == 1:
            return self._pair_custom_whitelist[pair]['strategy'].custom_stoploss(
                pair, *args, **kwargs
            )
        return super().custom_stoploss(pair, *args, **kwargs)

    def confirm_trade_exit(
        self,
        pair: str,
        trade: Trade,
        order_type: str,
        amount: float,
        rate: float,
        time_in_force: str,
        sell_reason: str,
        current_time: datetime,
        **kwargs,
    ) -> bool:
        if self._pair_custom_whitelist[pair].get('hyperopt') == 1:
            return self._pair_custom_whitelist[pair]['strategy'].confirm_trade_exit(
                pair,
                trade,
                order_type,
                amount,
                rate,
                time_in_force,
                sell_reason,
                current_time,
                **kwargs,
            )
        return super().confirm_trade_exit(
            pair,
            trade,
            order_type,
            amount,
            rate,
            time_in_force,
            sell_reason,
            current_time,
            **kwargs,
        )

    def custom_sell(
        self,
        pair: str,
        *args,
        **kwargs,
    ) -> Optional[Union[str, bool]]:
        if self._pair_custom_whitelist[pair].get('hyperopt') == 1:
            return self._pair_custom_whitelist[pair]['strategy'].custom_sell(pair, *args, **kwargs)
        return super().custom_sell(pair, *args, **kwargs)


@dataclass(frozen=True)
class DynamicStrategy:
    strategy_name: str
    pair: str
    params: dict
    config: dict

    @property
    def joined_name(self):
        return f"{self.strategy_name}-{self.pair.replace('/', '_')}"

    @property
    def tmp_path(self):
        return Path(f"/tmp/{self.joined_name}")

    def create_tmp_dir(self):
        """create a temporary directory for the strategy using the joined name"""
        # mkdir the directory
        self.tmp_path.mkdir(exist_ok=True)

    def copy_params(self):
        param_filename = self.strategy_file_name.with_suffix('.json')

        # copy the params to the temporary directory as a json file
        path = self.tmp_path / f"{param_filename}"
        if not self.params:
            logger.info(f"No params for strategy {self.strategy_name}")
            # delete the file if it exists
            path.unlink(missing_ok=True)
            return
        logger.info(f"writing params to {param_filename}")
        path.write_text(rapidjson.dumps(self.params))

    def copy_strategy(self):
        """copy the strategy to the temporary directory"""
        strategy_path = paths.STRATEGY_DIR / self.strategy_file_name
        self.create_tmp_dir()
        Path(self.tmp_path, f"{strategy_path.name}").write_text(strategy_path.read_text())

    @property
    def strategy_file_name(self):
        return HyperoptTools.get_strategy_filename(self.config, self.strategy_name)
