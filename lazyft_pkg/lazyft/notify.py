import os
from lazyft import logger
from pushbullet import Pushbullet

api_key = os.getenv('PB_TOKEN')
pb = Pushbullet(api_key)


def notify(title: str, body: str):
    try:
        return pb.push_note(title, body)
    except Exception as e:
        logger.exception(e)
