"""Configuration: read database settings from environment variables / .env."""

from __future__ import annotations

import os

from dotenv import load_dotenv
from sqlalchemy.engine import URL

# Reads the .env file (if present) into environment variables.
# Variables that are already set (e.g. by Docker) are NOT overwritten.
load_dotenv()


def get_database_url() -> URL:

    return URL.create(
        drivername="postgresql+psycopg2",
        username=os.environ["POSTGRES_USER"],
        password=os.environ["POSTGRES_PASSWORD"],
        host=os.getenv("POSTGRES_HOST", "localhost"),
        port=int(os.getenv("POSTGRES_PORT", "5432")),
        database=os.environ["POSTGRES_DB"],
    )