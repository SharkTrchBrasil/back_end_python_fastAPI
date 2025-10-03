from sqlalchemy.orm import Session, selectinload
from src.core import models

class StoreAccessService:
    """
    Serviço para gerenciar e verificar o acesso de administradores às lojas.
    """

    @staticmethod
    def get_accessible_stores_with_roles(db: Session, admin_user: models.AdminUser) -> list[models.StoreAccess]:
        """
        ✅ O NOVO MÉTODO PRINCIPAL
        Busca todos os objetos `StoreAccess` para um admin, carregando de forma otimizada
        as relações `store` e `role`. É a fonte de dados ideal para a lista de lojas.
        """
        if not admin_user:
            return []

        # Se for superadmin, ele tem acesso a TODAS as lojas com a role de 'owner'.
        if admin_user.is_superadmin:
            all_stores = db.query(models.Store).all()
            owner_role = db.query(models.Role).filter_by(machine_name='owner').first()

            # Cria objetos StoreAccess "virtuais" para o superadmin, pois eles não
            # existem no banco de dados.
            access_objects = []
            for store in all_stores:
                virtual_access = models.StoreAccess(
                    user_id=admin_user.id,
                    store_id=store.id,
                    role_id=owner_role.id if owner_role else None,
                    store=store,  # Anexa o objeto completo da loja
                    role=owner_role # Anexa o objeto completo da role
                )
                access_objects.append(virtual_access)
            return access_objects

        # Para admins normais, faz a busca otimizada na tabela de acesso.
        return db.query(models.StoreAccess).options(
            selectinload(models.StoreAccess.store), # Carrega a relação com a loja
            selectinload(models.StoreAccess.role)   # Carrega a relação com a role
        ).filter(models.StoreAccess.user_id == admin_user.id).all()


    @staticmethod
    def get_accessible_store_ids_with_fallback(db: Session, admin_user: models.AdminUser) -> list[int]:
        """
        (MÉTODO ANTIGO ATUALIZADO)
        Retorna apenas os IDs das lojas que o admin pode acessar.
        Útil para validações rápidas onde o objeto completo não é necessário.
        """
        if not admin_user:
            return []

        if admin_user.is_superadmin:
            # Superadmin tem acesso a todas as lojas.
            return [store.id for store in db.query(models.Store.id).all()]

        # Admin normal: busca os IDs na tabela de acesso.
        store_ids = [
            access.store_id
            for access in db.query(models.StoreAccess.store_id)
            .filter(models.StoreAccess.user_id == admin_user.id)
            .all()
        ]
        return list(set(store_ids)) # Usa set para garantir IDs únicos
