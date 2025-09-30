from contextlib import contextmanager
from typing import Annotated

from fastapi import Depends
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session

from src.core.config import config

DATABASE_URL = config.DATABASE_URL

# ✅ CORREÇÃO COMPLETA - FORÇANDO TIMEZONE
engine = create_engine(
    DATABASE_URL,
    connect_args={
        "options": "-c timezone=America/Sao_Paulo"
    },
    # ✅ ADICIONE ESTES PARÂMETROS TAMBÉM
    pool_pre_ping=True,
    echo=False  # Mude para True se quiser ver as queries no console
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    db = SessionLocal()
    try:
        # ✅ FORÇA O TIMEZONE NA SESSÃO TAMBÉM
        db.execute(text("SET TIME ZONE 'America/Sao_Paulo'"))
        yield db
    finally:
        db.close()

get_db_manager = contextmanager(get_db)

GetDBDep = Annotated[Session, Depends(get_db)]