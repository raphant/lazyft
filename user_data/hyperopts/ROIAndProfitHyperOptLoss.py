from pandas import DataFrame
from freqtrade.optimize.hyperopt import IHyperOptLoss

# Modify weights in order to maximice one aspect over another
ROI_WEIGHT = 3
STRATEGY_SELL_WEIGHT = 0
TRAILING_WEIGHT = 0
WIN_WEIGHT = 1
MIN_STOP_LOSS_WEIGHT = 0
PROFIT_WEIGHT = 20

SUM_WEIGHT = (
    ROI_WEIGHT
    + STRATEGY_SELL_WEIGHT
    + TRAILING_WEIGHT
    + WIN_WEIGHT
    + MIN_STOP_LOSS_WEIGHT
    + PROFIT_WEIGHT
)


class ROIAndProfitHyperOptLoss(IHyperOptLoss):
    @staticmethod
    def hyperopt_loss_function(
        results: DataFrame, trade_count: int, *args, **kwargs
    ) -> float:
        # Calculate the rate for different sell reason types
        results.loc[(results['sell_reason'] == 'roi'), 'roi_signals'] = 1
        roi_signals_rate = results['roi_signals'].sum() / trade_count

        results.loc[
            (results['sell_reason'] == 'sell_signal'), 'strategy_sell_signals'
        ] = 1
        strategy_sell_signal_rate = results['strategy_sell_signals'].sum() / trade_count

        results.loc[
            (results['sell_reason'] == 'trailing_stop_loss'),
            'trailing_stop_loss_signals',
        ] = 1
        trailing_stop_loss_signals_rate = (
            results['trailing_stop_loss_signals'].sum() / trade_count
        )

        results.loc[(results['sell_reason'] == 'stop_loss'), 'stop_loss_signals'] = 1
        stop_loss_signals_rate = results['stop_loss_signals'].sum() / trade_count

        results.loc[(results['profit_ratio'] > 0), 'wins'] = 1
        win_rate = results['wins'].sum() / trade_count

        average_profit = results['profit_ratio'].mean() * 100

        return (
            -1
            * (
                roi_signals_rate * ROI_WEIGHT
                + strategy_sell_signal_rate * STRATEGY_SELL_WEIGHT
                + trailing_stop_loss_signals_rate * TRAILING_WEIGHT
                + win_rate * WIN_WEIGHT
                + (1 - stop_loss_signals_rate) * MIN_STOP_LOSS_WEIGHT
                + average_profit * PROFIT_WEIGHT
            )
            / SUM_WEIGHT
        )
