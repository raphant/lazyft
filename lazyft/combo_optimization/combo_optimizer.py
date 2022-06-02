"""
This class defines the ComboOptimizer class which combines both Hyperopt and backtesting
for the purpose of finding the best combination of parameters on multiple market conditions.

This class utilizes custom spaces from the lazyft module and will automatically load the spaces
from a passed strategy. The strategy will have to define the spaces using the SpaceHandler class for
the spaces to be recognized.
"""
from collections import Counter, defaultdict
from copy import deepcopy
from functools import reduce
from itertools import combinations
from random import shuffle
from typing import Iterable, Optional

from lazyft.backtest.runner import BacktestRunner
from lazyft.combo_optimization import logger, notify
from lazyft.combo_optimization.errors import HyperoptError
from lazyft.combo_optimization.requirements import (
    find_epochs_that_meet_requirement,
    report_meets_requirements,
    should_update_hyperopt_baseline,
)
from lazyft.combo_optimization.stats import append_stats, print_stats
from lazyft.command_parameters import BacktestParameters, HyperoptParameters
from lazyft.hyperopt import HyperoptRunner
from lazyft.models.backtest import BacktestReport
from lazyft.models.hyperopt import HyperoptReport
from lazyft.reports import get_backtest_repo, get_hyperopt_repo
from lazyft.strategy import Strategy, get_space_handler_spaces
from lazyft.util import dict_to_telegram_string


class ComboOptimizer:
    """
    This class defines the ComboOptimizer class which combines both Hyperopt and backtesting
    """

    def __init__(
        self,
        backtest_requirements: dict,
        hyperopt_requirements: dict,
        n_trials=3,
    ) -> None:
        """
        Initialize the hyperopt class

        :param backtest_requirements: A dictionary of requirements that will be used to determine if a
            report meets the requirements
        :type backtest_requirements: dict
        :param hyperopt_requirements: A dictionary of requirements that will be used to determine if a
            report meets the requirements
        :type hyperopt_requirements: dict
        :param n_trials: The number of hyperopt trials to run, defaults to 3 (optional)
        """
        self.number_of_trials = n_trials
        self.backtest_requirements = backtest_requirements
        self.hyperopt_requirements = hyperopt_requirements

        self.backtests = []
        self.meets: dict[int, list[BacktestReport]] = {}

        self.current_trial = 0
        self.current_idx = 0
        self.best_hyperopt_id = None
        self.best_backtest_id = None
        self.strategy = None

        self.best_backtest_report: Optional[BacktestReport] = None

        self.custom_spaces: list[str] = []
        self.generated_params: list[HyperoptParameters] = []

        self.stats = defaultdict(list)
        self.counter = Counter()

        self.prepared = False

    def prepare(
        self,
        strategy: str,
        base_parameters: HyperoptParameters,
        shuffle_spaces: bool = True,
        extra_spaces: list[str] = None,
    ) -> None:
        """
        It takes the extra spaces and the base parameters and generates a list of hyperopt parameters

        :param strategy: The strategy to be used
        :type strategy: str
        :param extra_spaces: A list of extra spaces to be added to the default spaces
        :type extra_spaces: list[str]
        :param base_parameters: The base parameters to be used for the hyperopt
        :type base_parameters: HyperoptParameters
        :param shuffle_spaces: Whether to shuffle the spaces or not
        :type shuffle_spaces: bool
        """
        logger.info(f"Preparing {strategy} for combo optimization")
        self.strategy = strategy
        self.custom_spaces = self.generate_custom_spaces(extra_spaces)
        self.generated_params = self.generate_hyperopt_params(
            base_parameters, self.custom_spaces, shuffle_spaces
        )
        self.prepared = True

    def generate_custom_spaces(
        self,
        extra_spaces: Iterable[str] = None,
        max_len_of_combo: int = 4,
    ) -> list[str]:
        """
        Given a list of spaces, return all combinations of spaces.

        :param extra_spaces: A list of extra spaces to be added to the default spaces
        :type extra_spaces: Iterable[str]
        :param max_len_of_combo: The maximum length of the combo spaces
        :type max_len_of_combo: int
        :return: A list of strings.
        """
        logger.info("Generating custom spaces...")
        custom_spaces = get_space_handler_spaces(self.strategy)
        logger.info(f"Found {len(custom_spaces)} custom spaces in {self.strategy}: {custom_spaces}")
        if extra_spaces:
            custom_spaces.update(extra_spaces)

        spaces_combinations = reduce(
            lambda x, y: list(combinations(custom_spaces, y)) + x, range(len(custom_spaces) + 1), []
        )
        spaces_combinations = [
            " ".join(s) for s in spaces_combinations if 0 < len(s) < max_len_of_combo
        ]
        logger.info(f"Generated {len(spaces_combinations)} space combinations")
        return spaces_combinations

    @staticmethod
    def generate_hyperopt_params(
        base_params: HyperoptParameters,
        generated_spaces: list[str],
        shuffle_spaces: bool = True,
    ) -> list[HyperoptParameters]:
        """
        It takes a list of spaces, splits them into a list of spaces,
        and then creates a list of HyperoptParameters from the spaces

        :param base_params: A HyperoptParameters object with parameters that will be passed to the
            freqtrade hyperopt function.
        :type base_params: HyperoptParameters
        :param generated_spaces: list[str]
        :type generated_spaces: list[str]
        :param shuffle_spaces: If True, the order of the combinations will be randomized, defaults to
        True
        :type shuffle_spaces: bool (optional)
        :return: A list of HyperoptParameters objects.
        """
        logger.info("Generating hyperopt parameters...")
        hyperopt_params = []
        for space in generated_spaces:
            custom_spaces = ""
            spaces = ""
            params_copy = deepcopy(base_params)
            split = space.split(" ")
            for cs in split:
                if cs in ["roi", "stoploss", "trailing"]:
                    spaces += " " + cs
                else:
                    custom_spaces += " " + cs
            params_copy.custom_spaces = custom_spaces.strip()
            if spaces:
                params_copy.spaces += " " + spaces.strip()
            combined_space = (spaces + " " + custom_spaces).strip()
            params_copy.tag += f"__{combined_space}__{base_params.interval}"
            hyperopt_params.append(params_copy)
        # hyperopt_params = [
        #     h for h in hyperopt_params if len(h.custom_spaces.split()) <= max_len_of_combo
        # ]
        if shuffle_spaces:
            shuffle(hyperopt_params)
        logger.info(f"Created {len(hyperopt_params)} hyperopt parameters")
        return hyperopt_params

    def add_backtest(self, backtest_params: BacktestParameters) -> None:
        """
        Add a backtest to the backtests list

        :param backtest_params: A BacktestParameters object with parameters that will be passed to the
        :type backtest_params: BacktestParameters
        """
        self.backtests.append(backtest_params)

    def start_optimization(self) -> None:
        """
        For each hyperparameter, we run the hyperopt function and save the results.
        If the results meet the requirements, we backtest the results and save the results.
        We then delete the hyperopt results and repeat the process for the next hyperparameter
        """
        if not self.prepared:
            raise RuntimeError("You must call prepare() before start_optimization()")
        if not any(self.backtests):
            raise RuntimeError("You must add at least one backtest before start_optimization()")
        if self.best_backtest_id:
            self.best_backtest_report = get_backtest_repo().get(self.best_hyperopt_id)
        logger.info(
            f"Starting optimization for {self.strategy} with {len(self.generated_params)} "
            f"hyperopt parameters"
        )
        for i in range(1, self.number_of_trials + 1):
            self.current_trial = i
            logger.info(f"Starting trial {i}/{self.number_of_trials}")
            meets = []
            for idx, hyperopt_parameter in enumerate(self.generated_params, start=1):
                self.current_idx = idx
                to_backtest = []
                logger.info(
                    f"Hyperopting {hyperopt_parameter.tag} ({idx}/{len(self.generated_params)})"
                )
                try:
                    runner = self.run_hyperopt(hyperopt_parameter)
                except Exception as e:
                    logger.error(f"Error in trial {i}, index {idx}")
                    logger.exception(e)
                    raise e
                if not runner:
                    continue
                h_report = runner.save()
                epochs_that_meet_req = find_epochs_that_meet_requirement(
                    h_report, self.hyperopt_requirements, n_results=5
                )

                if not any(epochs_that_meet_req):
                    logger.info(
                        f"Found no epochs that meet requirements in hyperopt #{h_report.id}"
                    )
                    get_hyperopt_repo().delete(h_report.id)
                    continue
                else:
                    to_backtest.extend(epochs_that_meet_req)
                    logger.info(
                        f"Found {len(epochs_that_meet_req)} epochs that meet requirements in hyperopt #{h_report.id}"
                    )
                get_hyperopt_repo().delete(h_report.id)
                meets.extend(self.backtest_passed_epochs(to_backtest, hyperopt_parameter))
                print_stats(self.stats, self)
            logger.info(
                f'Reports rejected: {self.counter["n_skipped"]}, '
                f'Reports accepted: {self.counter["n_passed"]}, '
                f"Current best HID: {self.best_hyperopt_id}"
            )
            self.meets[i] = meets

    def run_hyperopt(self, parameter: HyperoptParameters) -> HyperoptRunner:
        """
        Run a hyperopt with the given parameters

        :param parameter: A HyperoptParameters object with parameters that will be passed to the
        :type parameter: HyperoptParameters
        :return: A HyperoptRunner object
        """
        strategy = Strategy(name=self.strategy, id=self.best_hyperopt_id)
        runner = parameter.run(strategy)
        # make sure report meets requirements
        if runner.exception or runner.error:
            logger.info(f"Report #{runner.report.id} failed with exception {runner.exception}")
            raise HyperoptError(
                f"Report #{runner.report.id} failed with exception {runner.exception}"
            )
        return runner

    def backtest_passed_epochs(
        self, to_backtest: list[HyperoptReport], hyperopt_parameter: HyperoptParameters
    ) -> list[BacktestReport]:
        """
        The function iterates through the list of hyperopt reports, and for each hyperopt report, it
        runs a backtest.

        The function then checks if the backtest meets the requirements. If it does, it appends the
        backtest report to the meets list.

        The function also updates the best hyperopt id if the backtest meets the requirements.

        :param to_backtest: A list of hyperopt reports that passed the requirements
        :type to_backtest: list[HyperoptReport]
        :param hyperopt_parameter: A HyperoptParameters object with parameters that were passed to the
            runner
        :type hyperopt_parameter: HyperoptParameters
        :return: A list of backtest reports that passed the requirements
        """
        meets = []
        for j, hyperopt_report in enumerate(to_backtest, start=1):
            try:
                logger.info(
                    f"Backtesting #{hyperopt_report.id}-{hyperopt_report.tag} ({j}/{len(to_backtest)})"
                )
                # notify(f'`Backtesting hyperopt #{r.id}-{r.tag} ({idx + 1}/{len(to_backtest)})`')
                b_runner = self.run_backtest(hyperopt_parameter, hyperopt_report)
                b_report = b_runner.save()
                append_stats(hyperopt_report, b_report, self.stats)
            except Exception as e:
                logger.exception(f"Failed while backtesting on idx {j}", exc_info=e)
                break
            if not report_meets_requirements(b_report, self.backtest_requirements):
                if not self.best_hyperopt_id:
                    logger.info(f"No hyperopt baseline found, updating to #{hyperopt_report.id}")
                    self.best_hyperopt_id = hyperopt_report.id
                    continue
                logger.info(
                    f"Backtest #{b_report.id} with hyperopt #{hyperopt_report.id} does not meet requirements {b_report.performance.dict()}"
                )
                get_backtest_repo().delete(b_report.id)
                get_hyperopt_repo().delete(hyperopt_report.id)
                self.counter["n_skipped"] += 1
            else:
                logger.info(
                    f"Backtest #{b_report.id} with hyperopt #{hyperopt_report.id} meets all requirements: \n{b_report.report_text}"
                )
                # notify(
                #     f'Backtest report #{b_report.id} `({r.tag})` meets all requirements.\n'
                #     f'Hyperopt #{r.id}:\n{dict_to_telegram_string(r.performance.dict())}\n\n'
                #     f'Backtest #{b_report.id}:\n{dict_to_telegram_string(b_report.performance.dict())}'
                # )
                meets.append(b_report)
                self.stats["n_passed"] += 1

                # update hyperopt id?
                self.update_best(b_report, hyperopt_report)
        return meets

    def run_backtest(
        self, hyperopt_parameter: HyperoptParameters, hyperopt_report: HyperoptReport
    ) -> BacktestRunner:
        """
        It takes a hyperopt parameter and a hyperopt report, and runs a backtest with the hyperopt
        parameter

        :param hyperopt_parameter: A HyperoptParameters object with parameters that will be passed
            to the runner
        :type hyperopt_parameter: HyperoptParameters
        :param hyperopt_report: The completed hyperopt report
        :type hyperopt_report: HyperoptReport
        :return: The backtest runner.
        """
        b_params_copy = deepcopy(self.backtests[0])
        b_params_copy.interval = hyperopt_parameter.interval
        b_params_copy.tag = f"{hyperopt_report.id}-{hyperopt_report.tag}"
        b_params_copy.custom_spaces = hyperopt_parameter.custom_spaces
        b_params_copy.custom_settings = hyperopt_parameter.custom_settings
        b_runner = b_params_copy.run(
            f"{hyperopt_report.strategy}-{hyperopt_report.id}", load_from_hash=True
        )
        if b_runner.error or b_runner.exception:
            logger.info(
                f"Backtest with hyperopt #{hyperopt_report.id} failed with exception {b_runner.exception}"
            )
            raise Exception(
                f"Error while backtesting with hyperopt #{hyperopt_report.id}. Error: {b_runner.error}, Exception: {b_runner.exception}"
            )
        return b_runner

    def update_best(self, b_report, hyperopt_report):
        """
        If the new report is better than the current best report, then update the best report

        :param b_report: The backtest report that we just ran
        :param hyperopt_report: the report of the hyperopt run that we are currently evaluating
        """
        if not self.best_hyperopt_id or should_update_hyperopt_baseline(
            self.best_backtest_report, b_report
        ):
            if not self.best_hyperopt_id:
                logger.info(f"No hyperopt baseline found, updating to #{b_report.hyperopt_id}")
            else:
                logger.info(
                    f"Found a better hyperopt baseline, updating to #{b_report.hyperopt_id}"
                )
            self.best_backtest_report = b_report
            self.best_backtest_id = b_report.id
            self.best_hyperopt_id = b_report.hyperopt_id
            # notify(f"New hyperopt baseline #{h_id}:\n{dict_to_telegram_string(b_report.performance.dict())}")
            notify(
                f"New hyperopt baseline `({hyperopt_report.tag})`.\n"
                f"Hyperopt #{hyperopt_report.id}:\n{dict_to_telegram_string(hyperopt_report.performance.dict())}\n\n"
                f"Backtest #{b_report.id}:\n{dict_to_telegram_string(b_report.performance.dict())}"
            )
        else:
            logger.info(
                f"New report #{b_report.id} from hyperopt #{hyperopt_report.id} was not an improvement"
            )
