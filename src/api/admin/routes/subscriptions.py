from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from typing import Annotated

from src.api.admin.services.payment import create_one_time_charge
from src.api.admin.socketio.emitters import admin_emit_store_updated
from src.core import models
from src.core.database import GetDBDep
# ✅ ALTERAÇÃO: Importamos uma dependência mais simples que só pega o usuário
from src.core.dependencies import GetCurrentUserDep
from src.api.schemas.subscriptions.store_subscription import CreateStoreSubscription

router = APIRouter(tags=["Subscriptions"], prefix="/stores/{store_id}/subscriptions")


@router.post("")
async def create_or_reactivate_subscription(
        db: GetDBDep,
        store_id: int,
        user: GetCurrentUserDep,  # ✅ ALTERAÇÃO: Usamos a dependência mais simples
        subscription_data: CreateStoreSubscription,
):
    """
    Endpoint robusto que ativa ou reativa uma assinatura.
    Ele mesmo faz a verificação de permissão para poder lidar com lojas 'expired'.
    """
    # 1. Busca a loja e verifica a permissão de 'owner' manualmente
    store_access = db.query(models.StoreAccess).filter(
        models.StoreAccess.store_id == store_id,
        models.StoreAccess.user_id == user.id,
        models.StoreAccess.role.has(machine_name='owner')
    ).first()

    if not store_access:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Acesso negado a esta loja.")

    store = store_access.store

    # 2. Busca a assinatura existente da loja
    subscription = db.query(models.StoreSubscription).filter(
        models.StoreSubscription.store_id == store_id
    ).first()

    if not subscription:
        # Lida com o caso de uma loja muito antiga que nunca teve um registro de assinatura
        main_plan = db.query(models.Plans).filter_by(id=2).first()
        if not main_plan:
            raise HTTPException(status_code=500, detail="Plano padrão não configurado.")

        subscription = models.StoreSubscription(
            store=store, plan=main_plan, status="expired",
            current_period_start=datetime.now(timezone.utc) - timedelta(days=30),
            current_period_end=datetime.now(timezone.utc),
        )
        db.add(subscription)
        db.flush()

    # 3. Se a assinatura já estiver ativa, apenas atualiza o cartão.
    if subscription.status == 'active':
        if subscription_data.card and subscription_data.card.payment_token:
            store.efi_payment_token = subscription_data.card.payment_token
            db.commit()
            return {"status": "success", "message": "Método de pagamento atualizado com sucesso."}
        else:
            return {"status": "info", "message": "Sua assinatura já está ativa."}

    # 4. Lógica de Ativação / Reativação
    if not subscription_data.card or not subscription_data.card.payment_token:
        raise HTTPException(status_code=400, detail="Token de pagamento do cartão é obrigatório para ativar.")

    store.efi_payment_token = subscription_data.card.payment_token

    try:
        # Se houver uma cobrança pendente, tenta quitá-la
        failed_charge = db.query(models.MonthlyCharge).filter(
            models.MonthlyCharge.subscription_id == subscription.id,
            models.MonthlyCharge.status == 'failed'
        ).order_by(models.MonthlyCharge.charge_date.desc()).first()

        if failed_charge:
            amount_in_cents = int(failed_charge.calculated_fee * 100)
            description = f"Pagamento da fatura pendente de {failed_charge.billing_period_start.strftime('%m/%Y')}"
            create_one_time_charge(
                payment_token=store.efi_payment_token,
                amount_in_cents=amount_in_cents,
                description=description
            )
            failed_charge.status = "paid"

        # Define o status como ATIVO e inicia um novo ciclo de 30 dias
        subscription.status = "active"
        subscription.current_period_start = datetime.now(timezone.utc)
        subscription.current_period_end = datetime.now(timezone.utc) + timedelta(days=30)

        db.commit()
        await admin_emit_store_updated(db, store.id)

        return {"status": "success", "message": "Assinatura ativada com sucesso!"}

    except Exception as e:
        db.rollback()
        error_detail = getattr(e, 'detail', str(e))
        raise HTTPException(status_code=400, detail=f"Falha ao processar o pagamento: {error_detail}")