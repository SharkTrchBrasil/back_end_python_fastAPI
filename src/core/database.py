from contextlib import contextmanager
from typing import Annotated

from fastapi import Depends
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

from src.core.config import config

DATABASE_URL = config.DATABASE_URL

# ✅ CORREÇÃO APLICADA AQUI
engine = create_engine(
    DATABASE_URL,
    connect_args={
        "options": "-c timezone=America/Sao_Paulo"
    }
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


get_db_manager = contextmanager(get_db)


GetDBDep = Annotated[Session, Depends(get_db)]