# src/core/services/store_access_service.py
from sqlalchemy.orm import Session
from src.core import models

class StoreAccessService:

    @staticmethod
    def get_admin_store_ids(db: Session, admin_id: int) -> list[int]:
        """Retorna os IDs das lojas que o admin tem acesso com role 'admin'"""
        store_ids = [
            sa.store_id
            for sa in db.query(models.StoreAccess)
            .join(models.Role)
            .filter(
                models.StoreAccess.user_id == admin_id,
                models.Role.machine_name == 'admin'
            )
            .all()
        ]
        return store_ids

    @staticmethod
    def get_accessible_store_ids_with_fallback(db: Session, admin_user) -> list[int]:
        """Busca as lojas acessíveis via StoreAccess e adiciona a loja principal se necessário"""
        store_ids = StoreAccessService.get_admin_store_ids(db, admin_user.id)

        if not store_ids and admin_user.store_id:
            store_ids.append(admin_user.store_id)

        return store_ids
