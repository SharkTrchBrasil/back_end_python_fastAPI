# src/api/admin/services/store_service.py

from typing import Dict, Any
import logging
from sqlalchemy import inspect

from src.api.admin.services.subscription_service import SubscriptionService
from src.core import models
from src.core.database import GetDBDep

logger = logging.getLogger(__name__)


class StoreService:
    """
    ✅ SERVIÇO ORQUESTRADOR DE LOJA

    Responsabilidade: Montar o payload completo da loja.
    NÃO faz cálculos complexos, apenas COMPÕE resultados de outros serviços.
    """

    @staticmethod
    def get_store_complete_payload(
            store: models.Store,
            db: GetDBDep
    ) -> Dict[str, Any]:
        """
        ✅ MÉTODO PRINCIPAL: Monta payload completo da loja

        Este método:
        1. Extrai dados básicos do ORM
        2. Adiciona relacionamentos simples
        3. DELEGA cálculos complexos para serviços especializados
        4. Valida com Pydantic
        5. Retorna dict JSON pronto

        Args:
            store: Objeto ORM da loja (com relações carregadas)
            db: Sessão do banco de dados

        Returns:
            Dict completo validado e pronto para JSON
        """
        from src.api.schemas.store.store_details import StoreDetails

        try:
            # ═══════════════════════════════════════════════════════════
            # 1. EXTRAI COLUNAS DO BANCO (automaticamente)
            # ═══════════════════════════════════════════════════════════
            mapper = inspect(store.__class__)
            store_dict = {
                column.key: getattr(store, column.key)
                for column in mapper.columns
            }

            # ═══════════════════════════════════════════════════════════
            # 2. ADICIONA RELACIONAMENTOS SIMPLES
            # (Que o Pydantic consegue validar diretamente)
            # ═══════════════════════════════════════════════════════════
            store_dict['store_operation_config'] = store.store_operation_config
            store_dict['hours'] = store.hours
            store_dict['cities'] = store.cities
            store_dict['scheduled_pauses'] = store.scheduled_pauses
            store_dict['banners'] = store.banners
            store_dict['payment_activations'] = store.payment_activations
            store_dict['coupons'] = store.coupons
            store_dict['chatbot_messages'] = store.chatbot_messages
            store_dict['chatbot_config'] = store.chatbot_config
            store_dict['categories'] = store.categories
            store_dict['products'] = store.products
            store_dict['variants'] = store.variants

            # ═══════════════════════════════════════════════════════════
            # 3. DELEGA CÁLCULOS COMPLEXOS PARA SERVIÇOS ESPECIALIZADOS
            # ═══════════════════════════════════════════════════════════

            # ✅ Assinatura (calculada pelo SubscriptionService)
            subscription_data = SubscriptionService.get_enriched_subscription(
                store=store,
                db=db
            )
            store_dict['active_subscription'] = subscription_data

            # ✅ Preview de cobrança (já vem dentro de subscription_data)
            store_dict['billing_preview'] = (
                subscription_data.get('billing_preview')
                if subscription_data
                else None
            )

            # ═══════════════════════════════════════════════════════════
            # 4. VALIDA COM PYDANTIC
            # ═══════════════════════════════════════════════════════════
            validated = StoreDetails.model_validate(store_dict)

            # ═══════════════════════════════════════════════════════════
            # 5. RETORNA DICT JSON PRONTO
            # ═══════════════════════════════════════════════════════════
            return validated.model_dump(by_alias=True, mode='json')

        except Exception as e:
            logger.error(f"❌ Erro ao montar payload da loja {store.id}: {e}", exc_info=True)
            raise