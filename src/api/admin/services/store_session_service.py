# src/core/services/session_service.py
from datetime import datetime
from sqlalchemy.orm import Session
from src.core import models

class SessionService:

    @staticmethod
    def create_or_update_session(
        db: Session,
        sid: str,
        client_type: str,
        user_id: int,
        store_id: int = None,
        device_name: str = None,      # ✅ NOVO
        device_type: str = None,      # ✅ NOVO
        platform: str = None,         # ✅ NOVO
        browser: str = None,          # ✅ NOVO
        ip_address: str = None        # ✅ NOVO
    ):
        """Cria ou atualiza uma sessão de admin, salvando informações do dispositivo."""
        session = db.query(models.StoreSession).filter_by(sid=sid).first()

        if not session:
            session = models.StoreSession(
                sid=sid,
                user_id=user_id,
                store_id=store_id,
                client_type=client_type,
                device_name=device_name,        # ✅ NOVO
                device_type=device_type,        # ✅ NOVO
                platform=platform,              # ✅ NOVO
                browser=browser,                # ✅ NOVO
                ip_address=ip_address,          # ✅ NOVO
                last_activity=datetime.utcnow() # ✅ NOVO
            )
            db.add(session)
        else:
            session.user_id = user_id
            session.store_id = store_id
            session.client_type = client_type
            session.device_name = device_name        # ✅ NOVO
            session.device_type = device_type        # ✅ NOVO
            session.platform = platform              # ✅ NOVO
            session.browser = browser                # ✅ NOVO
            session.ip_address = ip_address          # ✅ NOVO
            session.updated_at = datetime.utcnow()
            session.last_activity = datetime.utcnow() # ✅ NOVO

        db.commit()
        return session

    @staticmethod
    def update_last_activity(db: Session, sid: str):
        """Atualiza o timestamp de última atividade da sessão."""
        session = db.query(models.StoreSession).filter_by(sid=sid).first()
        if session:
            session.last_activity = datetime.utcnow()
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
        """Busca uma sessão por SID, opcionalmente filtrando por tipo de cliente"""
        query = db.query(models.StoreSession).filter_by(sid=sid)
        if client_type:
            query = query.filter_by(client_type=client_type)
        return query.first()

    @staticmethod
    def update_session_store(db: Session, sid: str, store_id: int):
        """Atualiza o store_id de uma sessão existente."""
        session = db.query(models.StoreSession).filter_by(sid=sid).first()
        if session:
            session.store_id = store_id
            session.updated_at = datetime.utcnow()
            session.last_activity = datetime.utcnow()  # ✅ NOVO
            db.commit()
        return session