import os
import shutil
import tempfile
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Iterable, Optional, Union

import attr
import rapidjson
import sh
from freqtrade.data.btanalysis import load_trades_from_db

from lazyft import logger, paths
from lazyft.config import Config
from lazyft.models import RemotePreset, Environment, RemoteBotInfo, Strategy
from lazyft.strategy import StrategyTools
from lazyft.util import ParameterTools

RUN_MODES = ["dry", "live"]
remotes_file = paths.BASE_DIR.joinpath("remotes.json")
if remotes_file.exists():
    remotes_dict = rapidjson.loads(remotes_file.read_text())
    remote_preset = {k: RemotePreset(**v) for k, v in remotes_dict.items()}
else:
    logger.warning("{} does not exist. Remotes not loaded", remotes_file)


# remote_preset = dict(
#     vps=RemotePreset(
#         'raphael@calibre.raphaelnanje.me', '/home/raphael/freqtrade/', 51111
#     ),
#     pi=RemotePreset('pi@pi4.local', '/home/pi/freqtrade/'),
# )
tmp_dir = TemporaryDirectory()


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
        env_file = self.tools.fetch_file(self.bot_id, ".env")
        env_file_text = env_file.read_text()
        # noinspection PyTypeChecker
        env = self._env = Environment(
            dict(tuple(e.split("=")) for e in env_file_text.split()), env_file
        )
        return env

    def print_logs(self, n_lines: int = 20):
        project_dir = self.preset.path + RemoteTools.FORMATTABLE_BOT_STRING.format(
            self.bot_id
        )
        command = f"cd {project_dir} && docker-compose logs --tail {n_lines}"
        sh.ssh(
            [self.preset.address, "-p", self.preset.port, " ".join(command.split())],
            _err=lambda o: print(o.strip()),
            _out=lambda o: print(o.strip()),
        )

    def refresh(self):
        self._config = None
        self._env = None

    def restart(self):
        self.tools.restart_bot(self.bot_id)

    def set_run_mode(self, mode: str):
        logger.info("Setting run mode to %s" % mode)
        mode = mode.lower()
        assert mode in RUN_MODES, "%s not in %r" % (mode, RUN_MODES)
        # update config
        self.update_config({"dry_run": mode == "dry"})
        # update env
        env = self.env.data
        env["RUN_MODE"] = mode
        self.sync_remote_env()
        self.save_env(env)

    def set_strategy(self, strategy: str, id: str = ""):
        self.env.data["STRATEGY"] = strategy
        self.env.data["ID"] = id
        self.sync_remote_env()
        self.tools.update_remote_strategy(self.bot_id, strategy, id)
        self.save_env()

    def save_env(self, new_env: dict = None):
        if not new_env:
            assert self._env, "No new_env passed and no loaded env"
            new_env = self.env.data
        new_text = "\n".join([f"{k}={v}" for k, v in new_env.items()]) + "\n"
        self.env.file.write_text(new_text)
        self.tools.send_file(self.bot_id, self.env.file, ".env")

    def sync_remote_env(self):
        """No save."""
        mode = self.env.data.get("RUN_MODE", "dry")
        strategy = self.env.data["STRATEGY"]
        id = self.env.data["ID"]
        db_file = f"tradesv3.{strategy}-{mode}-{id}".rstrip("-") + ".sqlite"

        self.env.data["DB_FILE"] = db_file

    def get_trades(self):
        """Get trades using the currently configured DB_FILE in the env"""
        # get name of db file
        file_name = self.env.data["DB_FILE"]
        # get db file from remote
        db_path = self.tools.fetch_file(self.bot_id, "user_data/" + file_name)
        if not db_path:
            return
        # create df from db
        df = load_trades_from_db("sqlite:///" + str(db_path))
        df.open_date = df.open_date.apply(lambda d: d.strftime('%x %X'))
        df.close_date = df.close_date.apply(lambda d: d.strftime('%x %X'))
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
        self.tools.send_file(self.bot_id, str(self.config), "user_data")

    def update_whitelist(self, whitelist: Iterable[str], append: bool = False):
        """
        Retrieve a local copy of specified bots remote config, update its whitelist, and send it
        back to the bot.
        """
        self.config.update_whitelist_and_save(whitelist, append=append)
        self.tools.send_file(self.bot_id, str(self.config), "user_data")

    def update_blacklist(self, blacklist: Iterable[str], append: bool = True):
        """
        Retrieve a local copy of specified bots remote config, update its whitelist, and send it
        back to the bot.
        """
        self.config.update_blacklist(blacklist, append=append)
        self.config.save()
        self.tools.send_file(self.bot_id, str(self.config), "user_data")

    def update_ensemble(self, strategies: Iterable[Strategy]):
        path = Path(tmp_dir.name, 'ensemble.json')
        path.write_text(rapidjson.dumps([s.name for s in strategies]))
        logger.info('New ensemble is %s', strategies)
        self.tools.send_file(self.bot_id, path, 'user_data/strategies/ensemble.json')


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
        local_params = Path(tmp_dir.name, 'params.json')
        local_params.write_text(rapidjson.dumps(ParameterTools.get_parameters(id)))
        remote_path = (
            f"user_data/strategies/"
            f"{StrategyTools.create_strategy_params_filepath(strategy).name}"
        )
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
        strategy_id: str = "",
    ):
        strategy_file_name = StrategyTools.get_file_name(strategy=strategy_name)
        if not strategy_file_name:
            raise FileNotFoundError(
                "Could not find strategy file that matches %s" % strategy_name
            )

        self.send_file(
            bot_id,
            Path(paths.STRATEGY_DIR, strategy_file_name),
            "user_data/strategies/",
        )
        if strategy_id:
            self.update_strategy_params(bot_id, strategy_name, strategy_id)

    def send_file(
        self, bot_id: int, local_path: Union[str, os.PathLike[str]], remote_path: str
    ):
        """

        Args:
            bot_id:
            local_path: Where to save the fetched file. Defaults to /tmp
            remote_path: The relative location of a remote file to fetch

        Returns:

        """
        logger.debug('[send] "{}" -> bot {}', local_path, bot_id)
        self.rsync(local_path, self.format_remote_path(bot_id, remote_path))

    def fetch_file(
        self, bot_id: int, remote_path: str, local_path: Optional[Path] = None
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

    def rsync(
        self, origin: os.PathLike[str], destination: os.PathLike[str], fetch=False
    ):
        if fetch:
            origin = f"{self.address}:{origin}"
        else:
            destination = f"{self.address}:{destination}"
        pre_command = ["-ai", origin, destination]
        if any(self.preset.opt_port):
            pre_command = self.preset.opt_port + pre_command
        command = [str(s) for s in pre_command]

        logger.debug('[sh] "rsync {}"', " ".join(command))
        sh.rsync(
            command,
            _err=lambda o: logger.debug(o.strip()),
            _out=lambda o: logger.debug(o.strip()),
        )

    def delete_strategy_params(self, bot_id: int, strategy: str):
        project_dir = self.path + self.FORMATTABLE_BOT_STRING.format(bot_id)
        params_file = StrategyTools.create_strategy_params_filepath(strategy)
        command = f"cd {project_dir};rm -vf user_data/strategies/{params_file.name}"

        sh.ssh(
            [self.address, " ".join(command.split())],
            _err=lambda o: logger.info(o.strip()),
            _out=lambda o: logger.info(o.strip()),
        )

    def restart_bot(self, bot_id: int):
        logger.debug("[restart bot] {}", bot_id)
        project_dir = self.path + self.FORMATTABLE_BOT_STRING.format(bot_id)
        command = (
            f"cd {project_dir} && docker-compose --no-ansi down; "
            f"docker-compose --no-ansi up  -d"
        )
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
    bot3 = RemoteBot(3, "pi")
    bot4 = RemoteBot(4, "vps")
    bot5 = RemoteBot(5, "pi")

    bot = bot3
    bot.set_strategy("NotAnotherSMAOffsetStrategyHOv3")
    bot.set_run_mode("live")
    print(bot.env)
    bot.restart()
