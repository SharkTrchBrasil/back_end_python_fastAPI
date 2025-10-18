"""
Funções de validação de segurança centralizadas
Autor: PDVix Security Team
Data: 2025-10-18
"""
from fastapi import HTTPException
from sqlalchemy.orm import Session
from src.core import models


def validate_store_ownership(
        db: Session,
        user: models.User,
        store_id: int
) -> models.Store:
    """
    ✅ Valida se o usuário tem acesso à loja

    Args:
        db: Sessão do banco
        user: Usuário autenticado
        store_id: ID da loja a validar

    Returns:
        Store object se válido

    Raises:
        HTTPException(403) se não tiver acesso
        HTTPException(404) se loja não existir
    """

    # Superuser tem acesso a tudo
    if user.is_superuser:
        store = db.query(models.Store).filter(
            models.Store.id == store_id
        ).first()

        if not store:
            raise HTTPException(
                status_code=404,
                detail="Loja não encontrada"
            )

        return store

    # Usuário normal: valida acesso
    store_access = db.query(models.StoreAccess).filter(
        models.StoreAccess.user_id == user.id,
        models.StoreAccess.store_id == store_id
    ).first()

    if not store_access:
        raise HTTPException(
            status_code=403,
            detail={
                "message": "Você não tem acesso a esta loja",
                "code": "NO_ACCESS_STORE"
            }
        )

    return store_access.store


def validate_resource_ownership(
        db: Session,
        resource_model: type,
        resource_id: int,
        store_id: int,
        resource_name: str = "Recurso"
):
    """
    ✅ Valida que um recurso pertence à loja

    Args:
        db: Sessão do banco
        resource_model: Modelo SQLAlchemy
        resource_id: ID do recurso
        store_id: ID da loja validada
        resource_name: Nome do recurso para mensagem de erro

    Returns:
        Resource object se válido

    Raises:
        HTTPException(404) se não encontrar
    """

    resource = db.query(resource_model).filter(
        resource_model.id == resource_id,
        resource_model.store_id == store_id
    ).first()

    if not resource:
        raise HTTPException(
            status_code=404,
            detail=f"{resource_name} não encontrado ou não pertence a esta loja"
        )

    return resource