from freqtrade.loggers import setup_logging_pre
from lazyft.command_parameters import BacktestParameters
from lazyft.config import Config

config_name = 'config_binance_20220526.json'

days = 30

if __name__ == '__main__':
    setup_logging_pre()

    cp = BacktestParameters(
        config_path=config_name,
        days=days,
        # timerange='20210110-20220110',
        download_data=True,
        # secrets_config=Config('config_binance_20220526.json'),
        # inf_interval='1h 1d',
        # pairs=['SOL/USDT'],
        max_open_trades=3,
        interval='1h',
        starting_balance=100,
        stake_amount='unlimited',
        # extra_args='--breakdown month',
        # timeframe_detail='5m',
        custom_settings={
            'use_custom_stoploss': False,
            # 'timeframe': '2h',
        },
        cache='none',
    )
    runner = cp.run('BB_RPB_TSL', load_from_hash=False)
    if runner.error:
        raise RuntimeError('Error in backtest runner')
    if bool(runner.report) and not runner.exception:
        report = runner.save()
        # report.trades_to_csv('bats_no_trailing.csv')
        # report.plot_weekly()
        print(report.report_text)
        report.plot()
