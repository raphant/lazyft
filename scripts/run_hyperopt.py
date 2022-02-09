from bullet import YesNo

from lazyft.command_parameters import HyperoptParameters
from lazyft import logger

days = 365

if __name__ == '__main__':
    hp = HyperoptParameters(
        config_path='config.1.18.22.json',
        epochs=15,
        spaces='buy sell',
        min_trades=1,
        loss='WinRatioAndProfitRatioLoss',
        # loss='ROIAndProfitHyperOptLoss',
        # loss='CalmarHyperOptLoss',
        # loss='SortinoHyperOptLoss',
        # timerange='20210110-20220110',
        days=days,
        download_data=True,
        max_open_trades=3,
        starting_balance=1000,
        stake_amount='333.33',
        custom_spaces='all',
        custom_settings={
            'use_custom_stoploss': False,
        },
        jobs=-2,
    )
    runner = hp.run('BatsContest-40', load_hashed_strategy=False)
    if runner.error:
        raise runner.exception
    # assert bool(runner.report)
    logger.info('Report: {}', runner.report)
    if runner.report:
        print(runner.report.report_text)
    client = YesNo('Do you want to save the report? ', default='n')
    result = client.launch()
    if bool(runner.report) and result:
        runner.save()
