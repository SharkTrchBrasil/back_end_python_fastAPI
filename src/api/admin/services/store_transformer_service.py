# src/api/admin/services/store_transformer_service.py
"""
Serviço de Transformação de Store para DTOs
============================================

Converte objetos ORM Store em schemas Pydantic enriquecidos.

✨ VERSÃO OTIMIZADA: Retorna diretamente objetos Pydantic validados

Autor: Sistema de Billing
Data: 2025-10-18
"""

from typing import Optional
from sqlalchemy.orm import Session
import logging

from src.core import models
from src.api.admin.services.subscription_service import SubscriptionService
from src.api.schemas.store.store_details import StoreDetails
from src.api.schemas.store.store_with_role import StoreWithRole

logger = logging.getLogger(__name__)


class StoreTransformerService:
    """
    Transforma objetos Store ORM em schemas Pydantic validados.
    """

    @staticmethod
    def enrich_store_with_subscription(
            store: models.Store,
            db: Session
    ) -> StoreDetails:
        """
        ✅ Enriquece Store ORM com dados calculados e retorna schema validado.

        Args:
            store: Objeto ORM da loja
            db: Sessão do banco de dados

        Returns:
            Schema StoreDetails completamente validado e populado
        """
        try:
            # 1. Converte ORM para dicionário (Pydantic faz isso automaticamente)
            store_dict = store.__dict__.copy()

            # Remove atributos internos do SQLAlchemy
            store_dict.pop('_sa_instance_state', None)

            # 2. ✅ CALCULA dados da assinatura
            subscription_details = SubscriptionService.get_subscription_details(
                store=store,
                db=db
            )

            # 3. ✅ INJETA no dicionário
            store_dict['active_subscription'] = subscription_details

            if subscription_details:
                store_dict['billing_preview'] = subscription_details.get('billing_preview')
            else:
                store_dict['billing_preview'] = None

            # 4. ✅ VALIDA com Pydantic (garante tipagem e validação)
            store_schema = StoreDetails.model_validate(store_dict)

            logger.debug(f"✅ Store {store.id} enriquecida e validada")
            return store_schema

        except Exception as e:
            logger.error(f"❌ Erro ao enriquecer Store {store.id}: {e}", exc_info=True)
            raise

    @staticmethod
    def enrich_store_access_with_role(
            store_access: models.StoreAccess,
            db: Session
    ) -> StoreWithRole:
        """
        ✅ Transforma StoreAccess em schema validado (usado em listas).

        Args:
            store_access: Objeto StoreAccess ORM
            db: Sessão do banco de dados

        Returns:
            Schema StoreWithRole completamente validado
        """
        try:
            # 1. Enriquece a store primeiro
            store_dict = store_access.store.__dict__.copy()
            store_dict.pop('_sa_instance_state', None)

            # 2. Calcula assinatura
            subscription_details = SubscriptionService.get_subscription_details(
                store=store_access.store,
                db=db
            )

            store_dict['active_subscription'] = subscription_details

            if subscription_details:
                store_dict['billing_preview'] = subscription_details.get('billing_preview')

            # 3. Monta o dicionário final
            access_dict = {
                'store': store_dict,
                'role': store_access.role,
                'store_id': store_access.store_id,
                'user_id': store_access.user_id,
            }

            # 4. Valida com Pydantic
            return StoreWithRole.model_validate(access_dict)

        except Exception as e:
            logger.error(f"❌ Erro ao enriquecer StoreAccess: {e}", exc_info=True)
            raise