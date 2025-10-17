# Arquivo: src/api/jobs/billing.py
"""
Sistema de Cobrança Mensal - Versão Blindada
============================================

Características:
- ✅ Segurança: Validação robusta de dados
- ✅ Escalabilidade: Pronto para processamento assíncrono
- ✅ Resiliência: Tratamento completo de erros
- ✅ Observabilidade: Logs estruturados
- ✅ Idempotência: Evita cobranças duplicadas
- ✅ Auditoria: Metadados completos

Autor: Sistema de Billing
Última atualização: 2025-01-15
"""

from datetime import date, timedelta, datetime
from decimal import Decimal, InvalidOperation
from typing import Dict, Optional
import logging
from src.api.admin.services.billing_strategy import BillingStrategy


from sqlalchemy import select, func
from sqlalchemy.orm import Session, selectinload
from sqlalchemy.exc import SQLAlchemyError

# ✅ PAGAR.ME IMPORT
from src.api.admin.services.pagarme_service import pagarme_service, PagarmeError

from src.api.admin.utils.business_days import is_first_business_day
from src.core import models
from src.core.database import get_db_manager

# ✅ CONFIGURAÇÃO DE LOGGING ESTRUTURADO
logger = logging.getLogger(__name__)


class BillingError(Exception):
    """Exceção base para erros de cobrança"""
    pass


class InvalidPlanError(BillingError):
    """Erro quando o plano está mal configurado"""
    pass


class InvalidRevenueError(BillingError):
    """Erro quando o faturamento é inválido"""
    pass


def validate_plan(plan: models.Plans) -> None:
    """
    ✅ SEGURANÇA: Valida configuração do plano

    Raises:
        InvalidPlanError: Se o plano estiver mal configurado
    """
    if not plan:
        raise InvalidPlanError("Plano não fornecido")

    # Valida campos obrigatórios
    required_fields = {
        'minimum_fee': 'Taxa mínima',
        'revenue_percentage': 'Percentual de receita',
        'percentage_tier_start': 'Início do Tier 2',
        'percentage_tier_end': 'Fim do Tier 2'
    }

    missing = []
    for field, name in required_fields.items():
        if getattr(plan, field, None) is None:
            missing.append(name)

    if missing:
        raise InvalidPlanError(
            f"Plano ID {plan.id} incompleto. Campos faltando: {', '.join(missing)}"
        )

    # Valida valores positivos
    if plan.minimum_fee < 0:
        raise InvalidPlanError("Taxa mínima não pode ser negativa")

    if plan.revenue_percentage < 0:
        raise InvalidPlanError("Percentual de receita não pode ser negativo")

    # Valida lógica dos tiers
    tier_start = Decimal(plan.percentage_tier_start) / 100
    tier_end = Decimal(plan.percentage_tier_end) / 100

    if tier_start >= tier_end:
        raise InvalidPlanError(
            f"Tier 1 (R$ {tier_start}) deve ser menor que Tier 2 (R$ {tier_end})"
        )


def calculate_platform_fee(
        monthly_revenue: Decimal,
        plan: models.Plans,
        months_active: int = 0
) -> Dict:
    """
    ✅ ROBUSTO: Calcula a taxa com validação completa

    Args:
        monthly_revenue: Faturamento mensal em Reais
        plan: Plano de assinatura
        months_active: Meses desde o início da assinatura

    Returns:
        Dict com detalhes da cobrança

    Raises:
        InvalidRevenueError: Se o faturamento for inválido
        InvalidPlanError: Se o plano estiver mal configurado
    """

    # ✅ 1. VALIDAÇÃO DE ENTRADA
    if not isinstance(monthly_revenue, Decimal):
        try:
            monthly_revenue = Decimal(str(monthly_revenue))
        except (ValueError, InvalidOperation) as e:
            raise InvalidRevenueError(f"Faturamento inválido: {e}")

    if monthly_revenue < 0:
        raise InvalidRevenueError(
            f"Faturamento negativo inválido: R$ {monthly_revenue}"
        )

    # Valida plano
    validate_plan(plan)

    # ✅ 2. CONVERSÃO SEGURA: Centavos → Reais
    try:
        minimum_fee_reais = Decimal(plan.minimum_fee) / 100
        revenue_cap_reais = (
            Decimal(plan.revenue_cap_fee) / 100
            if plan.revenue_cap_fee
            else None
        )
        tier_start_reais = Decimal(plan.percentage_tier_start) / 100
        tier_end_reais = Decimal(plan.percentage_tier_end) / 100
    except (TypeError, ValueError, InvalidOperation) as e:
        raise InvalidPlanError(f"Erro ao converter valores do plano: {e}")

    # ✅ 3. CALCULA TAXA BASE CONFORME O TIER
    if monthly_revenue <= tier_start_reais:
        # TIER 1: Taxa mínima fixa
        base_fee = minimum_fee_reais
        fee_type = "Taxa Mínima (Tier 1)"
        tier = 1

    elif monthly_revenue <= tier_end_reais:
        # TIER 2: Percentual do faturamento
        base_fee = monthly_revenue * plan.revenue_percentage
        # Garante mínimo de R$ 45,00 no Tier 2
        base_fee = max(base_fee, Decimal('45.00'))
        fee_type = f"Percentual (Tier 2: {(plan.revenue_percentage * 100):.1f}%)"
        tier = 2

    else:
        # TIER 3: Taxa máxima fixa
        base_fee = (
            revenue_cap_reais
            if revenue_cap_reais
            else monthly_revenue * plan.revenue_percentage
        )
        fee_type = "Taxa Máxima (Tier 3)"
        tier = 3

    # ✅ 4. APLICA BENEFÍCIOS PROGRESSIVOS
    if months_active == 0 and plan.first_month_free:
        final_fee = Decimal('0.00')
        discount_percentage = Decimal('1.00')  # 100%
        benefit_type = "🎁 1º mês por nossa conta!"

    elif months_active == 1 and plan.second_month_discount:
        final_fee = base_fee * plan.second_month_discount
        discount_percentage = Decimal('1.00') - plan.second_month_discount
        benefit_type = "🔥 2º mês com 50% de desconto!"

    elif months_active == 2 and plan.third_month_discount:
        final_fee = base_fee * plan.third_month_discount
        discount_percentage = Decimal('1.00') - plan.third_month_discount
        benefit_type = "💫 3º mês com 25% de desconto!"

    else:
        final_fee = base_fee
        discount_percentage = Decimal('0.00')
        benefit_type = "💎 Plano ativo - Preço justo"

    # ✅ 5. CALCULA TAXA EFETIVA
    effective_rate = (
        float(final_fee / monthly_revenue * 100)
        if monthly_revenue > 0
        else 0
    )

    # ✅ 6. GERA MENSAGEM
    message = generate_positive_message(benefit_type, final_fee, effective_rate)

    # ✅ 7. RETORNA DADOS COMPLETOS
    return {
        'base_fee': base_fee,
        'final_fee': final_fee,
        'discount_percentage': float(discount_percentage * 100),
        'benefit_type': benefit_type,
        'fee_type': fee_type,
        'effective_rate': effective_rate,
        'message': message,
        'has_benefit': discount_percentage > 0,
        'tier': tier,
        'tier_info': {
            'tier_1_max': float(tier_start_reais),
            'tier_2_max': float(tier_end_reais),
            'tier_1_fee': float(minimum_fee_reais),
            'tier_2_percentage': float(plan.revenue_percentage * 100),
            'tier_3_fee': float(revenue_cap_reais) if revenue_cap_reais else None
        }
    }


def generate_positive_message(
        benefit_type: str,
        final_fee: Decimal,
        effective_rate: float
) -> str:
    """Gera mensagem positiva sobre a cobrança"""
    if final_fee == 0:
        return f"{benefit_type} Aproveite nosso investimento no seu negócio!"
    elif effective_rate < 2:
        return f"{benefit_type} Taxa especial de apenas {effective_rate:.1f}%!"
    else:
        return f"{benefit_type} Valor justo de {effective_rate:.1f}% sobre seu faturamento!"


def get_store_revenue_for_period(
        db: Session,
        store_id: int,
        start_date: date,
        end_date: date
) -> Decimal:
    """
    ✅ SEGURO: Calcula faturamento com tratamento de erros

    Returns:
        Faturamento em Reais (Decimal)
    """
    try:
        start_datetime = datetime.combine(start_date, datetime.min.time())
        end_datetime = datetime.combine(end_date, datetime.max.time())

        total_revenue_cents = db.query(
            func.sum(models.Order.total_price)
        ).filter(
            models.Order.store_id == store_id,
            models.Order.order_status.in_(['finalized', 'delivered']),
            models.Order.created_at.between(start_datetime, end_datetime)
        ).scalar()

        # Converte centavos → Reais
        revenue_reais = Decimal(total_revenue_cents or 0) / 100
        return revenue_reais.quantize(Decimal('0.01'))

    except SQLAlchemyError as e:
        logger.error("database_error_revenue_calculation", extra={
            "store_id": store_id,
            "start_date": str(start_date),
            "end_date": str(end_date),
            "error": str(e)
        })
        return Decimal('0')

    except Exception as e:
        logger.error("unexpected_error_revenue_calculation", extra={
            "store_id": store_id,
            "error": str(e),
            "error_type": type(e).__name__
        }, exc_info=True)
        return Decimal('0')


def calculate_months_active(
        subscription: models.StoreSubscription,
        today: date
) -> int:
    """
    ✅ SEGURO: Calcula meses ativos com validação
    """
    try:
        from dateutil.relativedelta import relativedelta

        if not subscription.current_period_start:
            logger.warning("subscription_without_start_date", extra={
                "subscription_id": subscription.id
            })
            return 0

        start_date = subscription.current_period_start.date()
        months_active = relativedelta(today, start_date).months

        return max(0, months_active)

    except Exception as e:
        logger.error("error_calculating_months_active", extra={
            "subscription_id": subscription.id,
            "error": str(e)
        })
        return 0


def check_duplicate_charge(
        db: Session,
        store_id: int,
        billing_period_start: date,
        billing_period_end: date
) -> Optional[models.MonthlyCharge]:
    """
    ✅ IDEMPOTÊNCIA: Verifica se já existe cobrança para o período

    Returns:
        MonthlyCharge existente ou None
    """
    try:
        return db.query(models.MonthlyCharge).filter(
            models.MonthlyCharge.store_id == store_id,
            models.MonthlyCharge.billing_period_start == billing_period_start,
            models.MonthlyCharge.billing_period_end == billing_period_end
        ).first()
    except SQLAlchemyError as e:
        logger.error("error_checking_duplicate_charge", extra={
            "store_id": store_id,
            "error": str(e)
        })
        return None


# src/api/jobs/billing.py

def process_single_store_charge(
        db: Session,
        subscription: models.StoreSubscription,
        first_day_of_month: date,
        last_day_of_month: date,
        today: date
) -> bool:
    """
    ✅ VERSÃO BLINDADA: Processa cobrança com validações rigorosas

    NÃO COBRA:
    - Assinaturas canceladas
    - Assinaturas que iniciaram depois do período
    - Assinaturas já cobradas no período
    - Assinaturas sem método de pagamento (marca como failed)

    Returns:
        True se processou com sucesso (ou pulou corretamente)
        False se houve erro crítico
    """

    store = subscription.store

    if not store or not subscription.plan:
        logger.warning("subscription_without_store_or_plan", extra={
            "subscription_id": subscription.id,
            "has_store": bool(store),
            "has_plan": bool(subscription.plan)
        })
        return False

    # ═══════════════════════════════════════════════════════════
    # ✅ VALIDAÇÃO 1: NÃO COBRAR CANCELADAS
    # ═══════════════════════════════════════════════════════════

    if subscription.status == "canceled":
        logger.info("subscription_canceled_skipping", extra={
            "subscription_id": subscription.id,
            "store_id": store.id,
            "canceled_at": subscription.canceled_at.isoformat() if subscription.canceled_at else None,
            "period_end": subscription.current_period_end.isoformat()
        })
        return True  # ← Retorna sucesso (não é erro, só não processa)

    # ═══════════════════════════════════════════════════════════
    # ✅ CRIA SAVEPOINT (TRANSAÇÃO ISOLADA)
    # ═══════════════════════════════════════════════════════════

    savepoint = db.begin_nested()

    try:
        # ═══════════════════════════════════════════════════════════
        # ✅ VALIDAÇÃO 2: VERIFICA DUPLICATA (IDEMPOTÊNCIA)
        # ═══════════════════════════════════════════════════════════

        existing_charge = check_duplicate_charge(
            db, store.id, first_day_of_month, last_day_of_month
        )

        if existing_charge:
            logger.info("charge_already_exists", extra={
                "store_id": store.id,
                "charge_id": existing_charge.id,
                "status": existing_charge.status
            })
            savepoint.commit()
            return True

        # ═══════════════════════════════════════════════════════════
        # ✅ VALIDAÇÃO 3: VERIFICA SE ASSINATURA COBRIA ESSE PERÍODO
        # ═══════════════════════════════════════════════════════════

        subscription_start = subscription.current_period_start.date()
        subscription_end = subscription.current_period_end.date()

        # Se a assinatura começou DEPOIS do fim do período de cobrança, pula
        if subscription_start > last_day_of_month:
            logger.info("subscription_started_after_billing_period", extra={
                "store_id": store.id,
                "subscription_start": str(subscription_start),
                "billing_period_end": str(last_day_of_month)
            })
            savepoint.commit()
            return True

        # Se a assinatura terminou ANTES do início do período de cobrança, pula
        if subscription_end < first_day_of_month:
            logger.info("subscription_ended_before_billing_period", extra={
                "store_id": store.id,
                "subscription_end": str(subscription_end),
                "billing_period_start": str(first_day_of_month)
            })
            savepoint.commit()
            return True

        # ═══════════════════════════════════════════════════════════
        # ✅ 4. CALCULA FATURAMENTO DO PERÍODO
        # ═══════════════════════════════════════════════════════════

        revenue = get_store_revenue_for_period(
            db, store.id, first_day_of_month, last_day_of_month
        )

        # ═══════════════════════════════════════════════════════════
        # ✅ 5. CALCULA TAXA (COM BENEFÍCIOS PROGRESSIVOS)
        # ═══════════════════════════════════════════════════════════

        months_active = calculate_months_active(subscription, today)

        try:
            fee_details = calculate_platform_fee(
                revenue,
                subscription.plan,
                months_active
            )
        except (InvalidPlanError, InvalidRevenueError) as e:
            logger.error("fee_calculation_error", extra={
                "store_id": store.id,
                "error": str(e),
                "revenue": float(revenue)
            })
            savepoint.rollback()
            return False

        fee_in_cents = int(fee_details['final_fee'] * 100)

        # ═══════════════════════════════════════════════════════════
        # ✅ 6. LOG DETALHADO DA COBRANÇA CALCULADA
        # ═══════════════════════════════════════════════════════════

        logger.info("billing_calculated", extra={
            "store_id": store.id,
            "store_name": store.name,
            "revenue": float(revenue),
            "calculated_fee": float(fee_details['final_fee']),
            "tier": fee_details['tier'],
            "months_active": months_active,
            "has_benefit": fee_details['has_benefit']
        })

        # ═══════════════════════════════════════════════════════════
        # ✅ 7. PROCESSA PAGAMENTO (SE HOUVER VALOR)
        # ═══════════════════════════════════════════════════════════

        gateway_transaction_id = None
        charge_status = "no_charge"

        if fee_in_cents > 0:
            # Valida se tem método de pagamento cadastrado
            if not store.pagarme_customer_id or not store.pagarme_card_id:
                logger.warning("store_without_payment_method", extra={
                    "store_id": store.id,
                    "has_customer_id": bool(store.pagarme_customer_id),
                    "has_card_id": bool(store.pagarme_card_id)
                })
                charge_status = "failed"
            else:
                try:
                    # ✅ PAGAR.ME: Cria cobrança
                    charge_response = pagarme_service.create_charge(
                        customer_id=store.pagarme_customer_id,
                        card_id=store.pagarme_card_id,
                        amount_in_cents=fee_in_cents,
                        description=f"Mensalidade {store.name} - {first_day_of_month.strftime('%m/%Y')}",
                        store_id=store.id,
                        metadata={
                            "type": "monthly_charge",
                            "billing_period": f"{first_day_of_month} to {last_day_of_month}",
                            "tier": fee_details['tier'],
                            "months_active": months_active
                        }
                    )

                    gateway_transaction_id = charge_response["id"]
                    charge_status = "pending"

                    logger.info("charge_created", extra={
                        "store_id": store.id,
                        "gateway_transaction_id": gateway_transaction_id,
                        "amount_cents": fee_in_cents
                    })

                except PagarmeError as e:
                    logger.error("charge_creation_failed", extra={
                        "store_id": store.id,
                        "amount_cents": fee_in_cents,
                        "error": str(e),
                        "error_type": type(e).__name__
                    }, exc_info=True)
                    charge_status = "failed"

                except Exception as e:
                    logger.error("charge_creation_unexpected_error", extra={
                        "store_id": store.id,
                        "amount_cents": fee_in_cents,
                        "error": str(e),
                        "error_type": type(e).__name__
                    }, exc_info=True)
                    charge_status = "failed"

        # ═══════════════════════════════════════════════════════════
        # ✅ 8. REGISTRA NO BANCO (SEMPRE, MESMO SE NÃO COBROU)
        # ═══════════════════════════════════════════════════════════

        new_charge = models.MonthlyCharge(
            store_id=store.id,
            subscription_id=subscription.id,
            charge_date=today,
            billing_period_start=first_day_of_month,
            billing_period_end=last_day_of_month,
            total_revenue=revenue,
            calculated_fee=fee_details['final_fee'],
            status=charge_status,
            gateway_transaction_id=gateway_transaction_id,
            charge_metadata={
                'pricing_strategy': 'tiered_revenue_based',
                'months_partnership': months_active,
                'base_fee': float(fee_details['base_fee']),
                'benefit_percentage': fee_details['discount_percentage'],
                'benefit_type': fee_details['benefit_type'],
                'fee_type': fee_details['fee_type'],
                'effective_rate': fee_details['effective_rate'],
                'has_special_benefit': fee_details['has_benefit'],
                'tier': fee_details['tier'],
                'tier_info': fee_details['tier_info']
            }
        )

        db.add(new_charge)
        db.flush()

        # ═══════════════════════════════════════════════════════════
        # ✅ 9. ATUALIZA PERÍODO DA ASSINATURA (CRÍTICO!)
        # ═══════════════════════════════════════════════════════════

        next_period_start = last_day_of_month + timedelta(days=1)
        next_period_end = (next_period_start + timedelta(days=32)).replace(day=1) - timedelta(days=1)

        subscription.current_period_start = next_period_start
        subscription.current_period_end = next_period_end

        logger.info("subscription_period_updated", extra={
            "subscription_id": subscription.id,
            "new_period_start": str(next_period_start),
            "new_period_end": str(next_period_end)
        })

        logger.info("charge_saved", extra={
            "store_id": store.id,
            "charge_id": new_charge.id,
            "status": charge_status
        })

        # ═══════════════════════════════════════════════════════════
        # ✅ 10. COMMIT DA TRANSAÇÃO
        # ═══════════════════════════════════════════════════════════

        savepoint.commit()
        return True

    except SQLAlchemyError as e:
        savepoint.rollback()
        logger.error("database_error_processing_charge", extra={
            "store_id": store.id,
            "subscription_id": subscription.id,
            "error": str(e)
        }, exc_info=True)
        return False

    except Exception as e:
        savepoint.rollback()
        logger.error("unexpected_error_processing_charge", extra={
            "store_id": store.id,
            "subscription_id": subscription.id,
            "error": str(e),
            "error_type": type(e).__name__
        }, exc_info=True)
        return False




def generate_monthly_charges():
    """
    ✅ VERSÃO HÍBRIDA: Processa cobranças baseada na estratégia

    COMPORTAMENTO:
    - Roda TODO DIA às 03:00 UTC
    - Verifica quais lojas devem ser cobradas HOJE
    - Usa BillingStrategy para decidir data de cobrança
    """

    today = date.today()

    logger.info("═" * 60)
    logger.info(f"🔍 [Billing Job] Verificando cobranças para {today}")
    logger.info("═" * 60)

    with get_db_manager() as db:
        try:
            # ═══════════════════════════════════════════════════════════
            # 1. BUSCA TODAS AS ASSINATURAS ATIVAS
            # ═══════════════════════════════════════════════════════════

            active_subscriptions = db.execute(
                select(models.StoreSubscription)
                .options(selectinload(models.StoreSubscription.store))
                .where(
                    models.StoreSubscription.status == 'active'
                )
            ).scalars().all()

            logger.info(f"📋 Encontradas {len(active_subscriptions)} assinaturas ativas")

            # ═══════════════════════════════════════════════════════════
            # 2. FILTRA QUAIS DEVEM SER COBRADAS HOJE
            # ═══════════════════════════════════════════════════════════

            subscriptions_to_charge = []

            for sub in active_subscriptions:
                # ✅ NOVA LÓGICA: Usa estratégia híbrida
                next_billing_date = BillingStrategy.get_billing_date(sub, db)

                # Se a data de cobrança é HOJE, adiciona na lista
                if next_billing_date.date() == today:
                    subscriptions_to_charge.append(sub)
                    logger.info(
                        f"  ✅ Loja {sub.store.id} ({sub.store.name}) "
                        f"será cobrada hoje (estratégia: "
                        f"{'Aniversário' if next_billing_date.day != 1 else 'Dia 1º'})"
                    )

            logger.info(f"💳 {len(subscriptions_to_charge)} lojas para cobrar hoje")

            # ═══════════════════════════════════════════════════════════
            # 3. PROCESSA COBRANÇAS
            # ═══════════════════════════════════════════════════════════

            success_count = 0
            error_count = 0

            for subscription in subscriptions_to_charge:
                try:
                    result = process_single_store_charge(
                        db=db,
                        subscription=subscription,
                        first_day_of_month=_get_billing_period_start(subscription),
                        last_day_of_month=_get_billing_period_end(subscription),
                        today=today
                    )

                    if result:
                        success_count += 1
                    else:
                        error_count += 1

                except Exception as e:
                    logger.error(f"Erro ao processar loja {subscription.store_id}: {e}")
                    error_count += 1

            db.commit()

            logger.info("═" * 60)
            logger.info(f"✅ Job concluído: {success_count} sucesso, {error_count} erros")
            logger.info("═" * 60)

        except Exception as e:
            db.rollback()
            logger.error(f"❌ Erro crítico no job: {e}", exc_info=True)
            raise


def _get_billing_period_start(subscription: models.StoreSubscription) -> date:
    """Retorna início do período de cobrança"""
    return subscription.current_period_start.date()


def _get_billing_period_end(subscription: models.StoreSubscription) -> date:
    """Retorna fim do período de cobrança"""
    return subscription.current_period_end.date()

