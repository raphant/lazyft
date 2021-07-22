from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Iterable

import sh
from easyft.config import Config
from loguru import logger


class Remote:
    REMOTE_ADDR = 'pi@pi4.local'
    CONFIG_PATH = '/home/pi/freqtrade/freqtrade-bot{}/user_data/config.json'

    @classmethod
    def update_remote_bot_whitelist(cls, whitelist: Iterable[str], bot_id: int):
        """
        Retrieve a local copy of specified bots remote config, update its whitelist, and send it
        back to the bot.
        """
        temp = TemporaryDirectory()
        save_path = Path(temp.name, 'config.json').resolve()
        cls.rsync(cls.CONFIG_PATH.format(bot_id), str(save_path))
        assert save_path.exists()
        config = Config(save_path)
        config['exchange']['pair_whitelist'] = whitelist
        config.save()
        cls.rsync(str(save_path), cls.CONFIG_PATH.format(bot_id))

    @classmethod
    def rsync(cls, local: str, destination: str):
        sh.rsync(
            [
                '-a',
                local,
                f'{cls.REMOTE_ADDR}:{destination}',
            ],
            _err=logger.info,
            _out=logger.info,
        )

    @classmethod
    def restart_bot(cls, bot_id: int):
        sh.ssh(
            [cls.REMOTE_ADDR, f'docker restart freqtrade-bot{bot_id}_freqtrade_run_1'],
            _err=logger.info,
            _out=logger.info,
        )


if __name__ == '__main__':
    Remote.update_remote_bot_whitelist(['lololololololololololol'], 3)
