from typing import Annotated

from fastapi import Depends
from sqlmodel import Session, SQLModel

from .db import engine

def get_session():
    with Session(engine) as session:
        yield session


SessionDep = Annotated[Session, Depends(get_session)]


def create_db_and_tables():
    SQLModel.metadata.create_all(engine)
