import json
from typing import Any

from lazyft import paths
from pydantic import BaseModel, Field
from pathlib import Path


class LftSettings(BaseModel):
    base_config_path: Path = None

    def save(self):
        paths.LAZYFT_SETTINGS_PATH.write_text(self.json(indent=2))

    @classmethod
    def load(cls):
        if paths.LAZYFT_SETTINGS_PATH.exists():
            return cls.parse_raw(paths.LAZYFT_SETTINGS_PATH.read_text())
        else:
            return cls()
