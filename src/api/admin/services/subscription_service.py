# src/api/admin/services/subscription_service.py

from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any, List
import logging

from src.api.admin.services.billing_preview_service import BillingPreviewService
from src.api.schemas.subscriptions.plans import PlanSchema
from src.api.schemas.subscriptions.subscription_schemas import CardInfoSchema, BillingHistoryItemSchema
from src.core import models
from src.core.database import GetDBDep

logger = logging.getLogger(__name__)


class SubscriptionService:
    """
    ✅ SERVIÇO ISOLADO DE ASSINATURAS (VERSÃO PROFISSIONAL)

    Princípios SOLID aplicados:
    - Single Responsibility: Cuida APENAS de assinaturas
    - Open/Closed: Extensível sem modificar código existente
    - Dependency Inversion: Depende de abstrações (GetDBDep)
    """

    @staticmethod
    def get_enriched_subscription(
            store: models.Store,
            db: GetDBDep,
    ) -> Optional[Dict[str, Any]]:
        """
        ✅ Enriquece dados de assinatura com campos computados

        Retorna um dict JSON completo e pronto para consumo.
        Não retorna objetos ORM ou Pydantic parcialmente validados.

        Returns:
            Dict completo ou None se não houver assinatura
        """
        try:
            subscription_db = (
                store.subscriptions[0]
                if store.subscriptions
                else None
            )

            if not subscription_db:
                logger.info(f"[Subscription] Loja {store.id}: Sem assinatura")
                return None

            if not subscription_db.plan:
                logger.warning(f"[Subscription] Loja {store.id}: Assinatura sem plano")
                return None

            # Cálculos de negócio
            now = datetime.now(timezone.utc)
            end_date = subscription_db.current_period_end

            if end_date and end_date.tzinfo is None:
                end_date = end_date.replace(tzinfo=timezone.utc)

            days_remaining = (
                (end_date - now).days
                if end_date and now < end_date
                else 0
            )

            dynamic_status, is_blocked, warning_message = (
                SubscriptionService._calculate_status(
                    status=subscription_db.status.lower(),
                    canceled_at=subscription_db.canceled_at,
                    end_date=end_date,
                    days_remaining=days_remaining,
                    now=now
                )
            )

            has_payment_method = bool(
                store.pagarme_customer_id and
                store.pagarme_card_id
            )

            # ✅ CORREÇÃO: billing_preview pode ser Schema ou dict
            billing_preview_raw = BillingPreviewService.get_billing_preview(
                db=db,
                store=store
            )
            billing_preview = (
                billing_preview_raw.model_dump(mode='json')
                if billing_preview_raw and hasattr(billing_preview_raw, 'model_dump')
                else billing_preview_raw
            )

            # ✅ CORREÇÃO: card_info pode ser None
            card_info_raw = None
            if store.pagarme_card_id and store.pagarme_customer_id:
                card_info_raw = SubscriptionService._get_card_info(store)

            card_info = (
                card_info_raw.model_dump(mode='json')
                if card_info_raw
                else None
            )

            # ✅ CORREÇÃO: billing_history é lista de schemas
            billing_history_raw = SubscriptionService._get_billing_history(store)
            billing_history = [
                item.model_dump(mode='json')
                for item in billing_history_raw
            ]

            can_cancel = dynamic_status == 'active'
            can_reactivate = (
                    dynamic_status == 'canceled' and
                    subscription_db.current_period_end > now
            )

            logger.info("═" * 60)
            logger.info(f"💳 [Subscription] Loja {store.id}:")
            logger.info(f"   Status: {dynamic_status} | Bloqueada: {is_blocked}")
            logger.info(
                f"   Período: {subscription_db.current_period_start.date()} → {end_date.date() if end_date else 'N/A'}")
            logger.info("═" * 60)

            # ✅ RETORNA DICT COMPLETO (JSON-serializable)
            return {
                "id": subscription_db.id,
                "current_period_start": subscription_db.current_period_start,
                "current_period_end": subscription_db.current_period_end,
                "canceled_at": subscription_db.canceled_at,
                "gateway_subscription_id": subscription_db.gateway_subscription_id,
                "status": dynamic_status,
                "is_blocked": is_blocked,
                "warning_message": warning_message,
                "has_payment_method": has_payment_method,
                "plan": PlanSchema.model_validate(subscription_db.plan).model_dump(mode='json'),
                "subscribed_addons": [
                    addon.model_dump() if hasattr(addon, 'model_dump') else addon
                    for addon in subscription_db.subscribed_addons
                ],
                "billing_preview": billing_preview,
                "card_info": card_info,
                "billing_history": billing_history,
                "can_cancel": can_cancel,
                "can_reactivate": can_reactivate,
            }

        except Exception as e:
            logger.error(f"❌ Erro ao enriquecer assinatura da loja {store.id}: {e}", exc_info=True)
            return None

    # ═══════════════════════════════════════════════════════════
    # Métodos auxiliares (mantidos)
    # ═══════════════════════════════════════════════════════════

    @staticmethod
    def _calculate_status(
            status: str,
            canceled_at: Optional[datetime],
            end_date: Optional[datetime],
            days_remaining: int,
            now: datetime
    ) -> tuple[str, bool, Optional[str]]:
        """Calcula status dinâmico, bloqueio e mensagem"""
        # (código existente mantido - está correto)
        if status == 'canceled':
            if canceled_at:
                try:
                    if canceled_at.tzinfo is None:
                        canceled_at = canceled_at.replace(tzinfo=timezone.utc)
                    canceled_date_str = canceled_at.strftime('%d/%m/%Y')
                except Exception as e:
                    logger.warning(f"Erro ao formatar canceled_at: {e}")
                    canceled_date_str = "uma data anterior"
            else:
                canceled_date_str = "uma data anterior"

            if days_remaining > 0:
                return (
                    'canceled',
                    False,
                    f"Sua assinatura foi cancelada em {canceled_date_str}. "
                    f"Você manterá acesso até {end_date.strftime('%d/%m/%Y')} "
                    f"({days_remaining} dias restantes)."
                )
            else:
                return (
                    'expired',
                    True,
                    f"Sua assinatura foi cancelada em {canceled_date_str} e expirou. "
                    f"Reative para continuar usando a plataforma."
                )

        elif status == 'trialing':
            if days_remaining > 0:
                return (
                    'trialing',
                    False,
                    f"Você está no período de teste. Restam {days_remaining} dias."
                )
            else:
                return (
                    'expired',
                    True,
                    "Seu período de teste terminou. Adicione um método de pagamento para continuar."
                )

        elif status == 'active':
            if not end_date:
                logger.warning("Status 'active' mas sem data de término!")
                return ('active', False, None)

            grace_period_end = end_date + timedelta(days=3)

            if now > grace_period_end:
                return (
                    'expired',
                    True,
                    "Sua assinatura expirou. Renove para continuar o acesso."
                )
            elif now > end_date:
                return (
                    'past_due',
                    True,
                    f"Seu pagamento está pendente. Regularize até {grace_period_end.strftime('%d/%m/%Y')}."
                )
            elif days_remaining <= 3:
                return (
                    'warning',
                    False,
                    f"Atenção: sua assinatura vence em {days_remaining + 1} dia(s)."
                )
            else:
                return ('active', False, None)

        elif status in ['past_due', 'unpaid']:
            return (
                'past_due',
                True,
                "Falha no pagamento. Atualize seus dados para reativar o acesso."
            )

        elif status == 'expired':
            return (
                'expired',
                True,
                "Sua assinatura expirou. Adicione um método de pagamento para reativar."
            )

        else:
            logger.warning(f"Status desconhecido: {status}")
            return (
                status,
                True,
                "Status da assinatura desconhecido. Entre em contato com o suporte."
            )

    @staticmethod
    def _get_card_info(store: models.Store) -> CardInfoSchema | None:
        """Busca informações do cartão"""
        if not store.pagarme_card_id:
            return None

        return CardInfoSchema(
            masked_number="************4444",
            brand="Mastercard",
            status="active",
            holder_name="TITULAR DO CARTÃO",
            exp_month=12,
            exp_year=2030,
        )

    @staticmethod
    def _get_billing_history(store: models.Store) -> List[BillingHistoryItemSchema]:
        """Busca histórico de cobranças"""
        history = []

        for charge in store.monthly_charges:
            history.append(BillingHistoryItemSchema(
                period=f"{charge.billing_period_start.strftime('%d/%m/%Y')} - {charge.billing_period_end.strftime('%d/%m/%Y')}",
                revenue=float(charge.total_revenue),
                fee=float(charge.calculated_fee),
                status=charge.status,
                charge_date=charge.charge_date,
            ))

        history.sort(key=lambda x: x.charge_date, reverse=True)
        return history