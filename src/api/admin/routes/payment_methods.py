from fastapi import APIRouter, Form, HTTPException
from src.api.admin.schemas.payment_method import StorePaymentMethods
from src.core import models
from src.core.database import GetDBDep
from src.core.dependencies import GetStoreDep

router = APIRouter(
    tags=["Payment Methods"],
    prefix="/stores/{store_id}/payment-methods"
)

# ───────────────────────── CREATE ─────────────────────────
@router.post("", response_model=StorePaymentMethods)
def create_payment_method(
    db: GetDBDep,
    store: GetStoreDep,

    payment_type: str = Form(..., max_length=20),
    custom_name: str = Form(...),
    custom_icon: str | None = Form(None),           # ← nome do asset, ex: 'cash.svg'

    change_back: bool = Form(False),
    credit_in_account: bool = Form(False),
    is_active: bool = Form(True),

    active_on_delivery: bool = Form(True),
    active_on_pickup:   bool = Form(True),
    active_on_counter:  bool = Form(True),

    tax_rate: float = Form(0.0),
    days_to_receive: int = Form(0),
    has_fee: bool = Form(False),

    pix_key: str | None = Form(None),
    pix_key_active: bool = Form(False),
):
    pm = models.StorePaymentMethods(
        store_id=store.id,
        payment_type=payment_type,
        custom_name=custom_name,
        custom_icon=custom_icon,       # salva só o identificador

        change_back=change_back,
        credit_in_account=credit_in_account,
        is_active=is_active,

        active_on_delivery=active_on_delivery,
        active_on_pickup=active_on_pickup,
        active_on_counter=active_on_counter,

        tax_rate=tax_rate,
        days_to_receive=days_to_receive,
        has_fee=has_fee,

        pix_key=pix_key,
        pix_key_active=pix_key_active
    )

    db.add(pm)
    db.commit()
    db.refresh(pm)
    return pm

# ───────────────────────── LIST ─────────────────────────
@router.get("", response_model=list[StorePaymentMethods])
def list_payment_methods(db: GetDBDep, store: GetStoreDep):
    return (
        db.query(models.StorePaymentMethods)
          .filter(models.StorePaymentMethods.store_id == store.id)
          .all()
    )

# ───────────────────────── RETRIEVE ─────────────────────────
@router.get("/{pm_id}", response_model=StorePaymentMethods)
def get_payment_method(db: GetDBDep, store: GetStoreDep, pm_id: int):
    pm = (
        db.query(models.StorePaymentMethods)
          .filter(models.StorePaymentMethods.id == pm_id,
                  models.StorePaymentMethods.store_id == store.id)
          .first()
    )
    if not pm:
        raise HTTPException(404, detail="Payment method not found")
    return pm

# ───────────────────────── UPDATE/PATCH ─────────────────────────
@router.patch("/{pm_id}", response_model=StorePaymentMethods)
def update_payment_method(
    db: GetDBDep,
    store: GetStoreDep,
    pm_id: int,

    payment_type: str | None = Form(None),
    custom_name: str | None = Form(None),
    custom_icon: str | None = Form(None),      # ← recebe novo asset, se quiser

    change_back: bool | None = Form(None),
    credit_in_account: bool | None = Form(None),
    is_active: bool | None = Form(None),

    active_on_delivery: bool | None = Form(None),
    active_on_pickup:   bool | None = Form(None),
    active_on_counter:  bool | None = Form(None),

    tax_rate: float | None = Form(None),
    days_to_receive: int | None = Form(None),
    has_fee: bool | None = Form(None),

    pix_key: str | None = Form(None),
    pix_key_active: bool | None = Form(None),
):
    pm = (
        db.query(models.StorePaymentMethods)
          .filter(models.StorePaymentMethods.id == pm_id,
                  models.StorePaymentMethods.store_id == store.id)
          .first()
    )
    if not pm:
        raise HTTPException(404, detail="Payment method not found")

    if payment_type:          pm.payment_type = payment_type
    if custom_name:           pm.custom_name  = custom_name
    if custom_icon is not None: pm.custom_icon = custom_icon   # pode pôr '' p/ reset

    if change_back is not None:       pm.change_back = change_back
    if credit_in_account is not None: pm.credit_in_account = credit_in_account
    if is_active is not None:         pm.is_active = is_active

    if active_on_delivery is not None: pm.active_on_delivery = active_on_delivery
    if active_on_pickup   is not None: pm.active_on_pickup   = active_on_pickup
    if active_on_counter  is not None: pm.active_on_counter  = active_on_counter

    if tax_rate is not None:           pm.tax_rate = tax_rate
    if days_to_receive is not None:    pm.days_to_receive = days_to_receive
    if has_fee is not None:            pm.has_fee = has_fee

    if pix_key is not None:            pm.pix_key = pix_key
    if pix_key_active is not None:     pm.pix_key_active = pix_key_active

    db.commit()
    return pm


# ───────────────────────── DELETE ─────────────────────────
@router.delete("/{pm_id}")
def delete_payment_method(
    db: GetDBDep,
    store: GetStoreDep,
    pm_id: int
):
    pm = (
        db.query(models.StorePaymentMethods)
          .filter(models.StorePaymentMethods.id == pm_id,
                  models.StorePaymentMethods.store_id == store.id)
          .first()
    )
    if not pm:
        raise HTTPException(status_code=404, detail="Payment method not found")

    db.delete(pm)
    db.commit()
    return {"detail": "Payment method deleted successfully"}