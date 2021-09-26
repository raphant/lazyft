import uuid
from pathlib import Path

import rapidjson

from lazyft import logger, regex, paths
from lazyft.config import Config
from lazyft.models import HyperoptPerformance, HyperoptRepo, HyperoptReport
from lazyft.paths import PARAMS_FILE
from lazyft.util import ParameterTools


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
        self.id = str(uuid.uuid4())
        self.strategy = strategy
        self.config = config
        self.balance_info = balance_info
        self.tag = tag
        self.params_file = ParameterTools.save_params_file(strategy, self.id)
        extracted = self._extract_output(output)
        self.report_id = report_id
        if not extracted:
            raise ValueError('Report is empty')
        logger.debug('Finished extracting output')
        self.performance = extracted
        self.hyperopt_file = Path(
            paths.LAST_HYPEROPT_RESULTS_FILE.parent,
            rapidjson.loads(paths.LAST_HYPEROPT_RESULTS_FILE.read_text())[
                'latest_hyperopt'
            ],
        ).resolve()

    def save(self) -> HyperoptReport:
        """
        Returns: ID of report
        """
        if not PARAMS_FILE.exists():
            PARAMS_FILE.write_text('{}')
        repo = HyperoptRepo.parse_file(PARAMS_FILE)
        model = self.to_model
        repo.reports.append(model)
        PARAMS_FILE.write_text(repo.json())
        return model

    @classmethod
    def get_existing_data(cls) -> dict:
        if PARAMS_FILE.exists():
            return rapidjson.loads(PARAMS_FILE.read_text())
        return {}

    @property
    def to_model(self):
        return HyperoptReport(
            report_id=self.report_id,
            param_id=self.id,
            strategy=self.strategy,
            params_file=self.params_file,
            performance=self.performance,
            pairlist=self.config.whitelist,
            balance_info=self.balance_info,
            exchange=self.config['exchange']['name'],
            tag=self.tag,
            hyperopt_file=self.hyperopt_file,
        )

    @staticmethod
    def _extract_output(output: str) -> HyperoptPerformance:
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
