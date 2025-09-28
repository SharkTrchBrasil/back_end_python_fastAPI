# Arquivo: src/api/jobs/billing.py

from datetime import date, timedelta, datetime
from decimal import Decimal
from sqlalchemy import select, func
from sqlalchemy.orm import Session, selectinload

# Certifique-se de que este import está correto para o seu serviço de pagamento
from src.api.admin.services.payment import create_one_time_charge
from src.core import models
from src.core.database import get_db_manager


def calculate_monthly_fee(monthly_revenue: Decimal, plan: models.Plans) -> Decimal:
    """
    Calcula a taxa de assinatura mensal com base no faturamento da loja e
    nas regras do plano dinâmico.
    """
    revenue_in_reais = monthly_revenue
    minimum_fee = Decimal(plan.minimum_fee) / 100
    percentage_tier_start = Decimal(plan.percentage_tier_start) / 100
    percentage_tier_end = Decimal(plan.percentage_tier_end) / 100
    revenue_cap_fee = Decimal(plan.revenue_cap_fee) / 100

    if revenue_in_reais <= percentage_tier_start: return minimum_fee
    if percentage_tier_start < revenue_in_reais <= percentage_tier_end: return revenue_in_reais * plan.revenue_percentage
    if revenue_in_reais > percentage_tier_end: return revenue_cap_fee
    return minimum_fee


def get_store_revenue_for_period(db: Session, store_id: int, start_date: date, end_date: date) -> Decimal:
    """
    Calcula o faturamento total de uma loja em um determinado período.
    Confirme se os status 'finalized' e 'delivered' são os corretos para sua regra de negócio.
    """
    start_datetime = datetime.combine(start_date, datetime.min.time())
    end_datetime = datetime.combine(end_date, datetime.max.time())

    # Soma o valor total de pedidos com status 'finalized' ou 'delivered' no período
    total_revenue_cents = db.query(func.sum(models.Order.total_price)).filter(
        models.Order.store_id == store_id,
        models.Order.order_status.in_(['finalized', 'delivered']),
        models.Order.created_at.between(start_datetime, end_datetime)
    ).scalar()

    # Converte o valor de centavos para Reais
    return Decimal(total_revenue_cents or 0) / 100


def generate_monthly_charges():
    """
    Função principal do Job. Executada no início de cada mês para gerar
    a cobrança do mês anterior para todas as lojas com assinaturas ativas.
    """
    print("▶️ Executando job de geração de cobranças mensais...")
    today = date.today()
    # O Job só executa no dia 1º de cada mês
    if today.day != 1:
        print("ℹ️ Job de cobrança executa apenas no dia 1º. Encerrando.")
        return

    # Define o período de faturamento como o mês anterior completo
    last_day_of_previous_month = today - timedelta(days=1)
    first_day_of_previous_month = last_day_of_previous_month.replace(day=1)

    with get_db_manager() as db:
        # Busca todas as assinaturas ativas e já carrega os dados do plano e da loja
        active_subscriptions = db.execute(
            select(models.StoreSubscription)
            .options(selectinload(models.StoreSubscription.plan), selectinload(models.StoreSubscription.store))
            # ✅ GARANTE QUE APENAS ASSINATURAS 'active' SEJAM COBRADAS
            # Lojas com status 'trialing', 'canceled', etc., serão ignoradas.
            .where(models.StoreSubscription.status == 'active')
        ).scalars().all()

        for sub in active_subscriptions:
            store = sub.store

            # 1. Calcula o faturamento usando a função helper
            revenue = get_store_revenue_for_period(db, store.id, first_day_of_previous_month,
                                                   last_day_of_previous_month)

            # 2. Calcula a taxa a ser cobrada usando a outra função helper
            fee_to_charge = calculate_monthly_fee(revenue, sub.plan)
            fee_in_cents = int(fee_to_charge * 100)

            gateway_transaction_id = None
            if fee_in_cents > 0 and store.efi_payment_token:
                try:
                    # 3. Tenta criar a cobrança única na Efí
                    charge_response = create_one_time_charge(
                        payment_token=store.efi_payment_token,
                        amount_in_cents=fee_in_cents,
                        description=f"Mensalidade Ref. {first_day_of_previous_month.strftime('%m/%Y')}"
                    )
                    gateway_transaction_id = charge_response.get('charge_id')
                    print(
                        f"  -> Cobrança de R${fee_to_charge:.2f} iniciada na Efí para loja {store.id}. ID: {gateway_transaction_id}")
                except Exception as e:
                    print(f"  -> ERRO na cobrança da Efí para loja {store.id}: {e}")

            # 4. Salva o registro da cobrança no banco de dados com o status 'pending'
            new_charge = models.MonthlyCharge(
                store_id=store.id,
                subscription_id=sub.id,
                charge_date=today,
                billing_period_start=first_day_of_previous_month,
                billing_period_end=last_day_of_previous_month,
                total_revenue=revenue,
                calculated_fee=fee_to_charge,
                status="pending",
                gateway_transaction_id=gateway_transaction_id
            )
            db.add(new_charge)

        db.commit()
    print("✅ Geração de cobranças mensais concluída.")