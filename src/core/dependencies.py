from datetime import datetime
from typing import Annotated

from fastapi import Depends, HTTPException, Header
from sqlalchemy.orm import Session, joinedload

from src.api.admin.services.subscription_service import SubscriptionService
from src.core import models
from src.core.database import GetDBDep
from src.core.security.security import verify_access_token, oauth2_scheme
from src.core.utils.enums import Roles


def get_user_from_token(token: str, db: Session):
    """✅ VERSÃO ATUALIZADA: Compatível com novo verify_access_token"""
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
    """✅ VERSÃO SEGURA: Usa nova função verify_access_token com blacklist"""
    payload = verify_access_token(token)

    if not payload:
        raise HTTPException(
            status_code=401,
            detail="Token inválido ou revogado",
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


def get_optional_user(db: GetDBDep, authorization: Annotated[str | None, Header()] = None):
    """✅ ATUALIZADO: Compatível com nova função verify_access_token"""
    if not authorization:
        return None

    try:
        token_type, _, token_value = authorization.partition(" ")
        if token_type.lower() != "bearer" or not token_value:
            return None

        return get_user_from_token(db=db, token=token_value)
    except Exception:
        return None


GetCurrentUserDep = Annotated[models.User, Depends(get_current_user)]
GetOptionalUserDep = Annotated[models.User | None, Depends(get_optional_user)]


class GetStore:
    def __init__(self, roles: list[Roles]):
        self.roles = roles

    def __call__(self, db: GetDBDep, user: GetCurrentUserDep, store_id: int):

        if user.is_superuser:
            store = db.query(models.Store).options(
                joinedload(models.Store.subscriptions)
                .joinedload(models.StoreSubscription.plan)
            ).filter(models.Store.id == store_id).first()

            if not store:
                raise HTTPException(status_code=404, detail="Store not found")

        else:
            db_store_access = db.query(models.StoreAccess).filter(
                models.StoreAccess.user == user,
                models.StoreAccess.store_id == store_id
            ).first()

            if not db_store_access:
                raise HTTPException(
                    status_code=403,
                    detail={'message': 'User does not have access to this store', 'code': 'NO_ACCESS_STORE'}
                )

            if db_store_access.role.machine_name not in [e.value for e in self.roles]:
                raise HTTPException(
                    status_code=403,
                    detail={'message': f'User must be one of {[e.value for e in self.roles]} to execute this action',
                            'code': 'REQUIRES_ANOTHER_ROLE'}
                )

            store = db_store_access.store

        sub_details = SubscriptionService.get_subscription_details(store, db)

        if sub_details and sub_details.get("is_blocked"):
            raise HTTPException(
                status_code=403,
                detail={
                    'message': sub_details.get('warning_message', 'Acesso negado devido à assinatura.'),
                    'code': 'PLAN_EXPIRED'
                }
            )

        return store


get_store = GetStore([Roles.OWNER, Roles.MANAGER])
GetStoreDep = Annotated[models.Store, Depends(get_store)]


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
    """✅ ATUALIZADO: Compatível com nova função verify_access_token"""
    payload = verify_access_token(token)

    if not payload:
        raise HTTPException(status_code=401, detail="Token de cliente inválido ou expirado")

    email = payload.get("sub")
    if not email:
        raise HTTPException(status_code=401, detail="Token payload inválido")

    customer = db.query(models.Customer).filter(models.Customer.email == email).first()

    if not customer:
        raise HTTPException(status_code=404, detail="Cliente não encontrado")

    return customer


def get_current_customer(
        db: GetDBDep,
        token: Annotated[str, Depends(oauth2_scheme)]
) -> models.Customer:
    return get_customer_from_token(token, db)


get_current_customer_dep = Annotated[models.Customer, Depends(get_current_customer)]