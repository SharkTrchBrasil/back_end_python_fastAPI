# src/api/admin/services/subscription_service.py
"""
Serviço de Gerenciamento de Assinaturas
========================================

Consolida e calcula o estado dinâmico da assinatura de uma loja.

✅ VERSÃO FINAL BLINDADA:
- Trata canceled_at NULL
- Trata datas sem timezone
- Trata todos os status possíveis
- Logs detalhados
- Tratamento de erros robusto

Autor: Sistema de Billing
Última atualização: 2025-01-17
"""

from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any
from decimal import Decimal
import logging

from src.core import models
from src.api.schemas.subscriptions.subscription_schemas import Plans

logger = logging.getLogger(__name__)


class SubscriptionService:
    """
    Serviço responsável por consolidar e calcular o estado dinâmico
    da assinatura de uma loja para ser enviado ao frontend.

    ✅ BLINDADO: Funciona em TODOS os cenários
    """

    @staticmethod
    def get_subscription_details(store: models.Store) -> Optional[Dict[str, Any]]:
        """
        ✅ Retorna detalhes da assinatura com status calculado dinamicamente

        Retorna None apenas se a loja NUNCA teve assinatura.
        Para lojas com histórico de assinatura (mesmo canceladas), retorna dados completos.

        Args:
            store: Modelo da loja com relacionamento 'subscriptions' carregado

        Returns:
            Dict com detalhes da assinatura ou None se não houver histórico
        """

        try:
            # ═══════════════════════════════════════════════════════════
            # 1. BUSCA ASSINATURA (MAIS RECENTE)
            # ═══════════════════════════════════════════════════════════

            subscription_db = (
                store.subscriptions[0]
                if store.subscriptions
                else None
            )

            if not subscription_db:
                logger.info(f"[Subscription] Loja {store.id}: Sem histórico de assinatura")
                return None

            if not subscription_db.plan:
                logger.warning(f"[Subscription] Loja {store.id}: Assinatura sem plano vinculado!")
                return None

            # ═══════════════════════════════════════════════════════════
            # 2. NORMALIZA DADOS
            # ═══════════════════════════════════════════════════════════

            now = datetime.now(timezone.utc)
            status = subscription_db.status.lower()
            end_date = subscription_db.current_period_end

            # ✅ Garante timezone
            if end_date and end_date.tzinfo is None:
                end_date = end_date.replace(tzinfo=timezone.utc)

            # ✅ Calcula dias restantes
            days_remaining = (
                (end_date - now).days
                if end_date and now < end_date
                else 0
            )

            # ═══════════════════════════════════════════════════════════
            # 3. CALCULA STATUS DINÂMICO E BLOQUEIO
            # ═══════════════════════════════════════════════════════════

            dynamic_status, is_blocked, warning_message = (
                SubscriptionService._calculate_status(
                    status=status,
                    canceled_at=subscription_db.canceled_at,
                    end_date=end_date,
                    days_remaining=days_remaining,
                    now=now
                )
            )

            # ═══════════════════════════════════════════════════════════
            # 4. VERIFICA MÉTODO DE PAGAMENTO
            # ═══════════════════════════════════════════════════════════

            has_payment_method = bool(
                store.pagarme_customer_id and
                store.pagarme_card_id
            )

            # ═══════════════════════════════════════════════════════════
            # 5. LOG DETALHADO
            # ═══════════════════════════════════════════════════════════

            logger.info("═" * 60)
            logger.info(f"💳 [Subscription] Loja {store.id}:")
            logger.info(f"   Status DB: {subscription_db.status}")
            logger.info(f"   Status Calculado: {dynamic_status}")
            logger.info(f"   Bloqueada: {is_blocked}")

            # ✅ Trata canceled_at NULL
            if subscription_db.canceled_at:
                try:
                    canceled_at_str = subscription_db.canceled_at.strftime('%d/%m/%Y %H:%M')
                except:
                    canceled_at_str = "data inválida"
            else:
                canceled_at_str = "N/A"

            logger.info(f"   Cancelada em: {canceled_at_str}")
            logger.info(
                f"   Período: {subscription_db.current_period_start.date()} → {end_date.date() if end_date else 'N/A'}")
            logger.info(f"   Dias restantes: {days_remaining}")
            logger.info(f"   Método pagamento: {has_payment_method}")
            logger.info("═" * 60)

            # ═══════════════════════════════════════════════════════════
            # 6. MONTA RESPOSTA
            # ═══════════════════════════════════════════════════════════

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
                "plan": Plans.model_validate(subscription_db.plan) if subscription_db.plan else None,
                "subscribed_addons": subscription_db.subscribed_addons,
            }

        except Exception as e:
            logger.error(f"❌ Erro ao calcular detalhes da assinatura: {e}", exc_info=True)
            # ✅ FALLBACK: Retorna dados básicos mesmo com erro
            return {
                "id": subscription_db.id if 'subscription_db' in locals() else None,
                "status": "error",
                "is_blocked": True,
                "warning_message": "Erro ao processar assinatura. Contate o suporte.",
                "has_payment_method": False,
                "plan": None,
                "subscribed_addons": [],
            }

    @staticmethod
    def _calculate_status(
            status: str,
            canceled_at: Optional[datetime],
            end_date: Optional[datetime],
            days_remaining: int,
            now: datetime
    ) -> tuple[str, bool, Optional[str]]:
        """
        ✅ Calcula status dinâmico, bloqueio e mensagem de aviso

        Returns:
            Tupla (dynamic_status, is_blocked, warning_message)
        """

        # ═══════════════════════════════════════════════════════════
        # CASO 1: CANCELADA
        # ═══════════════════════════════════════════════════════════

        if status == 'canceled':
            # ✅ Formata data de cancelamento (trata NULL)
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

            # ✅ Verifica se ainda tem acesso
            if days_remaining > 0:
                return (
                    'canceled',
                    False,  # NÃO bloqueia enquanto tiver dias pagos
                    (
                        f"Sua assinatura foi cancelada em {canceled_date_str}. "
                        f"Você manterá acesso até {end_date.strftime('%d/%m/%Y')} "
                        f"({days_remaining} dias restantes)."
                    )
                )
            else:
                return (
                    'expired',
                    True,  # Bloqueia após expirar
                    (
                        f"Sua assinatura foi cancelada em {canceled_date_str} e expirou. "
                        f"Reative para continuar usando a plataforma."
                    )
                )

        # ═══════════════════════════════════════════════════════════
        # CASO 2: TRIAL
        # ═══════════════════════════════════════════════════════════

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

        # ═══════════════════════════════════════════════════════════
        # CASO 3: ATIVA
        # ═══════════════════════════════════════════════════════════

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

        # ═══════════════════════════════════════════════════════════
        # CASO 4: PAGAMENTO PENDENTE
        # ═══════════════════════════════════════════════════════════

        elif status in ['past_due', 'unpaid']:
            return (
                'past_due',
                True,
                "Falha no pagamento. Atualize seus dados para reativar o acesso."
            )

        # ═══════════════════════════════════════════════════════════
        # CASO 5: EXPIRADA
        # ═══════════════════════════════════════════════════════════

        elif status == 'expired':
            return (
                'expired',
                True,
                "Sua assinatura expirou. Adicione um método de pagamento para reativar."
            )

        # ═══════════════════════════════════════════════════════════
        # CASO 6: STATUS DESCONHECIDO
        # ═══════════════════════════════════════════════════════════

        else:
            logger.warning(f"Status desconhecido: {status}")
            return (
                status,
                True,
                "Status da assinatura desconhecido. Entre em contato com o suporte."
            )