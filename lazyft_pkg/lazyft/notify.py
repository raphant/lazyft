"""
Provides notification functions
"""
import os
import socket

from lazyft import logger
from pushbullet import Pushbullet, PushError, PushbulletError

import telegram

api_key = os.getenv('PB_TOKEN')


PUSHER_DEVICE_ID = '50012'

hostname = socket.gethostname()
ip = socket.gethostbyname(hostname)


class State:
    REACHED_API_LIMIT = False


try:
    pb = Pushbullet(api_key)
except PushbulletError as e:
    if str(e) == 'Too Many Requests, you have been ratelimited':
        logger.error(str(e))
        State.REACHED_API_LIMIT = True

def notify_pb(title: str, body: str):
    """Sends a PushBullet notification. Uses PB_TOKEN from .env"""
    if State.REACHED_API_LIMIT:
        return
    try:
        return pb.push_note(title, body)
    except PushError as e:
        if 'pushbullet_pro_required' in str(e) or 'ratelimited' in str(e):
            State.REACHED_API_LIMIT = True
            logger.error('Reached PushBullet API limit.')
    except Exception as e:
        logger.exception(e)


def notify_telegram(
    title: str,
    text: str,
    markdown: bool = True,
):
    msg = f"{title}\n{' -' * 10}\n{text}"
    bot = telegram.Bot(token=os.getenv('TELEGRAM_NOTIFY_TOKEN', ""))
    bot.send_message(
        chat_id=os.getenv('TELEGRAM_NOTIFY_CHAT_ID'),
        text=msg,
        parse_mode=telegram.ParseMode.MARKDOWN if markdown else None,
    )


if __name__ == '__main__':
    # notify_pb('Test', 'Test')
    notify_telegram('Test', 'Test')
