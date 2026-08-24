from collections.abc import Generator

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings

settings = get_settings()

engine = create_engine(settings.database_url, pool_pre_ping=True) #Connection Management
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False) #Session Management


def get_db_session() -> Generator[Session, None, None]:

    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def verify_database_connection() -> None:

    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))
