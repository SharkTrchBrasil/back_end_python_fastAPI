# src/api/admin/services/subscription_service.py

from datetime import datetime, date, timezone
from typing import Optional, Dict, Any
from src.core import models
import logging

logger = logging.getLogger(__name__)


class SubscriptionService:
    """
    Serviço responsável por consolidar e calcular o estado dinâmico
    da assinatura de uma loja para ser enviado ao frontend.

    ✅ VERSÃO BLINDADA - Retorna dados mesmo se cancelada
    """

    @staticmethod
    def get_subscription_details(store: models.Store) -> Optional[Dict[str, Any]]:
        """
        ✅ CORRIGIDO: Retorna detalhes de QUALQUER assinatura (ativa, trial, canceled, expired)

        Só retorna None se a loja NUNCA teve assinatura.
        """

        # ✅ MUDANÇA CRÍTICA: Busca QUALQUER assinatura, não apenas ativa
        subscription_db = store.subscriptions[0] if store.subscriptions else None

        if not subscription_db:
            logger.info(f"[Subscription] Loja {store.id} não possui nenhuma assinatura (nem histórico).")
            return None

        if not subscription_db.plan:
            logger.warning(f"[Subscription] Loja {store.id} tem assinatura sem plano vinculado!")
            return None

        # --- Lógica de Cálculo de Status ---
        now = datetime.now(timezone.utc)
        end_date = subscription_db.current_period_end

        if end_date and end_date.tzinfo is None:
            end_date = end_date.replace(tzinfo=timezone.utc)

        dynamic_status = subscription_db.status
        is_blocked = False
        warning_message = None

        # ═══════════════════════════════════════════════════════════
        # 🔴 TRATAMENTO DE ASSINATURA CANCELADA
        # ═══════════════════════════════════════════════════════════

        if subscription_db.status == 'canceled':
            # Verifica se ainda está dentro do período pago
            if end_date and now < end_date:
                # ✅ CANCELADA MAS AINDA TEM ACESSO
                dynamic_status = 'canceled'
                is_blocked = False  # Mantém acesso até o fim
                days_remaining = (end_date - now).days
                warning_message = (
                    f"Sua assinatura foi cancelada em {subscription_db.canceled_at.strftime('%d/%m/%Y')}. "
                    f"Você ainda tem acesso até {end_date.strftime('%d/%m/%Y')} ({days_remaining} dias restantes)."
                )
                logger.info(
                    f"[Subscription] Loja {store.id}: Cancelada mas com {days_remaining} dias de acesso restantes")
            else:
                # ❌ CANCELADA E JÁ EXPIROU
                dynamic_status = 'expired'
                is_blocked = True
                warning_message = (
                    f"Sua assinatura foi cancelada em {subscription_db.canceled_at.strftime('%d/%m/%Y')} "
                    f"e expirou em {end_date.strftime('%d/%m/%Y') if end_date else 'data desconhecida'}. "
                    f"Renove para continuar usando o sistema."
                )
                logger.info(f"[Subscription] Loja {store.id}: Cancelada e expirada")

        # ═══════════════════════════════════════════════════════════
        # 🟡 TRATAMENTO DE TRIAL
        # ═══════════════════════════════════════════════════════════

        elif subscription_db.status == 'trialing':
            if end_date:
                remaining_days = (end_date - now).days
                if remaining_days >= 0:
                    warning_message = f"Seu teste gratuito termina em {remaining_days + 1} dia(s)."
                else:
                    dynamic_status = 'expired'
                    is_blocked = True
                    warning_message = "Seu período de teste terminou. Adicione um método de pagamento para continuar."

        # ═══════════════════════════════════════════════════════════
        # 🔴 TRATAMENTO DE PAGAMENTO PENDENTE
        # ═══════════════════════════════════════════════════════════

        elif subscription_db.status in ['past_due', 'unpaid']:
            dynamic_status = 'past_due'
            is_blocked = True
            warning_message = "Falha no pagamento. Atualize seus dados para reativar o acesso."

        # ═══════════════════════════════════════════════════════════
        # 🟢 TRATAMENTO DE ATIVA
        # ═══════════════════════════════════════════════════════════

        elif subscription_db.status == 'active':
            if not end_date:
                logger.warning(f"[Subscription] Loja {store.id}: Status 'active' mas sem data de término!")
                dynamic_status = 'active'
                is_blocked = False
            else:
                grace_period_end = end_date + timedelta(days=3)

                if now > grace_period_end:
                    dynamic_status = "expired"
                    is_blocked = True
                    warning_message = "Sua assinatura expirou. Renove para continuar o acesso."
                elif now > end_date:
                    dynamic_status = "past_due"
                    is_blocked = True
                    warning_message = f"Seu pagamento está pendente. Regularize até {grace_period_end.strftime('%d/%m/%Y')} para evitar o cancelamento."
                elif (end_date - now).days <= 3:
                    remaining_days = (end_date - now).days
                    dynamic_status = "warning"
                    is_blocked = False
                    warning_message = f"Atenção: sua assinatura vence em {remaining_days + 1} dia(s)."
                else:
                    dynamic_status = "active"
                    is_blocked = False

        # ═══════════════════════════════════════════════════════════
        # ⚫ TRATAMENTO DE STATUS DESCONHECIDO
        # ═══════════════════════════════════════════════════════════

        else:
            is_blocked = True
            warning_message = "O status da sua assinatura é desconhecido. Contate o suporte."

        # ═══════════════════════════════════════════════════════════
        # 💳 VERIFICA MÉTODO DE PAGAMENTO
        # ═══════════════════════════════════════════════════════════

        has_payment_method = bool(
            store.pagarme_customer_id and
            store.pagarme_card_id
        )

        # ═══════════════════════════════════════════════════════════
        # 📊 LOG DETALHADO
        # ═══════════════════════════════════════════════════════════

        logger.info("═" * 60)
        logger.info(f"💳 [Subscription] Loja {store.id}:")
        logger.info(f"   - Status DB: {subscription_db.status}")
        logger.info(f"   - Status Calculado: {dynamic_status}")
        logger.info(f"   - Is Blocked: {is_blocked}")
        logger.info(f"   - Cancelada em: {subscription_db.canceled_at if subscription_db.canceled_at else 'N/A'}")
        logger.info(
            f"   - Período: {subscription_db.current_period_start.date()} até {end_date.date() if end_date else 'N/A'}")
        logger.info(f"   - Has Payment Method: {has_payment_method}")
        logger.info("═" * 60)

        # ═══════════════════════════════════════════════════════════
        # 📤 RETORNA DADOS COMPLETOS
        # ═══════════════════════════════════════════════════════════

        return {
            "id": subscription_db.id,
            "current_period_start": subscription_db.current_period_start,
            "current_period_end": subscription_db.current_period_end,
            "canceled_at": subscription_db.canceled_at,  # ✅ ADICIONA DATA DE CANCELAMENTO
            "gateway_subscription_id": subscription_db.gateway_subscription_id,
            "status": dynamic_status,
            "is_blocked": is_blocked,
            "warning_message": warning_message,
            "has_payment_method": has_payment_method,
            "plan": subscription_db.plan,
            "subscribed_addons": subscription_db.subscribed_addons,
        }