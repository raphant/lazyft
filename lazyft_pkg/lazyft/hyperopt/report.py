import attr
import rapidjson
from loguru import logger

from lazyft import util, regex
from lazyft.config import Config
from lazyft.paths import PARAMS_FILE, STRATEGY_DIR, PARAMS_DIR
from lazyft.strategy import Strategy


@attr.s
class HyperoptPerformance:
    trades: int = attr.ib(converter=int)
    wins: int = attr.ib(converter=int)
    losses: int = attr.ib(converter=int)
    draws: int = attr.ib(converter=int)
    avg_profits: float = attr.ib(converter=float)
    med_profit: float = attr.ib(converter=float)
    tot_profit: float = attr.ib(converter=float)
    profit_percent: float = attr.ib(converter=float)
    avg_duration: str = attr.ib()
    loss: float = attr.ib(converter=float)
    seed: int = attr.ib()
    from_date: str = attr.ib()
    to_date: str = attr.ib()


class HyperoptReport:
    def __init__(
        self,
        config: Config,
        output: str,
        strategy: str,
        secondary_config: dict = None,
    ) -> None:
        self.id = util.rand_token()
        self.strategy = strategy
        self.config = config
        self.secondary_config = secondary_config
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
        data = self.add_to_existing_data()
        PARAMS_FILE.write_text(rapidjson.dumps(data, indent=2))
        return self.id

    def add_to_existing_data(self) -> dict:
        # grab all data
        data = self.get_existing_data()
        # get strategy data if available, else create empty dict
        strategy_data = data.get(self.strategy, {})
        # add the current params to id in strategy data
        strategy_data[self.id] = {
            "params_file": str(self.params_file),
            "performance": self.performance.__dict__,
            "pairlist": self.config.whitelist,
            "balance_info": self.secondary_config,
        }
        # add strategy back to all data
        data[self.strategy] = strategy_data
        return data

    @classmethod
    def get_existing_data(cls) -> dict:
        if PARAMS_FILE.exists():
            return rapidjson.loads(PARAMS_FILE.read_text())
        return {}

    def _extract_output(self, output: str) -> HyperoptPerformance:
        logger.debug("Extracting output...")
        search = regex.FINAL_REGEX.search(output)
        assert search
        date_search = regex.H_DATE_FROM_TO.search(output)
        from_ = date_search.groupdict()["from"]
        to = date_search.groupdict()["to"]
        seed_search = regex.SEED_REGEX.search(output)
        seed = seed_search.groups()[0]
        performance = HyperoptPerformance(
            **search.groupdict(), seed=seed, from_date=from_, to_date=to
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
