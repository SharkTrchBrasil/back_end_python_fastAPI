from datetime import datetime
from typing import Annotated

from fastapi import Depends, HTTPException, Header
from sqlalchemy.orm import Session, joinedload



from src.core import models

from src.core.database import GetDBDep


from src.core.security import verify_access_token, oauth2_scheme
from src.core.utils.enums import Roles


def get_user_from_token(token: str, db: Session):
    email = verify_access_token(token)
    if not email:
        raise HTTPException(status_code=401, detail="Invalid token")

    user = db.query(models.User).filter(models.User.email == email).first()

    if not user:
        raise HTTPException(status_code=401, detail="Invalid token")

    return user


def get_current_user(
        db: GetDBDep, token: Annotated[str, Depends(oauth2_scheme)]
):
    return get_user_from_token(token, db)


def get_optional_user(db: GetDBDep, authorization: Annotated[str | None, Header()] = None):
    token = authorization
    if not token:
        return None
    try:
        token_type, _, token_value = token.partition(" ")
        if token_type.lower() != "bearer" or not token_value:
            return None

        return get_user_from_token(db=db, token=token_value)
    except Exception as e:
        return None


GetCurrentUserDep = Annotated[models.User, Depends(get_current_user)]
GetOptionalUserDep = Annotated[models.User | None, Depends(get_optional_user)]




class GetStore:
    def __init__(self, roles: list[Roles]):
        self.roles = roles

    def __call__(self, db: GetDBDep, user: GetCurrentUserDep, store_id: int):

        # --- INÍCIO DA MODIFICAÇÃO ---
        # 1. VERIFICA SE O USUÁRIO É A CONTA DE SERVIÇO
        if user.email == "chatbot-service@system.local":
            # Se for o chatbot, ele é um "Super Admin". Pula a verificação da tabela StoreAccess.
            # Apenas busca a loja diretamente para poder fazer a verificação de assinatura.
            store = db.query(models.Store).options(
                joinedload(models.Store.subscriptions)
                .joinedload(models.StoreSubscription.plan)
            ).filter(models.Store.id == store_id).first()

            if not store:
                # Se a loja não existe, retorna um erro 404
                raise HTTPException(status_code=404, detail="Store not found for service account")

        else:
            # 2. SE FOR UM USUÁRIO NORMAL, EXECUTA A LÓGICA ORIGINAL
            # Carrega tudo em uma única query
            db_store_access = db.query(models.StoreAccess).options(
                joinedload(models.StoreAccess.store)
                .joinedload(models.Store.subscriptions)
                .joinedload(models.StoreSubscription.plan),
                joinedload(models.StoreAccess.role)
            ).filter(
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

            if db_store_access.role.machine_name not in [e.value for e in self.roles]:
                raise HTTPException(
                    status_code=403,
                    detail={
                        'message': f'User must be one of {[e.value for e in self.roles]} to execute this action',
                        'code': 'REQUIRES_ANOTHER_ROLE'
                    }
                )

            store = db_store_access.store
        # --- FIM DA MODIFICAÇÃO ---

        # 3. A VERIFICAÇÃO DE ASSINATURA AGORA FICA FORA DO ELSE E VALE PARA AMBOS
        active_sub = next(
            (sub for sub in store.subscriptions
             if sub.status in ['active', 'new_charge'] and
             sub.current_period_end >= datetime.utcnow()),
            None
        )

        if not active_sub:
            raise HTTPException(
                status_code=403,
                detail={
                    'message': 'A assinatura desta loja expirou. Por favor, renove para continuar usando.',
                    'code': 'PLAN_EXPIRED'
                }
            )

        return store


# A linha abaixo continua igual
get_store = GetStore([Roles.OWNER, Roles.ADMIN])
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
    # ✅ NOME ATUALIZADO PARA CLAREZA
    db_variant = db.query(models.Variant).filter(
        models.Variant.id == variant_id,
        models.Variant.store_id == store_id
    ).first()
    if not db_variant:
        raise HTTPException(status_code=404, detail="Variant template not found")
    return db_variant

GetVariantDep = Annotated[models.Variant, Depends(get_variant_template)]

def get_variant_option(db: GetDBDep, variant: GetVariantDep, option_id: int):
    # ✅ CÓDIGO CORRIGIDO E MAIS SEGURO
    option = db.query(models.VariantOption).filter(
        models.VariantOption.id == option_id,
        models.VariantOption.variant_id == variant.id # Garante que a opção pertence à variante correta
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