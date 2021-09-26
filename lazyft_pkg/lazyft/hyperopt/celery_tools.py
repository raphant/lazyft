import signal
import uuid

import rapidjson
from celery.contrib.abortable import AbortableAsyncResult
from celery.result import AsyncResult

from lazyft import paths, hyperopt, logger
from lazyft.background.celery import app
from lazyft.command_parameters import HyperoptParameters
from lazyft.hyperopt import HyperoptRunner


class CeleryRunner:
    @staticmethod
    def celery_execute(parameters: HyperoptParameters):
        from lazyft.background.tasks import do_hyperopt

        task_id = str(uuid.uuid4())
        task_info = {'parameters': parameters.__dict__, 'task_id': task_id}
        result: AsyncResult = do_hyperopt.apply_async((task_info,), task_id=task_id)
        logger.info(
            'Running hyperopt through celery\nTask ID: {}\nParams: {}',
            task_id,
            parameters,
        )
        return result.id

    @staticmethod
    def load(task_id):
        task_info = rapidjson.loads(paths.CELERY_TASKS_FILE.read_text())[task_id]
        parameter_dict = task_info['parameters']
        params = HyperoptParameters(**parameter_dict)
        commands = hyperopt.create_commands(params)
        return HyperoptRunner(commands[0], task_id=task_id, loaded_from_celery=True)

    @staticmethod
    def get_running_hyperopt_id():
        return paths.CELERY_CURRENT_TASK_FILE.read_text()

    @staticmethod
    def stop():
        raise NotImplementedError()
        running_hyperopt_task_id = CeleryRunner.get_running_hyperopt_id()
        if not running_hyperopt_task_id:
            raise ValueError('Hyperopt Task not found')
        logger.info('Aborting "{}"', running_hyperopt_task_id)
        AbortableAsyncResult(running_hyperopt_task_id).revoke(
            terminate=True, signal='SIGINT'
        )
        # app.control.revoke(running_hyperopt_task_id, terminate=True, signal='SIGINT')

    @staticmethod
    def delete_task(task_id):
        logger.info('Removing task_id "{}" from celery', task_id)
        data = rapidjson.loads(paths.CELERY_TASKS_FILE.read_text())
        del data[task_id]
        paths.CELERY_TASKS_FILE.write_text(rapidjson.dumps(data))

    @staticmethod
    def clear_tasks():
        paths.CELERY_TASKS_FILE.write_text('{}')


if __name__ == '__main__':
    print(CeleryRunner.stop())
