import os
from lazyft import logger
from pushbullet import Pushbullet

api_key = os.getenv('PB_TOKEN')
pb = Pushbullet(api_key)


def notify_pb(title: str, body: str):
    """Sends a PushBullet notification. Uses PB_TOKEN from .env"""
    try:
        return pb.push_note(title, body)
    except Exception as e:
        logger.exception(e)
