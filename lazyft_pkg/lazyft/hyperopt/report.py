from typing import Tuple

import attr
import rapidjson

from lazyft import logger, util
from lazyft.constants import BASE_DIR
from lazyft.quicktools import regex

logger.getChild("hyperopt.report")


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
    SAVE_PATH = BASE_DIR.joinpath("lazy_params.json")

    def __init__(self, output: str, raw_params: str, strategy: str) -> None:
        self.strategy = strategy
        extracted = self._extract_output(raw_params, output)
        if not extracted:
            raise ValueError('Report is empty')
        self.params, self.performance = extracted
        self.id = util.rand_token()

    def save(self):
        data = self.add_to_existing_data()
        # with self.SAVE_PATH.open("w") as f:
        #     yaml.dump(data, f)
        self.SAVE_PATH.write_text(rapidjson.dumps(data))

    def add_to_existing_data(self):
        # grab all data
        data = self.get_existing_data()
        # get strategy data if available, else create empty dict
        strategy_data = data.get(self.strategy, {})
        # add the current params to id in strategy data
        strategy_data[self.id] = {
            "params": self.params,
            "performance": self.performance.__dict__,
        }
        # add strategy back to all data
        data[self.strategy] = strategy_data
        return data

    @classmethod
    def get_existing_data(cls):
        if cls.SAVE_PATH.exists():
            return rapidjson.loads(cls.SAVE_PATH.read_text())
        return {}

    def _extract_output(
        self, raw: str, output: str
    ) -> Tuple[dict, HyperoptPerformance]:
        logger.debug("Extracting output...")
        search = regex.FINAL_REGEX.search(output)
        if search:
            params = (
                raw.strip()
                .replace('"True"', "true")
                .replace('"False"', "false")
                .replace('"none"', "null")
            )
            date_search = regex.H_DATE_FROM_TO.search(output)
            from_ = date_search.groupdict()["from"]
            to = date_search.groupdict()["to"]
            seed_search = regex.SEED_REGEX.search(output)
            seed = seed_search.groups()[0]
            performance = HyperoptPerformance(
                **search.groupdict(), seed=seed, from_date=from_, to_date=to
            )

            return self._format_parameters(rapidjson.loads(params)), performance

    @staticmethod
    def _format_parameters(params: dict):
        dictionary = {}

        if "params" in params:
            bs = params.pop("params")
            buy_params = {}
            sell_params = {}
            for k, v in bs.items():
                d = buy_params if "buy" in k else sell_params
                try:
                    d[k] = float(v)
                except ValueError:
                    d[k] = v
            if buy_params:
                dictionary["buy_params"] = buy_params
            if sell_params:
                dictionary["sell_params"] = sell_params
        dictionary.update(**params)
        return dictionary
