# src/core/services/session_service.py
from datetime import datetime
from sqlalchemy.orm import Session
from src.core import models

class SessionService:

    @staticmethod
    def create_or_update_session(db: Session, sid: str, store_id: int, client_type: str = "admin"):
        """Cria ou atualiza uma sessão de admin"""
        session = db.query(models.StoreSession).filter_by(sid=sid).first()

        if not session:
            session = models.StoreSession(
                sid=sid,
                store_id=store_id,
                client_type=client_type
            )
            db.add(session)
        else:
            session.store_id = store_id
            session.client_type = client_type
            session.updated_at = datetime.utcnow()

        db.commit()
        return session

    @staticmethod
    def remove_session(db: Session, sid: str):
        """Remove uma sessão por sid"""
        session = db.query(models.StoreSession).filter_by(sid=sid).first()
        if session:
            db.delete(session)
            db.commit()
            return True
        return False


    @staticmethod
    def get_session(db: Session, sid: str, client_type: str = None):
        query = db.query(models.StoreSession).filter_by(sid=sid)
        if client_type:
            query = query.filter_by(client_type=client_type)
        return query.first()
