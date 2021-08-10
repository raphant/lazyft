import rapidjson

from lazyft import logger, util, regex
from lazyft.config import Config
from lazyft.models import HyperoptPerformance, BalanceInfo, HyperoptRepo, HyperoptReport
from lazyft.paths import PARAMS_FILE, STRATEGY_DIR, PARAMS_DIR
from lazyft.strategy import Strategy


class HyperoptReportExporter:
    def __init__(
        self,
        config: Config,
        output: str,
        strategy: str,
        balance_info: BalanceInfo = None,
        tags: list[str] = None,
    ) -> None:
        self.id = util.rand_token(8)
        self.strategy = strategy
        self.config = config
        self.balance_info = balance_info
        self.tags = tags
        self.params_file = self.get_params_file(strategy)
        extracted = self._extract_output(output)
        if not extracted:
            raise ValueError('Report is empty')
        self.performance = extracted

    def get_params_file(self, strategy):
        strategy_json = Strategy.get_file_name(strategy).rstrip('.py') + '.json'
        strat_file = STRATEGY_DIR.joinpath(strategy_json)
        moved = strat_file.replace(PARAMS_DIR.joinpath(self.id + '.json'))
        strat_file.unlink(missing_ok=True)
        return moved

    def save(self) -> str:
        """
        Returns: ID of report
        """
        if not PARAMS_FILE.exists():
            PARAMS_FILE.write_text('{}')
        repo = HyperoptRepo.parse_file(PARAMS_FILE)
        repo.reports.append(self.to_model)
        PARAMS_FILE.write_text(repo.json())
        return self.id

    @classmethod
    def get_existing_data(cls) -> dict:
        if PARAMS_FILE.exists():
            return rapidjson.loads(PARAMS_FILE.read_text())
        return {}

    @property
    def to_model(self):
        return HyperoptReport(
            id=self.id,
            strategy=self.strategy,
            params_file=str(self.params_file),
            performance=self.performance,
            pairlist=self.config.whitelist,
            balance_info=self.balance_info,
            exchange=self.config['exchange']['name'],
            tags=self.tags,
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
