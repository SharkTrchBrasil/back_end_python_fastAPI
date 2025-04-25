
from fastapi import APIRouter, HTTPException, Depends

from src.api.admin.schemas.store import StoreCreate, StoreWithRole, Roles
from src.core import models
from src.core.database import GetDBDep
from src.core.dependencies import GetCurrentUserDep, GetStoreDep

router = APIRouter(prefix="/stores", tags=["Stores"])

@router.post("", response_model=StoreWithRole)
def create_store(
    db: GetDBDep,
    user: GetCurrentUserDep,
    store_create: StoreCreate
):
    # 1) cria a loja e grava no banco
    db_store = models.Store(name=store_create.name, phone=store_create.phone,language=store_create.language,country=store_create.country, currency=store_create.currency )
    db.add(db_store)
    db.flush()                     # ← gera db_store.id sem dar commit

    # 2) vincula o usuário dono
    db_role = (
        db.query(models.Role)
        .filter(models.Role.machine_name == "owner")
        .first()
    )
    db_store_access = models.StoreAccess(
        user=user,
        role=db_role,
        store=db_store,
    )
    db.add(db_store_access)

    # 3) meios de pagamento default
    defaults = [
        dict(
            payment_type="cash",
            custom_name="Dinheiro",
            custom_icon="cash.svg",
            change_back=True,
            credit_in_account=False,
            is_active=True,
            active_on_delivery=True,
            active_on_pickup=True,
            active_on_counter=True,
            tax_rate=0.0,
            days_to_receive=0,
            has_fee=False,
            pix_key=None,
            pix_key_active=False,
        ),
        dict(
            payment_type="card",
            custom_name="Cartão",
            custom_icon="card.svg",
            change_back=False,
            credit_in_account=False,
            is_active=True,
            active_on_delivery=True,
            active_on_pickup=True,
            active_on_counter=True,
            tax_rate=2.49,
            days_to_receive=30,
            has_fee=True,
            pix_key=None,
            pix_key_active=False,
        ),
        dict(
            payment_type="pix",
            custom_name="Pix",
            custom_icon="pix.svg",
            change_back=False,
            credit_in_account=False,
            is_active=True,
            active_on_delivery=True,
            active_on_pickup=True,
            active_on_counter=True,
            tax_rate=0.0,
            days_to_receive=0,
            has_fee=False,
            pix_key=None,           # lojista configurará depois
            pix_key_active=False,
        ),
        dict(
            payment_type="other",
            custom_name="Outro",
            custom_icon="other.svg",
            change_back=False,
            credit_in_account=False,
            is_active=True,
            active_on_delivery=True,
            active_on_pickup=True,
            active_on_counter=True,
            tax_rate=0.0,
            days_to_receive=0,
            has_fee=False,
            pix_key=None,  # lojista configurará depois
            pix_key_active=False,
        ),
    ]

    for data in defaults:
        db.add(models.StorePaymentMethod(store_id=db_store.id, **data))

    # 4) salva tudo de uma vez
    db.commit()
    db.refresh(db_store_access)     # garante dados atualizados no retorno
    return db_store_access



@router.get("", response_model=list[StoreWithRole])
def list_stores(
    db: GetDBDep,
    user: GetCurrentUserDep,
):
    db_store_accesses = db.query(models.StoreAccess).filter(models.StoreAccess.user == user).all()
    return db_store_accesses


@router.patch("/{store_id}")
def patch_store(
    store: GetStoreDep,
):
    pass