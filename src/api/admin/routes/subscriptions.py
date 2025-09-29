from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from typing import Annotated

# ✅ 1. Importa o novo utilitário de cálculo
from src.api.admin.utils.proration import calculate_prorated_charge
from src.api.admin.services.payment import create_one_time_charge
from src.api.admin.socketio.emitters import admin_emit_store_updated
from src.core import models
from src.core.database import GetDBDep
from src.core.dependencies import GetCurrentUserDep
from src.api.schemas.subscriptions.store_subscription import CreateStoreSubscription

router = APIRouter(tags=["Subscriptions"], prefix="/stores/{store_id}/subscriptions")


@router.post("")
async def create_or_reactivate_subscription(
        db: GetDBDep,
        store_id: int,
        user: GetCurrentUserDep,
        subscription_data: CreateStoreSubscription,
):
    """
    Ativa ou reativa uma assinatura com cobrança proporcional imediata.
    """
    store_access = db.query(models.StoreAccess).filter(
        models.StoreAccess.store_id == store_id,
        models.StoreAccess.user_id == user.id,
        models.StoreAccess.role.has(machine_name='owner')
    ).first()

    if not store_access:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Acesso negado a esta loja.")

    store = store_access.store
    subscription = db.query(models.StoreSubscription).filter_by(store_id=store_id).first()

    if not subscription or not subscription.plan:
        raise HTTPException(status_code=404, detail="Plano ou assinatura não encontrados para esta loja.")

    if subscription.status == 'active':
        return {"status": "info", "message": "Sua assinatura já está ativa."}

    if not subscription_data.card or not subscription_data.card.payment_token:
        raise HTTPException(status_code=400, detail="Token de pagamento do cartão é obrigatório para ativar.")

    store.efi_payment_token = subscription_data.card.payment_token

    try:
        # Primeiro, quita qualquer dívida antiga, se houver
        failed_charge = db.query(models.MonthlyCharge).filter_by(subscription_id=subscription.id,
                                                                 status='failed').first()
        if failed_charge:
            # ... (Lógica para cobrar dívida antiga, como já tínhamos)
            pass

        # ✅ 2. Calcula a cobrança proporcional para o mês atual
        proration_details = calculate_prorated_charge(subscription.plan)
        prorated_amount_cents = proration_details["amount_in_cents"]

        # ✅ 3. Realiza a cobrança proporcional imediata (se houver valor)
        if prorated_amount_cents > 0:
            print(f"Realizando cobrança proporcional de {prorated_amount_cents} centavos para a loja {store.id}")
            create_one_time_charge(
                payment_token=store.efi_payment_token,
                amount_in_cents=prorated_amount_cents,
                description=proration_details["description"]
            )

        # ✅ 4. Define o novo ciclo de faturamento para o FIM DO MÊS ATUAL
        subscription.status = "active"
        subscription.current_period_start = datetime.now(timezone.utc)
        subscription.current_period_end = proration_details["new_period_end_date"]

        db.commit()
        await admin_emit_store_updated(db, store.id)

        return {"status": "success", "message": "Assinatura ativada com sucesso!"}

    except Exception as e:
        db.rollback()
        error_detail = getattr(e, 'detail', str(e))
        raise HTTPException(status_code=400, detail=f"Falha ao processar o pagamento: {error_detail}")