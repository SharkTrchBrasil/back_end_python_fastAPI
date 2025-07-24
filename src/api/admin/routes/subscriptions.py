from typing import Annotated
from datetime import datetime, timedelta  # Importe datetime e timedelta

from fastapi import APIRouter, Depends, HTTPException

from src.api.shared_schemas.store import Roles, Store
from src.core import models
from src.core.database import GetDBDep
from src.core.dependencies import GetStore

from src.api.admin.schemas.store_subscription import CreateStoreSubscription  # Seu schema
from src.api.app.services import payment as payment_services

router = APIRouter(tags=["Subscriptions"], prefix="/stores/{store_id}/subscriptions")


@router.post("")
def new_subscription(
        db: GetDBDep,
        store: Annotated[Store, Depends(GetStore([Roles.OWNER]))],
        subscription_data: CreateStoreSubscription,  # Nome da variável alterado para clareza
):
    # ✅ Usa o novo modelo 'Plans'
    plan = db.query(models.Plans).filter_by(id=subscription_data.plan_id, available=True).first()
    if not plan:
        raise HTTPException(status_code=404, detail="Plano não encontrado ou indisponível")

    previous_subscription = db.query(models.StoreSubscription).filter(
        models.StoreSubscription.status.in_(['active', 'new_charge', 'trialing']),
        models.StoreSubscription.store_id == store.id
    ).first()

    if plan.price > 0:
        # --- Lógica do Gateway de Pagamento (mantida) ---
        efi_payment_plans = payment_services.list_plans(plan.plan_name)
        efi_payment_plan = next(iter(p for p in efi_payment_plans if p['interval'] == plan.interval
                                     and p['repeats'] == plan.repeats), None)

        if not efi_payment_plan:
            efi_payment_plan = payment_services.create_plan(plan.plan_name, plan.repeats, plan.interval)

        gateway_sub_response = payment_services.create_subscription(
            efi_payment_plan['plan_id'],
            plan,
            subscription_data.card.payment_token,
            subscription_data.customer,
            subscription_data.address
        )
        # --- Fim da lógica do Gateway ---

        # Calcula a data de fim do primeiro período
        start_date = datetime.utcnow()
        # O 'interval' do seu plano está em meses
        end_date = start_date + timedelta(days=plan.interval * 30)  # Estimativa de 30 dias/mês

        db_subscription = models.StoreSubscription(
            store_id=store.id,
            subscription_plan_id=plan.id,
            status=gateway_sub_response['status'],
            gateway_subscription_id=gateway_sub_response.get('subscription_id'),

            # ✅ CORREÇÃO: Usa as datas calculadas para o registro inicial
            current_period_start=start_date,
            current_period_end=end_date,
        )

    else:  # Lógica para plano gratuito
        # ✅ CORREÇÃO CRÍTICA: Define um período de validade para o plano gratuito
        start_date = datetime.utcnow()
        end_date = start_date + timedelta(days=365 * 100)  # Ex: validade de 100 anos

        db_subscription = models.StoreSubscription(
            store_id=store.id,
            subscription_plan_id=plan.id,
            gateway_subscription_id= '',
            status='active',
            current_period_start=start_date,
            current_period_end=end_date,
        )

    # ✅ Boa prática mantida da versão do curso: cancela a assinatura anterior
    if previous_subscription:
        if previous_subscription.gateway_subscription_id:
            try:
                payment_services.cancel_subscription(previous_subscription.gateway_subscription_id)
            except Exception as e:
                print(f"AVISO: Falha ao cancelar assinatura anterior no gateway: {e}")

        # Marca a assinatura antiga como cancelada no seu banco
        previous_subscription.status = 'canceled'

    db.add(db_subscription)
    db.commit()

    return db_subscription