from typing import Annotated
from datetime import datetime, timedelta  # Importe datetime e timedelta

from fastapi import APIRouter, Depends, HTTPException

from src.core import models
from src.core.database import GetDBDep
from src.core.dependencies import GetStore

from src.api.schemas.store_subscription import CreateStoreSubscription  # Seu schema
from src.api.app.services import payment as payment_services
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
        raise HTTPException(status_code=404, detail="Plano não encontrado ou indisponível")

    previous_subscription = db.query(models.StoreSubscription).filter(
        models.StoreSubscription.status.in_(['active', 'new_charge', 'trialing']),
        models.StoreSubscription.store_id == store.id
    ).first()

    db_subscription = None  # Inicializa a variável

    if plan.price > 0:
        try:
            print(f"DEBUG: Buscando plano '{plan.plan_name}' na Efí Pay...")
            efi_payment_plans = payment_services.list_plans(plan.plan_name)
            print(f"DEBUG: Planos encontrados na Efí: {len(efi_payment_plans)} plano(s).")

            efi_payment_plan = next(iter(p for p in efi_payment_plans if p['interval'] == plan.interval
                                         and p['repeats'] == plan.repeats), None)

            if not efi_payment_plan:
                print(f"DEBUG: Plano não encontrado. Criando novo plano '{plan.plan_name}' na Efí...")
                efi_payment_plan = payment_services.create_plan(plan.plan_name, plan.repeats, plan.interval)
                print("DEBUG: Novo plano criado com sucesso.")

            print("DEBUG: Criando assinatura no gateway...")
            gateway_sub_response = payment_services.create_subscription(
                efi_payment_plan['plan_id'],
                plan,
                subscription_data.card.payment_token,
                subscription_data.customer,
                subscription_data.address
            )
            print("DEBUG: Assinatura criada no gateway.")

        except Exception as e:
            print(f"ERRO CRÍTICO durante a comunicação com o gateway: {e}")
            raise HTTPException(
                status_code=503,  # Service Unavailable
                detail="Não foi possível comunicar com o serviço de pagamento. Tente novamente mais tarde."
            )

        start_date = datetime.utcnow()
        end_date = start_date + timedelta(days=plan.interval * 30)

        db_subscription = models.StoreSubscription(
            store_id=store.id,
            subscription_plan_id=plan.id,
            status=gateway_sub_response.get('status', 'pending'),
            gateway_subscription_id=gateway_sub_response.get('subscription_id'),
            current_period_start=start_date,
            current_period_end=end_date,
        )
    else:
        start_date = datetime.utcnow()
        end_date = start_date + timedelta(days=365 * 100)

        db_subscription = models.StoreSubscription(
            store_id=store.id,
            subscription_plan_id=plan.id,
            gateway_subscription_id=None,
            status='active',
            current_period_start=start_date,
            current_period_end=end_date,
        )

    # ✅ LOGS DE DEPURAÇÃO ADICIONAIS
    print("DEBUG: Objeto de nova assinatura criado. Preparando para salvar no banco.")

    if previous_subscription:
        print(
            f"DEBUG: Assinatura anterior (ID: {previous_subscription.id}) encontrada. Status: {previous_subscription.status}.")
        if previous_subscription.gateway_subscription_id:
            try:
                print(
                    f"DEBUG: Cancelando assinatura anterior no gateway (ID: {previous_subscription.gateway_subscription_id})...")
                payment_services.cancel_subscription(previous_subscription.gateway_subscription_id)
                print("DEBUG: Assinatura anterior cancelada no gateway com sucesso.")
            except Exception as e:
                print(f"AVISO: Falha ao cancelar assinatura anterior no gateway: {e}")

        print("DEBUG: Atualizando status da assinatura anterior para 'canceled' localmente.")
        previous_subscription.status = 'canceled'
    else:
        print("DEBUG: Nenhuma assinatura anterior ativa encontrada.")

    try:
        print("DEBUG: Adicionando nova assinatura à sessão do banco de dados (db.add)...")
        db.add(db_subscription)
        print("DEBUG: Executando commit no banco de dados (db.commit)...")
        db.commit()
        print("DEBUG: Commit realizado com sucesso.")
    except Exception as e:
        # ✅ TRATAMENTO DE ERRO ESPECÍFICO PARA O BANCO DE DADOS
        print(f"ERRO CRÍTICO durante o commit no banco de dados: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail="Erro interno ao salvar a assinatura no banco de dados.")

    return db_subscription
