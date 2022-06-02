from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Optional, Union

from loguru import logger
from rich.syntax import Syntax
from sqlmodel import Field, Session, SQLModel, select

from lazyft import strategy
from lazyft.database import engine


class StrategyBackup(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=False)
    text: str = Field(index=False)
    hash: str = Field(index=True)
    date: datetime = Field(default_factory=datetime.now)

    def save(self):
        with Session(engine) as session:
            session.add(self)
            session.commit()
            session.refresh(self)
        return self

    def export_to(self, path: Union[Path, str]) -> Path:
        """
        Export the strategy to a file or directory.

        :param path: A file or a directory
        :return: The path to the exported file
        """
        if isinstance(path, str):
            path = Path(path)
        if path.is_dir():
            path = path / strategy.get_file_name(self.name)
        path.write_text(self.text)
        logger.info(f"Exported strategy {self.name} with hash {self.hash} to {path}")
        return path

    def print(self):
        from lazyft import print

        print(Syntax(self.text, lexer_name="python"))

    @classmethod
    def load_hash(cls, hash: str):
        with Session(engine) as session:
            statement = select(cls).where(cls.hash == hash)
            return session.exec(statement).first()

    @classmethod
    def first(cls):
        with Session(engine) as session:
            statement = select(cls).order_by(cls.date)
            return session.exec(statement).first()


SQLModel.metadata.create_all(engine)
