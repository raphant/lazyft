from bullet import YesNo
from lazyft import logger
from lazyft.command_parameters import HyperoptParameters

days = 365

if __name__ == '__main__':
    hp = HyperoptParameters(
        config_path='config.1.18.22.json',
        epochs=10,
        spaces='buy sell',
        min_trades=1,
        # loss='WinRatioAndProfitRatioLoss',
        # loss='ROIAndProfitHyperOptLoss',
        loss='CalmarHyperOptLoss',
        # loss='SortinoHyperOptLoss',
        # timerange='20210110-20220110',
        interval='2h',
        days=days,
        download_data=True,
        max_open_trades=3,
        starting_balance=100,
        stake_amount='33.33',
        custom_spaces='all',
        custom_settings={
            'use_custom_stoploss': False,
            'timeframe': '2h',
        },
        jobs=-2,
    )
    runner = hp.run('IndicatorMixAdvancedOpt', load_hashed_strategy=False)
    if runner.error:
        if runner.exception:
            raise runner.exception
        exit(1)

    # assert bool(runner.report)
    logger.info('Report: {}', runner.report)
    if bool(runner.report):
        print(runner.report.report_text)
    else:
        exit(1)
    client = YesNo('Do you want to save the report? ', default='n')
    result = client.launch()
    if bool(runner.report) and result:
        runner.save()
