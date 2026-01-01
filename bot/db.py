import asyncpg
import os


async def connect_db():
    """
    Establish and return a connection to the PostgreSQL database using environment variables.
    """
    return await asyncpg.connect(
        host=os.getenv("DB_HOST"),
        port=int(os.getenv("DB_PORT")),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        database=os.getenv("DB_NAME")
    )
