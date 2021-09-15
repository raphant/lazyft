from __future__ import absolute_import

from celery import Celery

app = Celery(
    'background',
    broker=f'redis://localhost/0',
    backend=f'redis://localhost/1',
    include=['lazyft.background.tasks'],
)
