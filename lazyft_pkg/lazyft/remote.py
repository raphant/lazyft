import os
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional, Union

import sh

from lazyft import logger, paths
from lazyft.config import Config
from lazyft.parameters import Parameter
from lazyft.strategy import Strategy


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
    REMOTE_ADDR = 'raphael@calibre.raphaelnanje.me'
    FT_MAIN_FOLDER = '/home/raphael/freqtrade/'
    FORMATTABLE_BOT_STRING = 'freqtrade-bot{}'

    tmp_files = []

    @classmethod
    def update_strategy_params(cls, bot_id: int, strategy: str, id: str):
        logger.debug('[Strategy Params] "{}" -> "{}.json"', strategy, id)
        # load path of params
        local_params = Parameter.get_path_of_params(id)
        # create the remote path to save as
        remote_path = f'user_data/strategies/{Strategy.create_strategy_params_filepath(strategy).name}'
        # send the local params to the remote path
        cls.send_file(bot_id, local_params, remote_path)

    @classmethod
    def update_remote_bot_whitelist(
        cls, bot_id: int, whitelist: Iterable[str], append: bool = False
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
        strategy_id: str = '',
    ):
        strategy_file_name = Strategy.get_file_name(strategy=strategy_name)
        if not strategy_file_name:
            raise FileNotFoundError(
                'Could not find strategy file that matches %s' % strategy_name
            )
        env = RemoteBotInfo(bot_id).env
        env.data['STRATEGY'] = strategy_name
        new_text = '\n'.join([f'{k}={v}' for k, v in env.data.items()]) + '\n'
        env.file.write_text(new_text)
        cls.send_file(bot_id, env.file, '.env')

        cls.send_file(
            bot_id,
            Path(paths.STRATEGY_DIR, strategy_file_name),
            'user_data/strategies/',
        )
        if strategy_id:
            cls.update_strategy_params(bot_id, strategy_name, strategy_id)

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
        logger.debug('[send] "{}" -> bot {}', local_path, bot_id)
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
        logger.debug('[fetch] "{}" <- bot {}', remote_path, bot_id)
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
            logger.debug('{} not found in remote.', remote_path)
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
        command = [str(s) for s in ['-ai', origin, destination]]
        logger.debug('[sh] "rsync {}"', ' '.join(command))
        sh.rsync(
            command,
            _err=lambda o: logger.debug(o.strip()),
            _out=lambda o: logger.debug(o.strip()),
        )

    @classmethod
    def delete_strategy_params(cls, bot_id: int, strategy: str):
        project_dir = cls.FT_MAIN_FOLDER + cls.FORMATTABLE_BOT_STRING.format(bot_id)
        params_file = Strategy.create_strategy_params_filepath(strategy)
        command = f'cd {project_dir};rm -vf user_data/strategies/{params_file.name}'

        sh.ssh(
            [cls.REMOTE_ADDR, ' '.join(command.split())],
            _err=lambda o: logger.info(o.strip()),
            _out=lambda o: logger.info(o.strip()),
        )

    @classmethod
    def restart_bot(cls, bot_id: int):
        logger.debug('[restart bot] {}', bot_id)
        project_dir = cls.FT_MAIN_FOLDER + cls.FORMATTABLE_BOT_STRING.format(bot_id)
        command = (
            f'cd {project_dir} && docker-compose --no-ansi down; '
            f'docker-compose --no-ansi up  -d'
        )
        sh.ssh(
            [cls.REMOTE_ADDR, ' '.join(command.split())],
            _err=lambda o: logger.info(o.strip()),
            _out=lambda o: logger.info(o.strip()),
        )

    @classmethod
    def delete_temp_files(cls):
        while cls.tmp_files:
            shutil.rmtree(cls.tmp_files.pop())


if __name__ == '__main__':
    # logger.setLevel('DEBUG')
    # Remote.update_remote_strategy(4, 'BollingerBands2', 'bollingerbands2.py')
    # Remote.send_file(4, constants.BASE_DIR.joinpath('logs.log'), './')
    # Remote.restart_bot(4)
    Remote.update_remote_strategy(2, 'TestBinH', 'jTc6jx')
    # Remote.delete_strategy_params(2, 'TestBinH')
