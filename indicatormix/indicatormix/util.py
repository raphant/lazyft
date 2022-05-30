from datetime import timedelta

import pandas as pd


def string_to_timedelta(delta_string):
    # turn "2 days, HH:MM:SS" into a time delta
    if 'day' in delta_string:
        delta = timedelta(
            days=int(delta_string.split(' ')[0]),
            hours=int(delta_string.split(' ')[2].split(':')[0]),
            minutes=int(delta_string.split(' ')[2].split(':')[1]),
            seconds=int(delta_string.split(' ')[2].split(':')[2]),
        )
    else:
        # turn "HH:MM:SS" into a time delta
        delta = timedelta(
            hours=int(delta_string.split(':')[0]),
            minutes=int(delta_string.split(':')[1]),
            seconds=int(delta_string.split(':')[2]),
        )
    return delta


def normalize(series: pd.Series):
    return (series - series.min()) / (series.max() - series.min())
