# src/api/admin/services/store_service.py

from typing import Dict, Any, List
import logging
from sqlalchemy import inspect

from src.api.admin.services.subscription_service import SubscriptionService
from src.core import models
from src.core.database import GetDBDep

logger = logging.getLogger(__name__)


class StoreService:
    """
    ✅ SERVIÇO ORQUESTRADOR DE LOJA (ARQUITETURA PROFISSIONAL)

    Responsabilidade: Composição de payloads complexos
    Princípio DRY: Centraliza lógica de montagem em um único lugar
    """

    # ═══════════════════════════════════════════════════════════
    # CONFIGURAÇÃO: Relacionamentos sempre incluídos
    # ═══════════════════════════════════════════════════════════
    SIMPLE_RELATIONS: List[str] = [
        'store_operation_config',
        'hours',
        'cities',
        'scheduled_pauses',
        'banners',
        'payment_activations',
        'coupons',
        'chatbot_messages',
        'chatbot_config',
        'categories',
        'products',
        'variants',
    ]

    @staticmethod
    def get_store_complete_payload(
            store: models.Store,
            db: GetDBDep
    ) -> Dict[str, Any]:
        """
        ✅ Monta payload completo da loja (JSON-serializable)

        Estratégia:
        1. Extrai APENAS colunas reais do banco (evita @hybrid_property)
        2. Adiciona relacionamentos ORM
        3. Delega cálculos complexos para serviços especializados
        4. Valida com Pydantic (que aplica @computed_field)
        5. Retorna dict JSON pronto

        Returns:
            Dict validado e JSON-serializable
        """
        from src.api.schemas.store.store_details import StoreDetails

        try:
            # ═══════════════════════════════════════════════════════════
            # 1. EXTRAI APENAS COLUNAS DO BANCO (sem @hybrid_property)
            # ═══════════════════════════════════════════════════════════
            mapper = inspect(store.__class__)
            store_dict = {
                column.key: getattr(store, column.key)
                for column in mapper.columns
            }

            # ═══════════════════════════════════════════════════════════
            # 2. ADICIONA RELACIONAMENTOS ORM
            # ═══════════════════════════════════════════════════════════
            for relation in StoreService.SIMPLE_RELATIONS:
                if hasattr(store, relation):
                    store_dict[relation] = getattr(store, relation)
                else:
                    logger.warning(
                        f"⚠️ Relação '{relation}' não encontrada no modelo Store"
                    )

            # ═══════════════════════════════════════════════════════════
            # 3. DELEGA CÁLCULOS COMPLEXOS PARA SERVIÇOS ESPECIALIZADOS
            # ═══════════════════════════════════════════════════════════
            subscription_data = SubscriptionService.get_enriched_subscription(
                store=store,
                db=db
            )
            store_dict['active_subscription'] = subscription_data
            store_dict['billing_preview'] = (
                subscription_data.get('billing_preview')
                if subscription_data
                else None
            )

            # ═══════════════════════════════════════════════════════════
            # 4. VALIDA COM PYDANTIC (aplica @computed_field)
            # ═══════════════════════════════════════════════════════════
            validated = StoreDetails.model_validate(store_dict)

            # ═══════════════════════════════════════════════════════════
            # 5. RETORNA DICT JSON
            # ═══════════════════════════════════════════════════════════
            return validated.model_dump(by_alias=True, mode='json')

        except Exception as e:
            logger.error(
                f"❌ Erro ao montar payload da loja {store.id}: {e}",
                exc_info=True
            )
            raise