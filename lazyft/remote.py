import os
import shutil
import tempfile
from pathlib import Path
from typing import Iterable, Optional, Union

import attr
import rapidjson
import sh
from freqtrade.data.btanalysis import load_trades_from_db

from lazyft import logger, paths
from lazyft.config import Config
from lazyft.models import StrategyBackup
from lazyft.models.remote import Environment, RemoteBotInfo, RemotePreset
from lazyft.reports import get_hyperopt_repo
from lazyft.strategy import Strategy, create_strategy_params_filepath, get_file_name

DEBUG = False
RUN_MODES = ["dry", "live"]
remotes_file = paths.BASE_DIR.joinpath("remotes.json")
if remotes_file.exists():
    remotes_dict = rapidjson.loads(remotes_file.read_text())
    remote_preset = {k: RemotePreset(**v) for k, v in remotes_dict.items()}


# remote_preset = dict(
#     vps=RemotePreset(
#         'raphael@calibre.raphaelnanje.me', '/home/raphael/freqtrade/', 51111
#     ),
#     pi=RemotePreset('pi@pi4.local', '/home/pi/freqtrade/'),
# )


@attr.s
class RemoteBot:
    bot_id: int = attr.ib()
    _preset: str = attr.ib(default="vps")
    _env: Optional[Environment] = None
    _config: Optional[Config] = None

    @property
    def tools(self):
        return RemoteTools(self.preset)

    @property
    def config(self) -> Config:
        self._config = self._config or self.tools.get_config(self.bot_id)
        return self._config

    @property
    def preset(self):
        return remote_preset[self._preset]

    @property
    def info(self):
        return RemoteBotInfo(self.bot_id)

    @property
    def env(self) -> Environment:
        if self._env:
            return self._env
        env_file = self.fetch_file(".env")
        env_file_text = env_file.read_text()
        # noinspection PyTypeChecker
        env = self._env = Environment(
            dict(tuple(e.split("=")) for e in env_file_text.split()), env_file
        )
        return env

    def print_logs(self, n_lines: int = 20):
        project_dir = self.preset.path + RemoteTools.FORMATTABLE_BOT_STRING.format(self.bot_id)
        command = f"cd {project_dir} && docker-compose logs --tail {n_lines}"
        sh.ssh(
            [self.preset.address, "-p", self.preset.port, " ".join(command.split())],
            _err=lambda o: print(o.strip()),
            _out=lambda o: print(o.strip()),
        )

    def refresh(self):
        self._config = None
        self._env = None

    def restart(self, build=False):
        self.tools.restart_bot(self.bot_id, build=build)

    def stop(self):
        self.tools.stop_bot(self.bot_id)

    def set_run_mode(self, mode: str):
        mode = mode.lower()
        assert mode in RUN_MODES, "%s not in %r" % (mode, RUN_MODES)
        dry_run = mode == "dry"
        logger.info("Setting run mode to %s" % mode)

        self.env.data["FREQTRADE__DRY_RUN"] = dry_run
        self.env.save()
        self.send_file(self.env.file, ".env")

    def set_strategy(self, strategy: str, id: str = ""):
        logger.info(f'Setting strategy for bot {self.bot_id} to "{strategy}" with id "{id}"...')
        self.tools.update_remote_strategy(self.bot_id, strategy, id)
        self.env.data["STRATEGY"] = strategy
        self.env.data["ID"] = id
        self.env.save()
        self.send_file(self.env.file, ".env")
        logger.info(f"Strategy for bot #{self.bot_id} set to {strategy} with id {id}")

    def get_trades(self):
        """Get trades using the currently configured DB_FILE in the env"""
        # get name of db file
        file_name = self.env.data["DB_FILE"]
        # get db file from remote
        db_path = self.fetch_file("user_data/" + file_name)
        if not db_path:
            return
        # create df from db
        df = load_trades_from_db("sqlite:///" + str(db_path))
        df.open_date = df.open_date.apply(lambda d: d.strftime("%x %X"))
        df.close_date = df.close_date.apply(lambda d: d.strftime("%x %X"))
        return df

    def update_config(self, update: dict):
        """Update the remote config with the passed dictionary

        Args:
            update (dict): A dictionary with the values to update
        """
        current_config = self.config
        current_config.update(update)
        self.save_config()

    def save_config(self):
        self.config.save()
        self.send_file(str(self.config), "user_data")

    def update_whitelist(self, whitelist: Iterable[str], append: bool = False):
        """
        Retrieve a local copy of specified bots remote config, update its whitelist, and send it
        back to the bot.
        """
        self.config.update_whitelist_and_save(whitelist, append=append)
        self.send_file(str(self.config), "user_data")

    def update_blacklist(self, blacklist: Iterable[str], append: bool = True):
        """
        Retrieve a local copy of specified bots remote config, update its whitelist, and send it
        back to the bot.
        """
        self.config.update_blacklist(blacklist, append=append)
        self.config.save()
        self.send_file(str(self.config), "user_data")

    def update_ensemble(self, strategies: Iterable[Strategy]):
        tmp_dir = tempfile.mkdtemp()
        path = Path(tmp_dir, "ensemble.json")
        path.write_text(rapidjson.dumps([s.name for s in strategies]))
        logger.info("New ensemble is %s", strategies)
        self.send_file(path, "user_data/strategies/ensemble.json")

    def send_file(self, local_path: Union[str, Path], remote_path: Union[str, Path]):
        return self.tools.send_file(self.bot_id, local_path, remote_path)

    def fetch_file(self, remote_path: Union[str, Path], local_path: Union[str, Path] = None):
        return self.tools.fetch_file(self.bot_id, remote_path, local_path)


@attr.s
class RemoteTools:
    preset: RemotePreset = attr.ib()
    FORMATTABLE_BOT_STRING = "freqtrade-bot{}"

    tmp_files = []

    @property
    def address(self):
        return self.preset.address

    @property
    def path(self):
        return self.preset.path

    def update_strategy_params(self, bot_id: int, strategy: str, id: str):
        logger.debug('[Strategy Params] "{}" -> "{}.json"', strategy, id)
        # load path of params
        # create the remote path to save as
        tmp_dir = tempfile.mkdtemp()
        local_params = Path(tmp_dir, "params.json")
        local_params.write_text(rapidjson.dumps(get_hyperopt_repo().get(id).parameters))
        remote_path = f"user_data/strategies/" f"{create_strategy_params_filepath(strategy).name}"
        # send the local params to the remote path
        self.send_file(bot_id, local_params, remote_path)

    def update_remote_bot_whitelist(
        self, bot_id: int, whitelist: Iterable[str], append: bool = False
    ):
        """
        Retrieve a local copy of specified bots remote config, update its whitelist, and send it
        back to the bot.
        """
        config = self.get_config(bot_id)
        config.update_whitelist_and_save(whitelist, append=append)
        config.save()
        self.send_file(bot_id, str(config), "user_data")

    def get_config(self, bot_id: int) -> Config:
        return Config(self.fetch_file(bot_id, "user_data/config.json"))

    def update_remote_strategy(
        self,
        bot_id: int,
        strategy_name: str,
        hyperopt_id: str = "",
    ):
        strategy_file_name = get_file_name(strategy=strategy_name)
        if not strategy_file_name:
            raise FileNotFoundError("Could not find strategy file that matches %s" % strategy_name)
        strategy_path = Path(paths.STRATEGY_DIR, strategy_file_name)
        if hyperopt_id:
            hash = get_hyperopt_repo().get(hyperopt_id).strategy_hash
            if hash:
                logger.info(f'Sending "{strategy_name}" using strategy hash "{hash}"')
                # create tmp dir
                tmp_dir = tempfile.mkdtemp()
                strategy_path = Path(tmp_dir, strategy_file_name)
                StrategyBackup.load_hash(hash).export_to(strategy_path)
            self.update_strategy_params(bot_id, strategy_name, hyperopt_id)
        self.send_file(
            bot_id,
            strategy_path,
            "user_data/strategies/",
        )
        strategy_path.unlink()

    def send_file(self, bot_id: int, local_path: Union[str, os.PathLike[str]], remote_path: str):
        """

        Args:
            bot_id:
            local_path: Where to save the fetched file. Defaults to /tmp
            remote_path: The relative location of a remote file to fetch

        Returns:

        """
        logger.debug('[send] "{}" -> bot {}', local_path, bot_id)
        self.rsync(local_path, self.format_remote_path(bot_id, remote_path))

    def fetch_file(self, bot_id: int, remote_path: str, local_path: Optional[Path] = None):
        """

        Args:
            bot_id:
            remote_path: The relative location of a remote file to fetch
            local_path: Where to save the fetched file. Defaults to /tmp

        Returns: Path of local copy of fetched file

        """
        logger.debug('[fetch] "{}" <- bot {}', remote_path, bot_id)
        if not local_path:
            temp = tempfile.mkdtemp(prefix="lazyft")
            local_path = Path(temp)
            self.tmp_files.append(local_path)
        try:
            self.rsync(
                self.format_remote_path(bot_id, str(remote_path)),
                local_path,
                fetch=True,
            )
        except sh.ErrorReturnCode_23:
            logger.debug("{} not found in remote.", remote_path)
            return None

        return Path(local_path, Path(remote_path).name)

    def format_remote_path(self, bot_id: int, path: str) -> Path:
        return Path(self.path, self.FORMATTABLE_BOT_STRING.format(bot_id), path)

    def rsync(self, origin: os.PathLike[str], destination: os.PathLike[str], fetch=False):
        if fetch:
            origin = f"{self.address}:{origin}"
        else:
            destination = f"{self.address}:{destination}"
        pre_command = ["-ai", origin, destination]
        if any(self.preset.opt_port):
            pre_command = self.preset.opt_port + pre_command
        command = [str(s) for s in pre_command]
        log = logger.debug if DEBUG else logger.info
        log('[sh] "rsync {}"', " ".join(command))
        sh.rsync(
            command,
            _err=lambda o: log(o.strip()),
            _out=lambda o: log(o.strip()),
        )

    def delete_strategy_params(self, bot_id: int, strategy: str):
        project_dir = self.path + self.FORMATTABLE_BOT_STRING.format(bot_id)
        params_file = create_strategy_params_filepath(strategy)
        command = f"cd {project_dir};rm -vf user_data/strategies/{params_file.name}"

        sh.ssh(
            [self.address, " ".join(command.split())],
            _err=lambda o: logger.info(o.strip()),
            _out=lambda o: logger.info(o.strip()),
        )

    def restart_bot(self, bot_id: int, build=False):
        logger.debug("[restart bot] {}", bot_id)
        project_dir = self.path + self.FORMATTABLE_BOT_STRING.format(bot_id)
        command = f"cd {project_dir} && docker-compose --ansi never up  -d"
        if build:
            command += " --build"
        logger.debug("Running ssh {}", command)
        sh.ssh(
            [f"-p {self.preset.port}", self.address, " ".join(command.split())],
            _err=lambda o: logger.info(o.strip()),
            _out=lambda o: logger.info(o.strip()),
        )

    def stop_bot(self, bot_id: int):
        logger.debug("[stop bot] {}", bot_id)
        project_dir = self.path + self.FORMATTABLE_BOT_STRING.format(bot_id)
        command = f"cd {project_dir} && docker-compose --ansi never down"
        logger.debug("Running ssh {}", command)
        sh.ssh(
            [f"-p {self.preset.port}", self.address, " ".join(command.split())],
            _err=lambda o: logger.info(o.strip()),
            _out=lambda o: logger.info(o.strip()),
        )

    @classmethod
    def delete_temp_files(cls):
        while cls.tmp_files:
            shutil.rmtree(cls.tmp_files.pop())


if __name__ == "__main__":
    bot1 = RemoteBot(1, "vps")
    bot2 = RemoteBot(2, "pi")
    bot3 = RemoteBot(3, "pi")
    bot4 = RemoteBot(4, "pi")
    bot5 = RemoteBot(5, "pi")

    bot = bot2
    bot.set_strategy("BatsContest")
    bot.set_run_mode("dry")
    print(bot.env)
    bot.restart()
