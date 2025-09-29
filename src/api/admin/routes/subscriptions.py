from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException
from typing import Annotated

# Importe o serviço de pagamento para a cobrança avulsa
from src.api.admin.services.payment import create_one_time_charge
from src.api.admin.socketio.emitters import admin_emit_store_updated
from src.core import models
from src.core.database import GetDBDep
from src.core.dependencies import GetStore
from src.api.schemas.subscriptions.store_subscription import CreateStoreSubscription
from src.core.utils.enums import Roles

router = APIRouter(tags=["Subscriptions"], prefix="/stores/{store_id}/subscriptions")

@router.post("")
async def create_or_reactivate_subscription(
    db: GetDBDep,
    store: Annotated[models.Store, Depends(GetStore([Roles.OWNER]))],
    subscription_data: CreateStoreSubscription,
):
    """
    Cria uma nova assinatura ou reativa uma existente com pagamento pendente.
    """
    # --- FLUXO DE REATIVAÇÃO ---
    past_due_subscription = db.query(models.StoreSubscription).filter(
        models.StoreSubscription.store_id == store.id,
        models.StoreSubscription.status == 'past_due'
    ).first()

    if past_due_subscription:
        failed_charge = db.query(models.MonthlyCharge).filter(
            models.MonthlyCharge.subscription_id == past_due_subscription.id,
            models.MonthlyCharge.status == 'failed'
        ).order_by(models.MonthlyCharge.charge_date.desc()).first()

        if not failed_charge:
            raise HTTPException(status_code=404, detail="Débito pendente não localizado para quitação.")

        try:
            # Tenta cobrar o valor pendente com o novo cartão
            amount_in_cents = int(failed_charge.calculated_fee * 100)
            create_one_time_charge(
                payment_token=subscription_data.card.payment_token,
                amount_in_cents=amount_in_cents,
                description=f"Pagamento da fatura de {failed_charge.billing_period_start.strftime('%m/%Y')}"
            )

            # Se a cobrança for bem-sucedida, atualiza os registros
            failed_charge.status = "paid"
            past_due_subscription.status = "active"
            past_due_subscription.current_period_start = datetime.utcnow()
            past_due_subscription.current_period_end = datetime.utcnow() + timedelta(days=30)
            store.efi_payment_token = subscription_data.card.payment_token
            db.commit()

            # ✅ 3. EMITIR O EVENTO APÓS O SUCESSO DA REATIVAÇÃO
            await admin_emit_store_updated(db, store.id)

            return {"status": "success", "message": "Pagamento efetuado e assinatura reativada!"}

        except Exception as e:
            db.rollback()
            raise HTTPException(status_code=400, detail=f"Falha ao processar o pagamento do débito: {str(e)}")

    # --- FLUXO DE CRIAÇÃO/TROCA DE PLANO (Lógica original) ---
    plan = db.query(models.Plans).filter_by(id=subscription_data.plan_id, available=True).first()
    if not plan:
        raise HTTPException(status_code=404, detail="Plano não encontrado.")

    store.efi_payment_token = subscription_data.card.payment_token

    # Cancela a assinatura ativa anterior, se houver (para trocas de plano)
    active_subscription = store.active_subscription
    if active_subscription:
        active_subscription.status = 'canceled'

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
        await admin_emit_store_updated(db, store.id)
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail="Erro interno ao salvar a nova assinatura.")

    return {"status": "success", "message": "Assinatura ativada com sucesso."}