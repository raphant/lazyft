import operator

from technical import qtpylib

op_map = {
    '<': operator.lt,
    '>': operator.gt,
    '<=': operator.le,
    '>=': operator.ge,
    'crossed_above': qtpylib.crossed_above,
    'crossed_below': qtpylib.crossed_below,
}
