import os
import urllib.parse

from sqlmodel import create_engine
from sqlalchemy.engine.url import URL

DATABASE = {
    "drivername": "postgresql",
    "username": os.getenv("POSTGRES_USER"),
    "password": urllib.parse.quote_plus(os.getenv("POSTGRES_PASSWORD")),
    "host": os.getenv("POSTGRES_HOST", "localhost"),
    "port": os.getenv("POSTGRES_PORT", "5432"),
    "database": os.getenv("POSTGRES_DB"),
}

DATABASE_URL = URL.create(**DATABASE)

engine = create_engine(DATABASE_URL)
