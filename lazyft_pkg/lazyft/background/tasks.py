import time

import rapidjson
from celery.contrib.abortable import AbortableTask
from loguru import logger

from .celery import app
from .. import hyperopt, paths
from ..hyperopt import HyperoptRunner
from ..command_parameters import HyperoptParameters


@app.task(bind=True, base=AbortableTask)
def do_hyperopt(self, task_info: dict):
    parameters_dict, task_id = task_info.values()
    data = {}
    if not paths.CELERY_TASKS_FILE.exists():
        paths.CELERY_TASKS_FILE.write_text('{}')
    else:
        data = rapidjson.loads(paths.CELERY_TASKS_FILE.read_text())
    data[task_id] = {'parameters': parameters_dict, 'running': True}
    paths.CELERY_TASKS_FILE.write_text(rapidjson.dumps(data))
    commands = hyperopt.create_commands(HyperoptParameters(**parameters_dict))
    runner = HyperoptRunner(commands[0], task_id=task_id, celery=True, autosave=True)
    runner.execute(background=False)
    return runner.report.report_id


if __name__ == '__main__':
    print(app.AsyncResult('0dda023d-4429-4598-9dcb-b366b644cff5'))
