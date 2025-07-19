# src/core/services/store_access_service.py
from sqlalchemy.orm import Session
from src.core import models

class StoreAccessService:

    @staticmethod
    def get_admin_store_ids(db: Session, admin_id: int) -> list[int]:
        """
        Retorna os IDs das lojas onde o usuário tem acesso com a role 'owner'.
        """
        store_ids = [
            sa.store_id
            for sa in db.query(models.StoreAccess)
            .join(models.Role)
            .filter(
                models.StoreAccess.user_id == admin_id,
                models.Role.machine_name == 'owner' # <--- FILTRA APENAS POR 'owner'
            )
            .all()
        ]
        return store_ids

    @staticmethod
    def get_accessible_store_ids_with_fallback(db: Session, admin_user) -> list[int]:
        # Esta função continuará a usar o método acima
        store_ids = StoreAccessService.get_admin_store_ids(db, admin_user.id)

        # A lógica de fallback permanece a mesma: adiciona a loja principal do usuário
        # SOMENTE se nenhuma loja for encontrada pelos acessos de 'owner'.
        if not store_ids and admin_user.store_id:
            store_ids.append(admin_user.store_id)

        # Garante que não há duplicatas, o que é sempre uma boa prática defensiva.
        return list(set(store_ids))