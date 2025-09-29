# Arquivo: src/api/jobs/billing.py

from datetime import date, timedelta, datetime
from decimal import Decimal
from sqlalchemy import select, func
from sqlalchemy.orm import Session, selectinload

# Ajuste os imports conforme sua estrutura
from src.api.admin.services.payment import create_one_time_charge
from src.api.admin.utils.business_days import is_first_business_day
from src.core import models
from src.core.database import get_db_manager


def calculate_platform_fee(monthly_revenue: Decimal, plan: models.Plans, months_active: int = 0) -> dict:
    """
    Calcula a taxa da plataforma com nossos diferenciais exclusivos.
    """
    # ✅ CONVERTE VALORES DO PLANO PARA REAIS
    minimum_fee_reais = Decimal(plan.minimum_fee) / 100
    revenue_cap_reais = Decimal(plan.revenue_cap_fee) / 100 if plan.revenue_cap_fee else None
    tier_start_reais = Decimal(plan.percentage_tier_start) / 100
    tier_end_reais = Decimal(plan.percentage_tier_end) / 100

    # ✅ 1. CALCULA TAXA BASE (VALOR JUSTO)
    if monthly_revenue <= tier_start_reais:
        base_fee = minimum_fee_reais
        fee_type = "taxa mínima"
    elif monthly_revenue <= tier_end_reais:
        base_fee = monthly_revenue * plan.revenue_percentage
        base_fee = max(base_fee, minimum_fee_reais)  # Respeita o mínimo
        fee_type = f"{(plan.revenue_percentage * 100):.1f}% do faturamento"
    else:
        base_fee = revenue_cap_reais if revenue_cap_reais else monthly_revenue * plan.revenue_percentage
        fee_type = "taxa máxima"

    # ✅ 2. APLICA NOSSOS BENEFÍCIOS EXCLUSIVOS
    if months_active == 0 and plan.first_month_free:
        final_fee = Decimal('0.00')
        discount_percentage = Decimal('1.00')
        benefit_type = "🎁 1º mês por nossa conta!"

    elif months_active == 1:
        final_fee = base_fee * plan.second_month_discount
        discount_percentage = Decimal('1.00') - plan.second_month_discount
        benefit_type = "🔥 2º mês com 50% de desconto!"

    elif months_active == 2:
        final_fee = base_fee * plan.third_month_discount
        discount_percentage = Decimal('1.00') - plan.third_month_discount
        benefit_type = "💫 3º mês com 25% de desconto!"

    else:
        final_fee = base_fee
        discount_percentage = Decimal('0.00')
        benefit_type = "💎 Plano ativo - Valor especial"

    # ✅ 3. CALCULA NOSSO VALOR
    effective_rate = (final_fee / monthly_revenue * 100) if monthly_revenue > 0 else 0

    # ✅ 4. PREPARA MENSAGEM POSITIVA
    message = generate_positive_message(benefit_type, final_fee, effective_rate)

    return {
        'base_fee': base_fee,
        'final_fee': final_fee,
        'discount_percentage': float(discount_percentage * 100),
        'benefit_type': benefit_type,
        'fee_type': fee_type,
        'effective_rate': effective_rate,
        'message': message,
        'has_benefit': discount_percentage > 0
    }


def generate_positive_message(benefit_type: str, final_fee: Decimal, effective_rate: float) -> str:
    """Gera mensagem positiva sobre nossos benefícios"""
    if final_fee == 0:
        return f"{benefit_type} Aproveite nosso investimento no seu negócio!"
    elif effective_rate < 3:
        return f"{benefit_type} Taxa especial de apenas {effective_rate:.1f}%!"
    else:
        return f"{benefit_type} Valor justo pelo melhor serviço!"


def get_store_revenue_for_period(db: Session, store_id: int, start_date: date, end_date: date) -> Decimal:
    """
    Calcula o faturamento total de uma loja em um determinado período.
    """
    try:
        start_datetime = datetime.combine(start_date, datetime.min.time())
        end_datetime = datetime.combine(end_date, datetime.max.time())

        total_revenue_cents = db.query(func.sum(models.Order.total_price)).filter(
            models.Order.store_id == store_id,
            models.Order.order_status.in_(['finalized', 'delivered']),
            models.Order.created_at.between(start_datetime, end_datetime)
        ).scalar()

        # Converte de centavos para Reais
        revenue_reais = Decimal(total_revenue_cents or 0) / 100
        return revenue_reais.quantize(Decimal('0.01'))

    except Exception as e:
        print(f"Erro ao calcular faturamento da loja {store_id}: {e}")
        return Decimal('0')


def calculate_months_active(subscription: models.StoreSubscription, today: date) -> int:
    """Calcula meses de parceria conosco"""
    from dateutil.relativedelta import relativedelta

    start_date = subscription.current_period_start.date()
    months_active = relativedelta(today, start_date).months

    return max(0, months_active)


def generate_monthly_charges():
    """
    Job principal com nossos diferenciais
    """
    print("▶️ Iniciando processo de cobrança mensal...")
    today = date.today()

    if not is_first_business_day(today):
        print("ℹ️ Agendado para o primeiro dia útil. Processo interrompido.")
        return

    last_day_of_previous_month = today - timedelta(days=1)
    first_day_of_previous_month = last_day_of_previous_month.replace(day=1)

    with get_db_manager() as db:
        active_subscriptions = db.execute(
            select(models.StoreSubscription)
            .options(selectinload(models.StoreSubscription.plan), selectinload(models.StoreSubscription.store))
            .where(models.StoreSubscription.status == 'active')
        ).scalars().all()

        print(f"📊 Processando {len(active_subscriptions)} assinaturas ativas...")

        for sub in active_subscriptions:
            store = sub.store

            if not store or not sub.plan:
                continue

            try:

                if sub.current_period_start.date() >= first_day_of_previous_month:
                    print(f"  ℹ️ Loja {store.id} iniciou no meio do período ({sub.current_period_start.date()}). A cobrança proporcional já foi feita. Pulando a fatura deste mês.")
                    continue

                # O resto da sua lógica de cobrança continua normalmente...
                months_active = calculate_months_active(sub, today)
                revenue = get_store_revenue_for_period(db, store.id, first_day_of_previous_month,
                                                       last_day_of_previous_month)
                fee_details = calculate_platform_fee(revenue, sub.plan, months_active)

                fee_in_cents = int(fee_details['final_fee'] * 100)

                print(f"🏪 Loja {store.id} - {fee_details['message']}")

                gateway_transaction_id = None
                if fee_in_cents > 0 and store.efi_payment_token:
                    try:
                        charge_response = create_one_time_charge(
                            payment_token=store.efi_payment_token,
                            amount_in_cents=fee_in_cents,
                            description=f"Investimento Plataforma - {first_day_of_previous_month.strftime('%m/%Y')}"
                        )
                        gateway_transaction_id = charge_response.get('charge_id')
                        print(f"  ✅ Valor de R${fee_details['final_fee']:.2f} processado")
                    except Exception as e:
                        print(f"  ❌ Processamento não realizado: {e}")

                # 4. Registra com nossos benefícios
                new_charge = models.MonthlyCharge(
                    store_id=store.id,
                    subscription_id=sub.id,
                    charge_date=today,
                    billing_period_start=first_day_of_previous_month,
                    billing_period_end=last_day_of_previous_month,
                    total_revenue=revenue,
                    calculated_fee=fee_details['final_fee'],
                    status="pending" if gateway_transaction_id else "no_charge",
                    gateway_transaction_id=gateway_transaction_id,
                    # ✅ REGISTRA NOSSOS DIFERENCIAIS
                    metadata={
                        'pricing_strategy': 'value_based',
                        'months_partnership': months_active,
                        'base_fee': float(fee_details['base_fee']),
                        'benefit_percentage': fee_details['discount_percentage'],
                        'benefit_type': fee_details['benefit_type'],
                        'fee_type': fee_details['fee_type'],
                        'effective_rate': fee_details['effective_rate'],
                        'has_special_benefit': fee_details['has_benefit']
                    }
                )
                db.add(new_charge)

            except Exception as e:
                print(f"❌ Processo interrompido para loja {store.id}: {e}")
                continue

        db.commit()
        print("✅ Processo de cobrança concluído com sucesso!")