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
                models.Role.machine_name == 'owner'
            )
            .all()
        ]
        return store_ids

    @staticmethod
    def get_accessible_store_ids_with_fallback(db: Session, admin_user) -> list[int]:
        # ✅ CORREÇÃO:
        # A função agora apenas chama o método principal. A lógica de fallback
        # que causava o erro foi removida.
        # Se um fallback for necessário no futuro, ele precisará ser implementado
        # com uma nova consulta ao banco (ex: buscar lojas onde é 'manager'),
        # e não acessando um campo inexistente.

        store_ids = StoreAccessService.get_admin_store_ids(db, admin_user.id)

        # A chamada para list(set(store_ids)) é redundante aqui, mas podemos manter
        # por segurança, caso a lógica seja expandida no futuro.
        return list(set(store_ids))