import time

from .celery import app
from .. import hyperopt
from ..hyperopt import HyperoptRunner
from ..command_parameters import HyperoptParameters


@app.task
def test(arg):
    time.sleep(5)
    print(arg)
    return arg


@app.task
def do_hyperopt(command_dict: dict):
    commands = hyperopt.create_commands(HyperoptParameters(**command_dict))
    runner = HyperoptRunner(commands[0])
    runner.execute()
    runner.save()
    return runner.report.report_id


if __name__ == '__main__':
    print(app.AsyncResult('0dda023d-4429-4598-9dcb-b366b644cff5'))
