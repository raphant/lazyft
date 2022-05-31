from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from pydantic import BaseModel


class RemotePreset(BaseModel):
    address: str
    path: str
    port: int = 22

    @property
    def opt_port(self):
        if self.port != 22:
            return ["-e", f"ssh -p {self.port}"]
        return [""]


@dataclass
class Environment:
    data: dict
    file: Path

    def save(self, new_data: dict = None):
        """
        It saves the environment to a file.

        :param new_data: dict = None
        :type new_data: dict
        """
        data = new_data or self.data
        self.update_db_file_name()
        new_text = "\n".join([f"{k}={v}" for k, v in data.items()]) + "\n"
        self.file.write_text(new_text)

    def update_db_file_name(self):
        """
        If the user has set the
        `FREQTRADE__DRY_RUN` environment variable to `True`, then the database file name
        will be `tradesv3.{strategy}-dry_run-id.sqlite`.

        If the user has set the
        `FREQTRADE__DRY_RUN` environment variable to `False`, then the database file name
        will be `tradesv3.{strategy}-live-id.sqlite`
        """
        mode = self.data.get("FREQTRADE__DRY_RUN", True)
        dry_run = "dry_run" if mode else "live"
        strategy = self.data["STRATEGY"]
        id = self.data["ID"]
        db_file = f"tradesv3.{strategy}-{dry_run}-{id}".rstrip("-") + ".sqlite"
        self.data["DB_FILE"] = db_file


@dataclass
class RemoteBotInfo:
    bot_id: int
    _env_file = None
    env: Environment

    @property
    def strategy(self) -> str:
        # noinspection PyUnresolvedReferences
        return self.env.data["STRATEGY"]
