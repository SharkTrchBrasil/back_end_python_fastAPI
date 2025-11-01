# src/core/dependencies.py - GetStore COMPLETA E CORRIGIDA

from datetime import datetime
from typing import Annotated

from fastapi import Header
from fastapi import HTTPException, Request
from sqlalchemy.orm import Session, joinedload

from src.api.admin.services.subscription_service import SubscriptionService
from src.core import models
from src.core.database import GetDBDep
from src.core.security.security import verify_access_token, oauth2_scheme
from src.core.utils.enums import Roles
from fastapi import Depends

from src.core.utils.audit import AuditLogger


def get_user_from_token(token: str, db: Session):
    """âœ… VERSÃƒO ATUALIZADA: CompatÃ­vel com novo verify_access_token"""
    payload = verify_access_token(token)

    if not payload:
        raise HTTPException(status_code=401, detail="Invalid token")

    email = payload.get("sub")
    if not email:
        raise HTTPException(status_code=401, detail="Invalid token payload")

    user = db.query(models.User).filter(models.User.email == email).first()

    if not user:
        raise HTTPException(status_code=401, detail="Invalid token")

    return user


def get_current_user(
        db: GetDBDep,
        token: Annotated[str, Depends(oauth2_scheme)]
):
    """âœ… VERSÃƒO SEGURA: Usa nova funÃ§Ã£o verify_access_token com blacklist"""
    payload = verify_access_token(token)

    if not payload:
        raise HTTPException(
            status_code=401,
            detail="Token invÃ¡lido ou revogado",
            headers={"WWW-Authenticate": "Bearer"},
        )

    email = payload.get("sub")
    if not email:
        raise HTTPException(status_code=401, detail="Invalid token payload")

    user = db.query(models.User).filter(models.User.email == email).first()

    if not user:
        raise HTTPException(status_code=401, detail="User not found")

    if not user.is_active:
        raise HTTPException(status_code=401, detail="Inactive user")

    return user


# âœ… ADICIONAR: FunÃ§Ã£o para validar admin
def get_current_admin_user(
        db: GetDBDep,
        token: Annotated[str, Depends(oauth2_scheme)]
) -> models.User:
    """
    âœ… Retorna o usuÃ¡rio atual SE FOR ADMIN/SUPERUSER

    Uso: Proteger endpoints de administraÃ§Ã£o que nÃ£o dependem de store_id

    Exemplo:
    ```python
    @app.get("/admin/stats")
    async def admin_stats(admin: GetCurrentAdminUserDep):
        return {"admin": admin.email}
    ```
    """
    # Reutiliza a funÃ§Ã£o existente
    user = get_current_user(db, token)

    # âœ… Valida se Ã© admin
    if not user.is_superuser:
        raise HTTPException(
            status_code=403,
            detail="Acesso negado. Requer privilÃ©gios de administrador."
        )

    return user


def get_optional_user(db: GetDBDep, authorization: Annotated[str | None, Header()] = None):
    """âœ… ATUALIZADO: CompatÃ­vel com nova funÃ§Ã£o verify_access_token"""
    if not authorization:
        return None

    try:
        token_type, _, token_value = authorization.partition(" ")
        if token_type.lower() != "bearer" or not token_value:
            return None

        return get_user_from_token(db=db, token=token_value)
    except Exception:
        return None


# âœ… Type annotations para usar com Depends()
GetCurrentUserDep = Annotated[models.User, Depends(get_current_user)]
GetCurrentAdminUserDep = Annotated[models.User, Depends(get_current_admin_user)]  # âœ… NOVO
GetOptionalUserDep = Annotated[models.User | None, Depends(get_optional_user)]


# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
# âœ… GetStore CORRIGIDA E COMPLETA
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•

class GetStore:
    """
    âœ… DependÃªncia para validar acesso Ã  loja

    ValidaÃ§Ãµes:
    - Usuário é admin OU tem acesso declarado
    - Usuário tem a role correta (Owner/Manager)
    - !! NÃƒO valida status da assinatura aqui !!

    O bloqueio por assinatura deve ser feito POR ENDPOINT específico,
    não na dependência genérica (que é usada por muitos endpoints).
    """

    def __init__(self, roles: list[Roles]):
        self.roles = roles

    def __call__(self, db: GetDBDep, user: GetCurrentUserDep, store_id: int):

        # ✅ 1. ADMIN VÊ TUDO
        if user.is_superuser:
            store = db.query(models.Store).options(
                joinedload(models.Store.subscriptions)
                .joinedload(models.StoreSubscription.plan)
            ).filter(models.Store.id == store_id).first()

            if not store:
                raise HTTPException(
                    status_code=404,
                    detail="Store not found"
                )

            return store

        # ✅ 2. USUÁRIO COMUM: VALIDA ACESSO
        db_store_access = db.query(models.StoreAccess).filter(
            models.StoreAccess.user == user,
            models.StoreAccess.store_id == store_id
        ).first()

        if not db_store_access:
            raise HTTPException(
                status_code=403,
                detail={
                    'message': 'User does not have access to this store',
                    'code': 'NO_ACCESS_STORE'
                }
            )

        # ✅ 3. VALIDA ROLE (OWNER, MANAGER, etc)
        if db_store_access.role.machine_name not in [e.value for e in self.roles]:
            raise HTTPException(
                status_code=403,
                detail={
                    'message': f'User must be one of {[e.value for e in self.roles]} to execute this action',
                    'code': 'REQUIRES_ANOTHER_ROLE'
                }
            )

        store = db_store_access.store

        # ✅ 4. REMOVED: NÃO VALIDAMOS BLOQUEIO AQUI
        # O bloqueio por assinatura expirada deve ser feito por endpoint específico

        return store


# ✅ Instância padrão: Owner e Manager
get_store = GetStore([Roles.OWNER, Roles.MANAGER])
GetStoreDep = Annotated[models.Store, Depends(get_store)]


# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
# âœ… GetStoreForSubscriptionRoutes - PARA ENDPOINTS DE ASSINATURA
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•

class GetStoreForSubscriptionRoutes:
    """
    âœ… DependÃªncia especial para rotas de assinatura

    IDÊNTICA ao GetStore, MAS SEM validação de is_blocked.

    Permite que o usuário (dono) acesse as rotas de assinatura
    mesmo que a assinatura anterior tenha expirado.

    Isso é CRÍTICO para:
    - POST /subscriptions â†' Criar nova assinatura
    - DELETE /subscriptions â†' Cancelar assinatura
    - POST /subscriptions/reactivate â†' Reativar cancelada
    - PATCH /subscriptions/card â†' Atualizar cartão
    """

    def __init__(self, roles: list[Roles]):
        self.roles = roles

    def __call__(self, db: GetDBDep, user: GetCurrentUserDep, store_id: int):

        # ✅ 1. ADMIN VÊ TUDO
        if user.is_superuser:
            store = db.query(models.Store).options(
                joinedload(models.Store.subscriptions)
                .joinedload(models.StoreSubscription.plan)
            ).filter(models.Store.id == store_id).first()

            if not store:
                raise HTTPException(
                    status_code=404,
                    detail="Store not found"
                )

            return store

        # ✅ 2. USUÁRIO COMUM: VALIDA ACESSO
        db_store_access = db.query(models.StoreAccess).filter(
            models.StoreAccess.user == user,
            models.StoreAccess.store_id == store_id
        ).first()

        if not db_store_access:
            raise HTTPException(
                status_code=403,
                detail={
                    'message': 'User does not have access to this store',
                    'code': 'NO_ACCESS_STORE'
                }
            )

        # ✅ 3. VALIDA ROLE (OWNER só para gerenciar assinaturas)
        if db_store_access.role.machine_name not in [e.value for e in self.roles]:
            raise HTTPException(
                status_code=403,
                detail={
                    'message': f'Only {[e.value for e in self.roles]} can manage subscriptions',
                    'code': 'REQUIRES_OWNER_ROLE'
                }
            )

        store = db_store_access.store

        # ✅ 4. NÃO VALIDAMOS BLOQUEIO AQUI!
        # Isso permite que o usuário crie nova assinatura mesmo se a anterior expirou

        return store


# ✅ Instância: Apenas OWNER pode gerenciar assinaturas
get_store_for_subscription = GetStoreForSubscriptionRoutes([Roles.OWNER])
GetStoreForSubscriptionDep = Annotated[models.Store, Depends(get_store_for_subscription)]


# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
# OUTRAS DEPENDÊNCIAS (mantidas como estavam)
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•

def get_product(
        db: GetDBDep,
        store: GetStoreDep,
        product_id: int,
):
    db_product = db.query(models.Product).filter(
        models.Product.id == product_id,
        models.Product.store_id == store.id
    ).first()
    if not db_product:
        raise HTTPException(status_code=404, detail="Product not found")
    return db_product


GetProductDep = Annotated[models.Product, Depends(get_product)]


def get_variant_template(db: GetDBDep, store_id: int, variant_id: int):
    db_variant = db.query(models.Variant).filter(
        models.Variant.id == variant_id,
        models.Variant.store_id == store_id
    ).first()
    if not db_variant:
        raise HTTPException(status_code=404, detail="Variant template not found")
    return db_variant


GetVariantDep = Annotated[models.Variant, Depends(get_variant_template)]


def get_variant_option(db: GetDBDep, variant: GetVariantDep, option_id: int):
    option = db.query(models.VariantOption).filter(
        models.VariantOption.id == option_id,
        models.VariantOption.variant_id == variant.id
    ).first()
    if not option:
        raise HTTPException(status_code=404, detail="Option not found")
    return option


GetVariantOptionDep = Annotated[models.VariantOption, Depends(get_variant_option)]


def get_store_from_token(
        db: GetDBDep,
        token: Annotated[str | None, Header(alias="Totem-Token")] = None
) -> models.Store:
    if not token:
        raise HTTPException(status_code=401, detail="Missing Totem token")

    totem = db.query(models.TotemAuthorization).filter(
        models.TotemAuthorization.totem_token == token,
        models.TotemAuthorization.granted.is_(True)
    ).first()

    if not totem or not totem.store:
        raise HTTPException(status_code=401, detail="Invalid or unauthorized token")

    return totem.store


GetStoreFromTotemTokenDep = Annotated[models.Store, Depends(get_store_from_token)]


def get_customer_from_token(token: str, db: Session) -> models.Customer:
    """âœ… ATUALIZADO: CompatÃ­vel com nova funÃ§Ã£o verify_access_token"""
    payload = verify_access_token(token)

    if not payload:
        raise HTTPException(status_code=401, detail="Token de cliente invÃ¡lido ou expirado")

    email = payload.get("sub")
    if not email:
        raise HTTPException(status_code=401, detail="Token payload invÃ¡lido")

    customer = db.query(models.Customer).filter(models.Customer.email == email).first()

    if not customer:
        raise HTTPException(status_code=404, detail="Cliente nÃ£o encontrado")

    return customer


def get_current_customer(
        db: GetDBDep,
        token: Annotated[str, Depends(oauth2_scheme)]
) -> models.Customer:
    return get_customer_from_token(token, db)


get_current_customer_dep = Annotated[models.Customer, Depends(get_current_customer)]


def get_audit_logger(
        request: Request,
        db: GetDBDep,
        current_user: GetCurrentUserDep,
        store: GetStoreDep
) -> AuditLogger:
    """Cria uma instÃ¢ncia do AuditLogger para uso nas rotas"""
    return AuditLogger(db, request, current_user, store)


GetAuditLoggerDep = Annotated[AuditLogger, Depends(get_audit_logger)]