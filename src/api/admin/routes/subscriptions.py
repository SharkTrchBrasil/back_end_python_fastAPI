from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from typing import Annotated

from src.api.admin.services.pagarme_service import pagarme_service, PagarmeError
from src.api.admin.socketio.emitters import admin_emit_store_updated
from src.api.admin.utils.proration import calculate_prorated_charge
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
    ✅ ATUALIZADO: Ativa/Reativa assinatura usando Pagar.me
    """
    # 1. Verifica permissão
    store_access = db.query(models.StoreAccess).filter(
        models.StoreAccess.store_id == store_id,
        models.StoreAccess.user_id == user.id,
        models.StoreAccess.role.has(machine_name='owner')
    ).first()

    if not store_access:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acesso negado"
        )

    store = store_access.store

    # 2. Busca/Cria assinatura
    subscription = db.query(models.StoreSubscription).filter(
        models.StoreSubscription.store_id == store_id
    ).first()

    if not subscription:
        main_plan = db.query(models.Plans).filter_by(id=2).first()
        if not main_plan:
            raise HTTPException(status_code=500, detail="Plano não configurado")

        subscription = models.StoreSubscription(
            store=store,
            plan=main_plan,
            status="expired",
            current_period_start=datetime.now(timezone.utc) - timedelta(days=30),
            current_period_end=datetime.now(timezone.utc),
        )
        db.add(subscription)
        db.flush()

    # 3. Se já está ativa, apenas atualiza o cartão
    if subscription.status == 'active':
        if subscription_data.card and subscription_data.card.payment_token:
            try:
                # ✅ PAGAR.ME: Adiciona novo cartão
                if not store.pagarme_customer_id:
                    # Cria cliente se não existir
                    customer_response = pagarme_service.create_customer(
                        email=user.email,
                        name=store.name,
                        document=store.cnpj or "00000000000",
                        phone=store.phone or "0000000000",
                        store_id=store.id
                    )
                    store.pagarme_customer_id = customer_response["id"]

                # Adiciona o cartão
                card_response = pagarme_service.create_card(
                    customer_id=store.pagarme_customer_id,
                    card_token=subscription_data.card.payment_token
                )
                store.pagarme_card_id = card_response["id"]

                db.commit()
                return {
                    "status": "success",
                    "message": "Método de pagamento atualizado"
                }

            except PagarmeError as e:
                db.rollback()
                raise HTTPException(status_code=400, detail=str(e))

        return {"status": "info", "message": "Assinatura já ativa"}

    # 4. Ativação/Reativação
    if not subscription_data.card or not subscription_data.card.payment_token:
        raise HTTPException(
            status_code=400,
            detail="Token do cartão é obrigatório"
        )

    try:
        # ✅ CRIA CLIENTE NO PAGAR.ME (se não existir)
        if not store.pagarme_customer_id:
            customer_response = pagarme_service.create_customer(
                email=user.email,
                name=store.name,
                document=store.cnpj or "00000000000",
                phone=store.phone or "0000000000",
                store_id=store.id
            )
            store.pagarme_customer_id = customer_response["id"]

        # ✅ ADICIONA CARTÃO
        card_response = pagarme_service.create_card(
            customer_id=store.pagarme_customer_id,
            card_token=subscription_data.card.payment_token
        )
        store.pagarme_card_id = card_response["id"]

        # ✅ TENTA PAGAR FATURA PENDENTE
        failed_charge = db.query(models.MonthlyCharge).filter(
            models.MonthlyCharge.subscription_id == subscription.id,
            models.MonthlyCharge.status == 'failed'
        ).order_by(models.MonthlyCharge.charge_date.desc()).first()

        if failed_charge:
            amount_in_cents = int(failed_charge.calculated_fee * 100)
            description = f"Fatura pendente {failed_charge.billing_period_start.strftime('%m/%Y')}"

            charge_response = pagarme_service.create_charge(
                customer_id=store.pagarme_customer_id,
                card_id=store.pagarme_card_id,
                amount_in_cents=amount_in_cents,
                description=description,
                store_id=store.id,
                metadata={
                    "charge_id": str(failed_charge.id),
                    "type": "overdue_payment"
                }
            )
            failed_charge.gateway_transaction_id = charge_response["id"]
            failed_charge.status = "pending"

        # ✅ COBRANÇA PROPORCIONAL
        proration_details = calculate_prorated_charge(subscription.plan)
        prorated_amount_cents = proration_details["amount_in_cents"]

        if prorated_amount_cents > 0:
            charge_response = pagarme_service.create_charge(
                customer_id=store.pagarme_customer_id,
                card_id=store.pagarme_card_id,
                amount_in_cents=prorated_amount_cents,
                description=proration_details["description"],
                store_id=store.id,
                metadata={"type": "prorated_charge"}
            )

        # ✅ ATIVA ASSINATURA
        subscription.status = "active"
        subscription.current_period_start = datetime.now(timezone.utc)
        subscription.current_period_end = proration_details["new_period_end_date"]

        db.commit()
        await admin_emit_store_updated(db, store.id)

        return {
            "status": "success",
            "message": "Assinatura ativada com sucesso!"
        }

    except PagarmeError as e:
        db.rollback()
        raise HTTPException(
            status_code=400,
            detail=f"Erro ao processar pagamento: {str(e)}"
        )