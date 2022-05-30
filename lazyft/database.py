from sqlmodel import create_engine

from lazyft.paths import BASE_DIR

engine = create_engine(f'sqlite:///{BASE_DIR.joinpath("lazyft.db")}')
