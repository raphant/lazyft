import os
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional, Union

import rapidjson
import sh

from lazyft import constants, logger
from lazyft.config import Config

logger = logger.getChild('remote')


@dataclass
class Environment:
    data: dict
    file: Path


@dataclass
class RemoteBotInfo:
    bot_id: int
    _env_file = None

    @property
    def strategy(self) -> str:
        return self.env.data['STRATEGY']

    @property
    def config(self) -> Config:
        return Remote.get_config(self.bot_id)

    @property
    def env(self) -> Environment:
        env_file = Remote.fetch_file(self.bot_id, '.env')
        env_file_text = env_file.read_text()
        # noinspection PyTypeChecker
        return Environment(
            dict(tuple(e.split('=')) for e in env_file_text.split()), env_file
        )


class Remote:
    REMOTE_ADDR = 'pi@pi4.local'
    FT_MAIN_FOLDER = '/home/pi/freqtrade/'
    FORMATTABLE_BOT_STRING = 'freqtrade-bot{}'

    tmp_files = []

    @classmethod
    def update_strategy_id(cls, bot_id: int, strategy: str, id: str):
        logger.debug('[Strategy ID] "%s" -> "%s"', strategy, id)
        remote_path = 'user_data/strategies/strategy_ids.json'
        si = cls.fetch_file(bot_id, remote_path)
        assert si, 'Could not find "strategy_ids.json" in remote'
        si_loaded = rapidjson.loads(si.read_text())
        si_loaded[strategy] = id
        si.write_text(rapidjson.dumps(si_loaded))
        cls.send_file(bot_id, si, remote_path)

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
    def update_config(cls, bot_id: int, update: dict):
        current_config = cls.get_config(bot_id)
        current_config.update(update)
        current_config.save()
        cls.send_file(bot_id, str(current_config), 'user_data')

    @classmethod
    def get_config(cls, bot_id: int) -> Config:
        return Config(cls.fetch_file(bot_id, 'user_data/config.json'))

    @classmethod
    def update_remote_strategy(
        cls,
        bot_id: int,
        strategy_name: str,
        strategy_file_name: str = None,
        strategy_id: str = '',
    ):
        env = RemoteBotInfo(bot_id).env
        env.data['STRATEGY'] = strategy_name
        new_text = '\n'.join([f'{k}={v}' for k, v in env.data.items()]) + '\n'
        env.file.write_text(new_text)
        cls.send_file(bot_id, env.file, '.env')
        if strategy_file_name:
            cls.send_file(
                bot_id,
                Path(constants.STRATEGY_DIR, strategy_file_name),
                'user_data/strategies/',
            )
        # todo check if custom_util.py exists
        # if not cls.fetch_file(bot_id, 'user_data/strategies/custom_util.py'):
        #     logger.debug('custom_util.py not found, sending copy to bot %s', bot_id)
        cls.send_file(
            bot_id,
            Path(constants.STRATEGY_DIR, 'custom_util.py'),
            'user_data/strategies/',
        )
        if strategy_id:
            cls.update_strategy_id(bot_id, strategy_name, strategy_id)

    @classmethod
    def send_file(
        cls, bot_id: int, local_path: Union[str, os.PathLike[str]], remote_path: str
    ):
        """

        Args:
            bot_id:
            local_path: Where to save the fetched file. Defaults to /tmp
            remote_path: The relative location of a remote file to fetch

        Returns:

        """
        logger.debug('[send] "%s" -> bot %s', local_path, bot_id)
        cls.rsync(local_path, cls.format_remote_path(bot_id, remote_path))

    @classmethod
    def fetch_file(
        cls, bot_id: int, remote_path: str, local_path: Optional[Path] = None
    ):
        """

        Args:
            bot_id:
            remote_path: The relative location of a remote file to fetch
            local_path: Where to save the fetched file. Defaults to /tmp

        Returns: Path of local copy of fetched file

        """
        logger.debug('[fetch] "%s" <- bot %s', remote_path, bot_id)
        if not local_path:
            temp = tempfile.mkdtemp(prefix='lazyft')
            local_path = Path(temp)
            cls.tmp_files.append(local_path)
        try:
            cls.rsync(
                cls.format_remote_path(bot_id, str(remote_path)),
                local_path,
                fetch=True,
            )
        except sh.ErrorReturnCode_23:
            logger.debug('%s not found in remote.', remote_path)
            return None

        return Path(local_path, Path(remote_path).name)

    @classmethod
    def format_remote_path(cls, bot_id: int, path: str) -> Path:
        return Path(cls.FT_MAIN_FOLDER, cls.FORMATTABLE_BOT_STRING.format(bot_id), path)

    @classmethod
    def rsync(
        cls, origin: os.PathLike[str], destination: os.PathLike[str], fetch=False
    ):
        if fetch:
            origin = f'{cls.REMOTE_ADDR}:{origin}'
        else:
            destination = f'{cls.REMOTE_ADDR}:{destination}'
        command = [str(s) for s in ['-a', origin, destination]]
        logger.debug('[sh] "rsync %s"', ' '.join(command))
        sh.rsync(
            command,
            _err=lambda o: logger.debug(o.strip()),
            _out=lambda o: logger.info(o.strip()),
        )

    @classmethod
    def restart_bot(cls, bot_id: int):
        sh.ssh(
            [cls.REMOTE_ADDR, f'docker restart freqtrade_bot{bot_id}'],
            _err=logger.error,
            _out=logger.info,
        )

    @classmethod
    def delete_temp_files(cls):
        while cls.tmp_files:
            shutil.rmtree(cls.tmp_files.pop())


if __name__ == '__main__':
    logger.setLevel('DEBUG')
