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
    ✅ SERVIÇO ISOLADO DE ASSINATURAS

    Responsabilidade ÚNICA: Calcular e enriquecer dados de assinatura.
    Não depende de StoreService, não sabe nada sobre produtos/categorias.
    """

    @staticmethod
    def get_enriched_subscription(
            store: models.Store,
            db: GetDBDep,
    ) -> Optional[Dict[str, Any]]:
        """
        ✅ MÉTODO PRINCIPAL: Retorna assinatura completa e enriquecida

        Retorna um dict JSON pronto com TODOS os campos computados:
        - is_blocked
        - has_payment_method
        - billing_preview
        - card_info
        - warning_message
        - etc

        Este dict pode ser usado diretamente em:
        - Payloads de API REST
        - Eventos de Socket.IO
        - Respostas de endpoints específicos

        Args:
            store: Objeto ORM da loja (com subscriptions carregadas)
            db: Sessão do banco de dados

        Returns:
            Dict completo ou None se não houver assinatura
        """
        try:
            # 1. Busca assinatura ativa
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

            # 2. Calcula campos de negócio
            now = datetime.now(timezone.utc)
            end_date = subscription_db.current_period_end

            if end_date and end_date.tzinfo is None:
                end_date = end_date.replace(tzinfo=timezone.utc)

            days_remaining = (
                (end_date - now).days
                if end_date and now < end_date
                else 0
            )

            # 3. Status dinâmico e bloqueio
            dynamic_status, is_blocked, warning_message = (
                SubscriptionService._calculate_status(
                    status=subscription_db.status.lower(),
                    canceled_at=subscription_db.canceled_at,
                    end_date=end_date,
                    days_remaining=days_remaining,
                    now=now
                )
            )

            # 4. Verifica método de pagamento
            has_payment_method = bool(
                store.pagarme_customer_id and
                store.pagarme_card_id
            )

            # 5. Preview de cobrança
            billing_preview = BillingPreviewService.get_billing_preview(
                db=db,
                store=store
            )

            # 6. Informações do cartão
            card_info = None
            if store.pagarme_card_id and store.pagarme_customer_id:
                card_info = SubscriptionService._get_card_info(store)

            # 7. Histórico de cobranças
            billing_history = SubscriptionService._get_billing_history(store)

            # 8. Ações disponíveis
            can_cancel = dynamic_status == 'active'
            can_reactivate = (
                    dynamic_status == 'canceled' and
                    subscription_db.current_period_end > now
            )

            # 9. Log detalhado
            logger.info("═" * 60)
            logger.info(f"💳 [Subscription] Loja {store.id}:")
            logger.info(f"   Status DB: {subscription_db.status}")
            logger.info(f"   Status Calculado: {dynamic_status}")
            logger.info(f"   Bloqueada: {is_blocked}")
            logger.info(
                f"   Período: {subscription_db.current_period_start.date()} → {end_date.date() if end_date else 'N/A'}")
            logger.info(f"   Dias restantes: {days_remaining}")
            logger.info("═" * 60)

            # 10. ✅ RETORNA DICT COMPLETO E PRONTO
            return {
                # Campos do banco
                "id": subscription_db.id,
                "current_period_start": subscription_db.current_period_start,
                "current_period_end": subscription_db.current_period_end,
                "canceled_at": subscription_db.canceled_at,
                "gateway_subscription_id": subscription_db.gateway_subscription_id,
                "status": dynamic_status,

                # Campos computados (calculados acima)
                "is_blocked": is_blocked,
                "warning_message": warning_message,
                "has_payment_method": has_payment_method,

                # Relacionamentos (já validados)
                "plan": PlanSchema.model_validate(subscription_db.plan).model_dump(mode='json'),
                "subscribed_addons": [
                    addon.model_dump() if hasattr(addon, 'model_dump') else addon
                    for addon in subscription_db.subscribed_addons
                ],

                # Dados enriquecidos (de outros serviços)
                "billing_preview": billing_preview.model_dump(mode='json') if billing_preview else None,
                "card_info": card_info.model_dump(mode='json') if card_info else None,
                "billing_history": [item.model_dump(mode='json') for item in billing_history],

                # Ações disponíveis
                "can_cancel": can_cancel,
                "can_reactivate": can_reactivate,
            }

        except Exception as e:
            logger.error(f"❌ Erro ao enriquecer assinatura da loja {store.id}: {e}", exc_info=True)
            return None

    # ═══════════════════════════════════════════════════════════
    # MÉTODOS AUXILIARES (Lógica isolada e testável)
    # ═══════════════════════════════════════════════════════════

    @staticmethod
    def _calculate_status(
            status: str,
            canceled_at: Optional[datetime],
            end_date: Optional[datetime],
            days_remaining: int,
            now: datetime
    ) -> tuple[str, bool, Optional[str]]:
        """
        Calcula status dinâmico, bloqueio e mensagem de aviso.

        Lógica de negócio isolada e facilmente testável.
        """
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
                    f"Seu pagamento está pendente. Regularize até {grace_period_end.strftime('%d/%m/%Y')} para evitar o cancelamento."
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
        """
        Busca informações do cartão de crédito.

        TODO: Integrar com Pagar.me API para dados reais.
        """
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
        """
        Busca histórico de cobranças da loja.
        """
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