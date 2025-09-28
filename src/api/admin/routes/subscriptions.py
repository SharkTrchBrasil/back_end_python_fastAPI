
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException
from typing import Annotated

from src.core import models
from src.core.database import GetDBDep
from src.core.dependencies import GetStore
from src.api.schemas.subscriptions.store_subscription import CreateStoreSubscription
# Ajuste o import para o seu serviço

from src.core.utils.enums import Roles

router = APIRouter(tags=["Subscriptions"], prefix="/stores/{store_id}/subscriptions")

@router.post("")
def new_subscription(
    db: GetDBDep,
    store: Annotated[models.Store, Depends(GetStore([Roles.OWNER]))],
    subscription_data: CreateStoreSubscription,
):
    plan = db.query(models.Plans).filter_by(id=subscription_data.plan_id, available=True).first()
    if not plan:
        raise HTTPException(status_code=404, detail="Plano não encontrado.")

    # A função `create_customer_and_tokenize_card` foi simplificada,
    # pois o `payment_token` já vem do frontend. Apenas o salvamos.
    store.efi_payment_token = subscription_data.card.payment_token

    previous_subscription = store.active_subscription
    if previous_subscription:
        previous_subscription.status = 'canceled'

    db_subscription = models.StoreSubscription(
        store_id=store.id,
        subscription_plan_id=plan.id,
        status='active',
        current_period_start=datetime.utcnow(),
        current_period_end=datetime.utcnow() + timedelta(days=30),
    )
    db.add(db_subscription)

    try:
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail="Erro interno ao salvar a assinatura.")

    return {"status": "success", "message": "Assinatura ativada com sucesso."}