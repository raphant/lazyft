from pathlib import Path

import rapidjson

from lazyft import logger, regex, paths
from lazyft.config import Config
from lazyft.models import HyperoptPerformance, HyperoptReport
from lazyft.paths import PARAMS_FILE
from lazyft.strategy import StrategyTools


class HyperoptReportExporter:
    def __init__(
        self,
        config: Config,
        output: str,
        strategy: str,
        report_id: str,
        balance_info: dict = None,
        tag: str = None,
    ) -> None:
        self.strategy = strategy
        self.config = config
        self.tag = tag
        self.report_id = report_id
        self.balance_info = balance_info
        if isinstance(self.balance_info['stake_amount'], str):
            self.balance_info['stake_amount'] = -1
        try:
            extracted = self.get_performance_from_output(output)
        except (AssertionError, ValueError):
            raise ValueError('Report is empty')
        logger.debug('Finished extracting output')
        self.performance = extracted
        self.hyperopt_file = Path(
            paths.LAST_HYPEROPT_RESULTS_FILE.parent,
            rapidjson.loads(paths.LAST_HYPEROPT_RESULTS_FILE.read_text())[
                'latest_hyperopt'
            ],
        ).resolve()

    @classmethod
    def get_existing_data(cls) -> dict:
        if PARAMS_FILE.exists():
            return rapidjson.loads(PARAMS_FILE.read_text())
        return {}

    def generate(self):
        return HyperoptReport(
            strategy=self.strategy,
            performance_string=rapidjson.dumps(
                self.performance.dict(), datetime_mode=rapidjson.DM_ISO8601
            ),
            param_data_str=StrategyTools.create_strategy_params_filepath(
                self.strategy
            ).read_text(),
            pairlist=','.join(self.config.whitelist),
            exchange=self.config['exchange']['name'],
            tag=self.tag,
            hyperopt_file_str=str(self.hyperopt_file),
            max_open_trades=self.balance_info['max_open_trades'],
            stake_amount=self.balance_info['stake_amount'],
            starting_balance=self.balance_info['starting_balance'],
        )

    @staticmethod
    def get_performance_from_output(output: str) -> HyperoptPerformance:
        logger.debug("Extracting output...")
        search = regex.FINAL_REGEX.search(output)
        assert search
        date_search = regex.H_DATE_FROM_TO.search(output)
        from_ = date_search.groupdict()["from"]
        to = date_search.groupdict()["to"]
        seed_search = regex.SEED_REGEX.search(output)
        seed = seed_search.groups()[0]
        performance = HyperoptPerformance(
            **search.groupdict(), seed=seed, start_date=from_, end_date=to
        )

        return performance

    @staticmethod
    def _format_parameters(params: dict) -> dict:
        dictionary = {}
        assert "params" in params, '"params" key not found while scraping parameters.'
        bs = params.pop("params")
        buy_params = {}
        sell_params = {}
        for k, v in bs.items():
            d = buy_params if "buy" in k else sell_params
            try:
                d[k] = float(v)
            except (TypeError, ValueError):
                d[k] = v
        if buy_params:
            dictionary["buy_params"] = buy_params
        if sell_params:
            dictionary["sell_params"] = sell_params
        dictionary.update(**params)
        return dictionary
