import sqlalchemy as db

from lazyft.paths import BASE_DIR

engine = db.create_engine(f'sqlite:///{BASE_DIR.joinpath("library.db")}')
connection = engine.connect()
metadata = db.MetaData()
census = db.Table('census', metadata, autoload=True, autoload_with=engine)
print(census.columns.keys())


class BacktestReport:
    pass
