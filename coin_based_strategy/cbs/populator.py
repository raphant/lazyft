from typing import Optional

from freqtrade.data.dataprovider import DataProvider
from loguru import logger
from pandas import DataFrame
from lazyft import paths
from cbs import CbsConfiguration, Strategy
from cbs.mapper import Mapper
from freqtrade.configuration import Configuration
from freqtrade.resolvers import StrategyResolver
from freqtrade.strategy import IStrategy

keys_to_delete = [
    "minimal_roi",
    "stoploss",
    "ignore_roi_if_buy_signal",
    'trailing_stop',
    'trailing_stop_positive_offset',
    'trailing_only_offset_is_reached',
    'use_custom_stoploss',
    'use_sell_signal',
]


class Populator:
    _cached_strategies: dict[str, IStrategy] = {}

    @classmethod
    def prep(cls, parent_strategy: IStrategy, pair: str, mapper: Mapper):
        logger.info(f"Prepping strategies for {pair}")
        strategies = mapper.get_strategies(pair)
        for strategy in strategies:
            Populator._load_strategy(strategy, parent_strategy)

    @staticmethod
    def load_strategies(mapper: Mapper, pair: str):
        strategies = mapper.get_strategies(pair)
        if not any(strategies):
            logger.info(f"No strategies found for {pair}")
            return
        return [Populator._load_strategy(strategy) for strategy in strategies]

    @staticmethod
    def _load_strategy(
        cbs_strategy: Strategy,
        parent_strategy: IStrategy = None,
    ) -> IStrategy:
        #
        if cbs_strategy.joined_name in Populator._cached_strategies:
            logger.debug(f"Using cached strategy {cbs_strategy.joined_name}")
            return Populator._cached_strategies[cbs_strategy.joined_name]
        cbs_strategy.copy_strategy()
        cbs_strategy.copy_params()
        strategy_dir = cbs_strategy.tmp_path
        config = parent_strategy.config
        config['strategy_path'] = strategy_dir
        config['user_data_dir'] = strategy_dir
        config['data_dir'] = paths.USER_DATA_DIR / 'data'
        config = config.copy()
        config["strategy"] = cbs_strategy.strategy_name
        for k in keys_to_delete:
            try:
                del config[k]
            except KeyError:
                pass
        strategy = StrategyResolver.load_strategy(config)
        strategy.dp = parent_strategy.dp
        parent_strategy.startup_candle_count = max(
            parent_strategy.startup_candle_count, strategy.startup_candle_count
        )

        strategy.dp = parent_strategy.dp
        strategy.wallets = parent_strategy.wallets
        Populator._cached_strategies[cbs_strategy.joined_name] = strategy
        return strategy

    @classmethod
    def populate_indicators(
        cls,
        dataframe: DataFrame,
        pair: str,
        mapper: Mapper,
    ):
        strategies = mapper.get_strategies(pair)
        if not any(strategies):
            logger.info(f"No strategies found for {pair}")
            return dataframe
        dataframe = Populator._populate_multiple(None, strategies, dataframe, pair)
        logger.info(
            f"Populated indicators for {pair} with {[s.strategy_name for s in strategies]}"
        )
        return dataframe

    @classmethod
    def _populate_multiple(
        cls,
        parent_strategy: Optional[IStrategy],
        strategies: list[Strategy],
        dataframe: DataFrame,
        pair: str,
    ):
        inf_frames: list[DataFrame] = []
        for cbs_strategy in strategies:
            # load instance of strategy_name
            strategy = Populator._load_strategy(
                cbs_strategy, parent_strategy=parent_strategy
            )
            dataframe = strategy.advise_indicators(dataframe, {'pair': pair})
            # remove inf data from dataframe to avoid duplicates
            # _x or _y gets added to the inf columns that already exist
            inf_frames.append(dataframe.filter(regex=r"\w+_\d{1,2}[mhd]"))
            dataframe = dataframe[
                dataframe.columns.drop(
                    list(dataframe.filter(regex=r"\w+_\d{1,2}[mhd]"))
                )
            ]

        # add informative data back to dataframe
        for frame in inf_frames:
            for col, series in frame.iteritems():
                if col in dataframe:
                    continue
                dataframe[col] = series

        return dataframe

    @staticmethod
    def _populate_buy(
        strategies: list[Strategy],
        dataframe: DataFrame,
        pair: str,
    ):
        dataframe['buy_tag'] = ''
        dataframe['buy_strategies'] = ''
        for cbs_strategy in strategies:
            # load instance of strategy_name
            strategy = Populator._load_strategy(cbs_strategy)
            # essentially call populate_buy_trend on strategy_name
            # I use copy() here to prevent duplicate columns from being populated
            strategy_dataframe = strategy.advise_buy(dataframe.copy(), {'pair': pair})
            # create column for `strategy`
            strategy_dataframe.loc[:, "buy_strategies"] = ""
            # On every candle that a buy signal is found, strategy_name
            # name will be added to its 'new_buy_tag' column
            strategy_dataframe.loc[
                strategy_dataframe.buy == 1, "buy_strategies"
            ] = cbs_strategy.strategy_name
            # get the strategies that already exist for the row in the original dataframe
            strategy_dataframe.loc[:, "existing_strategies"] = dataframe[
                "buy_strategies"
            ]
            # join the strategies found in the original dataframe's row with the new strategy
            strategy_dataframe.loc[:, "buy_strategies"] = strategy_dataframe.apply(
                lambda x: ",".join(
                    (x["buy_strategies"], x["existing_strategies"])
                ).strip(","),
                axis=1,
            )
            # # update the original dataframe with the new strategies buy signals
            dataframe.loc[:, "buy_strategies"] = strategy_dataframe["buy_strategies"]
            for k in strategy_dataframe:
                if k not in dataframe:
                    dataframe[k] = strategy_dataframe[k]
        # drop unnecessary columns
        dataframe.drop(
            [
                'existing_strategies',
            ],
            axis=1,
            inplace=True,
            errors="ignore",
        )
        dataframe.loc[(dataframe.buy_strategies != ''), 'buy_tag'] = (
            f'({pair}) ' + dataframe.buy_strategies
        )
        # set `buy` column of rows with a buy_tag to 1
        dataframe.loc[dataframe.buy_tag != "", "buy"] = 1
        return dataframe

    @staticmethod
    def _populate_sell(
        strategies: list[Strategy],
        dataframe: DataFrame,
        pair: str,
    ):
        dataframe['sell_tag'] = ''
        dataframe['sell_strategies'] = ''

        for csb_strategy in strategies:
            # If you know a better way of doing this, feel free to criticize this and let me know!
            # load instance of strategy_name
            strategy = Populator._load_strategy(csb_strategy)

            # essentially call populate_sell_trend on strategy_name
            # I use copy() here to prevent duplicate columns from being populated
            dataframe_copy = strategy.advise_sell(dataframe.copy(), {'pair': pair})

            # create column for `strategy`
            dataframe_copy.loc[:, "sell_strategies"] = ""
            # On every candle that a buy signal is found, strategy_name
            # name will be added to its 'strategy' column
            dataframe_copy.loc[
                dataframe_copy.sell == 1, "sell_strategies"
            ] = csb_strategy.strategy_name
            # get the strategies that already exist for the row in the original dataframe
            dataframe_copy.loc[:, "existing_strategies"] = dataframe["sell_strategies"]
            # join the strategies found in the original dataframe's row with the new strategy
            dataframe_copy.loc[:, "sell_strategies"] = dataframe_copy.apply(
                lambda x: ",".join(
                    (x["sell_strategies"], x["existing_strategies"])
                ).strip(","),
                axis=1,
            )
            # update the original dataframe with the new strategies sell signals
            dataframe.loc[:, "sell_strategies"] = dataframe_copy["sell_strategies"]
            for k in dataframe_copy:
                if k not in dataframe:
                    dataframe[k] = dataframe_copy[k]
        # drop unnecessary columns
        dataframe.drop(
            [
                'new_sell_tag',
                'existing_strategies',
            ],
            axis=1,
            inplace=True,
            errors="ignore",
        )
        # clear sell signals so they can be handled by custom_sell
        dataframe.loc[dataframe.sell_strategies != '', 'sell'] = 1
        # noinspection PyComparisonWithNone
        dataframe.loc[
            (dataframe.sell_strategies != '') & dataframe.exit_tag.isna(), 'exit_tag'
        ] = (f'({pair}) ' + dataframe.sell_strategies)
        return dataframe

    @staticmethod
    def buy_trend(dataframe: DataFrame, pair: str, mapper: Mapper):
        strategies = mapper.get_strategies(pair)
        if not any(strategies):
            return dataframe
        logger.info(f"Populating buy signals for {pair} ")
        dataframe = Populator._populate_buy(strategies, dataframe, pair)
        return dataframe

    @classmethod
    def sell_trend(cls, dataframe, pair, mapper: Mapper):
        strategies = mapper.get_strategies(pair)
        if not any(strategies):
            return dataframe
        logger.info(f"Populating sell signals for {pair} ")
        dataframe = Populator._populate_sell(strategies, dataframe, pair)
        return dataframe
