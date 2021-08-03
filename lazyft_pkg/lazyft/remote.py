import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional, Union

import sh

from lazyft import constants, logger
from lazyft.config import Config


@dataclass
class RemoteBotInfo:
    bot_id: int

    @property
    def strategy(self) -> str:
        return self.env['STRATEGY']

    @property
    def config(self) -> Config:
        return Remote.get_config(self.bot_id)

    @property
    def env(self) -> dict:
        env_file = Remote.fetch_file(self.bot_id, '.env')
        env_file_text = env_file.read_text()
        # noinspection PyTypeChecker
        return dict(tuple(e.split('=')) for e in env_file_text.split())


class Remote:
    REMOTE_ADDR = 'pi@pi4.local'
    CONFIG_PATH = '/home/pi/freqtrade/freqtrade-bot{}/user_data/config.json'
    BOT_FOLDER = '/home/pi/freqtrade/freqtrade-bot{}/'

    @classmethod
    def update_remote_bot_whitelist(
        cls, whitelist: Iterable[str], bot_id: int, append: bool = False
    ):
        """
        Retrieve a local copy of specified bots remote config, update its whitelist, and send it
        back to the bot.
        """
        config = cls.get_config(bot_id)
        config.update_whitelist(whitelist, append=append)
        config.save()
        cls.send_file(bot_id, str(config), 'user_data')

    @classmethod
    def get_config(cls, bot_id: int) -> Config:
        return Config(cls.fetch_file(bot_id, 'user_data/config.json'))

    @classmethod
    def update_remote_strategy(
        cls, bot_id: int, strategy_name: str, strategy_file_name: str
    ):
        logger.debug('Updating ')
        env_file = cls.fetch_file(bot_id, '.env')
        env_file_text = env_file.read_text()
        # noinspection PyTypeChecker
        env_dict = dict(tuple(e.split('=')) for e in env_file_text.split())
        env_dict['STRATEGY'] = strategy_name
        new_text = '\n'.join([f'{k}={v}' for k, v in env_dict.items()]) + '\n'
        env_file.write_text(new_text)
        cls.send_file(bot_id, env_file, '.env')
        cls.send_file(
            bot_id,
            Path(constants.STRATEGY_DIR, strategy_file_name),
            'user_data/strategies/',
        )
        cls.send_file(
            bot_id,
            Path(constants.STRATEGY_DIR, 'custom_util.py'),
            'user_data/strategies/',
        )

    @classmethod
    def send_file(
        cls, bot_id: int, local_path: Union[str, os.PathLike[str]], remote_path: str
    ):
        logger.debug('Sending copy of %s to bot %s', local_path, bot_id)
        cls.rsync(local_path, cls.format_remote_path(bot_id, remote_path))

    @classmethod
    def fetch_file(
        cls, bot_id: int, remote_path: str, local_dir: Optional[Path] = None
    ):
        """

        Args:
            bot_id:
            remote_path: The relative location of a remote file to fetch
            local_dir: Where to save the fetched file. Defaults to /tmp

        Returns: Path of local copy of fetched file

        """
        logger.debug('Fetching local copy of %s from bot %s', remote_path, bot_id)
        if not local_dir:
            temp = tempfile.mkdtemp(prefix='lazyft')
            local_dir = Path(temp)
        cls.rsync(
            cls.format_remote_path(bot_id, str(remote_path)),
            local_dir,
            fetch=True,
        )
        assert local_dir.exists(), 'Failed to fetch remote file %s' % remote_path

        return Path(local_dir, Path(remote_path).name)

    @classmethod
    def format_remote_path(cls, bot_id: int, path: str) -> Path:
        return Path(cls.BOT_FOLDER.format(bot_id), path)

    @classmethod
    def rsync(
        cls, origin: os.PathLike[str], destination: os.PathLike[str], fetch=False
    ):
        if fetch:
            origin = f'{cls.REMOTE_ADDR}:{origin}'
        else:
            destination = f'{cls.REMOTE_ADDR}:{destination}'
        command = [str(s) for s in ['-a', origin, destination]]
        logger.debug('Running command: rsync %s', ' '.join(command))
        sh.rsync(
            command,
            _err=lambda o: logger.error(o.strip()),
            _out=lambda o: logger.info(o.strip()),
        )

    @classmethod
    def restart_bot(cls, bot_id: int):
        sh.ssh(
            [cls.REMOTE_ADDR, f'docker restart freqtrade-bot{bot_id}_freqtrade_run_1'],
            _err=logger.error,
            _out=logger.info,
        )


if __name__ == '__main__':
    Remote.update_remote_strategy(4, 'BollingerBands2', 'bollingerbands2.py')
