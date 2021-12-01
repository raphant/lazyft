import logging
import math

from freqtrade.misc import round_dict
from freqtrade.optimize.space.decimalspace import SKDecimal
from scipy.interpolate import interp1d
from skopt.space import Categorical, Dimension, Integer

logger = logging.getLogger()


class HyperOpt:
    # region manigold settings
    # roi
    roi_time_interval_scaling = 1
    roi_table_step_size = 5
    roi_value_step_scaling = 0.9
    # stoploss
    stoploss_min_value = -0.02
    stoploss_max_value = -0.3
    # trailing
    trailing_stop_positive_min_value = 0.01
    trailing_stop_positive_max_value = 0.08
    trailing_stop_positive_offset_min_value = 0.011
    trailing_stop_positive_offset_max_value = 0.1

    # endregion
    @classmethod
    def generate_roi_table(cls, params: dict) -> dict[int, float]:
        """
        Generates a Custom Long Continuous ROI Table with less gaps in it.
        Configurable step_size is loaded in from the Master MGM Framework.
        :param params: (dict) Base Parameters used for the ROI Table calculation
        :return dict: Generated ROI Table
        """
        step = cls.roi_table_step_size

        minimal_roi = {
            0: params["roi_p1"] + params["roi_p2"] + params["roi_p3"],
            params["roi_t3"]: params["roi_p1"] + params["roi_p2"],
            params["roi_t3"] + params["roi_t2"]: params["roi_p1"],
            params["roi_t3"] + params["roi_t2"] + params["roi_t1"]: 0,
        }

        max_value = max(map(int, minimal_roi.keys()))
        f = interp1d(list(map(int, minimal_roi.keys())), list(minimal_roi.values()))
        x = list(range(0, max_value, step))
        y = list(map(float, map(f, x)))
        if y[-1] != 0:
            x.append(x[-1] + step)
            y.append(0)
        return dict(zip(x, y))

    @classmethod
    def roi_space(cls) -> list[Dimension]:
        """
        Create a ROI space. Defines values to search for each ROI steps.
        This method implements adaptive roi HyperSpace with varied ranges for parameters which automatically adapts
        to the un-zoomed informative_timeframe used by the MGM Framework during BackTesting & HyperOpting.
        :return List: Generated ROI Space
        """

        # Default scaling coefficients for the ROI HyperSpace. Can be changed to adjust resulting ranges of the ROI
        # tables. Increase if you need wider ranges in the ROI HyperSpace, decrease if shorter ranges are needed:
        # roi_t_alpha: Limits for the time intervals in the ROI Tables. Components are scaled linearly.
        roi_t_alpha = cls.roi_time_interval_scaling
        # roi_p_alpha: Limits for the ROI value steps. Components are scaled logarithmically.
        roi_p_alpha = cls.roi_value_step_scaling

        # Load in the un-zoomed timeframe size from the Master MGM Framework
        timeframe_min = 5

        # The scaling is designed so that it maps exactly to the legacy Freqtrade roi_space()
        # method for the 5m timeframe.
        roi_t_scale = timeframe_min
        roi_p_scale = math.log1p(timeframe_min) / math.log1p(5)
        roi_limits = {
            "roi_t1_min": int(10 * roi_t_scale * roi_t_alpha),
            "roi_t1_max": int(120 * roi_t_scale * roi_t_alpha),
            "roi_t2_min": int(10 * roi_t_scale * roi_t_alpha),
            "roi_t2_max": int(60 * roi_t_scale * roi_t_alpha),
            "roi_t3_min": int(10 * roi_t_scale * roi_t_alpha),
            "roi_t3_max": int(40 * roi_t_scale * roi_t_alpha),
            "roi_p1_min": 0.01 * roi_p_scale * roi_p_alpha,
            "roi_p1_max": 0.04 * roi_p_scale * roi_p_alpha,
            "roi_p2_min": 0.01 * roi_p_scale * roi_p_alpha,
            "roi_p2_max": 0.07 * roi_p_scale * roi_p_alpha,
            "roi_p3_min": 0.01 * roi_p_scale * roi_p_alpha,
            "roi_p3_max": 0.20 * roi_p_scale * roi_p_alpha,
        }

        # Generate MGM's custom long continuous ROI table
        logger.debug(f"Using ROI space limits: {roi_limits}")
        p = {
            "roi_t1": roi_limits["roi_t1_min"],
            "roi_t2": roi_limits["roi_t2_min"],
            "roi_t3": roi_limits["roi_t3_min"],
            "roi_p1": roi_limits["roi_p1_min"],
            "roi_p2": roi_limits["roi_p2_min"],
            "roi_p3": roi_limits["roi_p3_min"],
        }
        logger.info(f"Min ROI table: {round_dict(cls.generate_roi_table(p), 3)}")
        p = {
            "roi_t1": roi_limits["roi_t1_max"],
            "roi_t2": roi_limits["roi_t2_max"],
            "roi_t3": roi_limits["roi_t3_max"],
            "roi_p1": roi_limits["roi_p1_max"],
            "roi_p2": roi_limits["roi_p2_max"],
            "roi_p3": roi_limits["roi_p3_max"],
        }
        logger.info(f"Max ROI table: {round_dict(cls.generate_roi_table(p), 3)}")

        return [
            Integer(roi_limits["roi_t1_min"], roi_limits["roi_t1_max"], name="roi_t1"),
            Integer(roi_limits["roi_t2_min"], roi_limits["roi_t2_max"], name="roi_t2"),
            Integer(roi_limits["roi_t3_min"], roi_limits["roi_t3_max"], name="roi_t3"),
            SKDecimal(
                roi_limits["roi_p1_min"],
                roi_limits["roi_p1_max"],
                decimals=3,
                name="roi_p1",
            ),
            SKDecimal(
                roi_limits["roi_p2_min"],
                roi_limits["roi_p2_max"],
                decimals=3,
                name="roi_p2",
            ),
            SKDecimal(
                roi_limits["roi_p3_min"],
                roi_limits["roi_p3_max"],
                decimals=3,
                name="roi_p3",
            ),
        ]

    @classmethod
    def stoploss_space(cls) -> list[Dimension]:
        """
        Define custom stoploss search space with configurable parameters for the Stoploss Value to search.
        Override it if you need some different range for the parameter in the 'stoploss' optimization hyperspace.
        :return List: Generated Stoploss Space
        """
        # noinspection PyTypeChecker
        return [
            SKDecimal(
                cls.stoploss_max_value,
                cls.stoploss_min_value,
                decimals=3,
                name="stoploss",
            )
        ]

    # noinspection PyTypeChecker
    @classmethod
    def trailing_space(cls) -> list[Dimension]:
        """
        Define custom trailing search space with parameters configurable in 'mgm-config'
        :return List: Generated Trailing Space
        """
        return [
            # It was decided to always set trailing_stop is to True if the 'trailing' hyperspace
            # is used. Otherwise hyperopt will vary other parameters that won't have effect if
            # trailing_stop is set False.
            # This parameter is included into the hyperspace dimensions rather than assigning
            # it explicitly in the code in order to have it printed in the results along with
            # other 'trailing' hyperspace parameters.
            Categorical([True], name="trailing_stop"),
            SKDecimal(
                cls.trailing_stop_positive_min_value,
                cls.trailing_stop_positive_max_value,
                decimals=3,
                name="trailing_stop_positive",
            ),
            # 'trailing_stop_positive_offset' should be greater than 'trailing_stop_positive',
            # so this intermediate parameter is used as the value of the difference between
            # them. The value of the 'trailing_stop_positive_offset' is constructed in the
            # generate_trailing_params() method.
            # This is similar to the hyperspace dimensions used for constructing the ROI tables.
            SKDecimal(
                cls.trailing_stop_positive_offset_min_value,
                cls.trailing_stop_positive_offset_max_value,
                decimals=3,
                name="trailing_stop_positive_offset_p1",
            ),
            Categorical([True, False], name="trailing_only_offset_is_reached"),
        ]
