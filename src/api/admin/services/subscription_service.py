# Dentro da classe SubscriptionService
from datetime import datetime, timedelta

from sqlalchemy.orm import joinedload

from src.core import models


@staticmethod
def get_subscription_details(db, store_id: int) -> tuple[dict, bool]:
    # Busca a loja e, de forma otimizada, já carrega todas as suas assinaturas e os detalhes aninhados
    store_db = db.query(models.Store).options(

        joinedload(models.Store.subscriptions)
        .joinedload(models.StoreSubscription.plan)
        .joinedload(models.Plans.included_features)
        .joinedload(models.PlansFeature.feature),
        joinedload(models.Store.subscriptions)
        .joinedload(models.StoreSubscription.subscribed_addons)
        .joinedload(models.PlansAddon.feature)

    ).filter(models.Store.id == store_id).first()

    if not store_db:
        # Lógica de fallback se a loja não existir
        return {"error": "Loja não encontrada"}, False

    subscription_db = store_db.active_subscription

    # 2. Caso não haja assinatura
    if not subscription_db:
        payload = {
            "plan_name": "Nenhum", "status": "expired",
            "expiry_date": None, "features": [],
            "warning_message": "Nenhuma assinatura encontrada para esta loja."
        }
        return payload, False

    # ✅ 3. LÓGICA ATUALIZADA PARA UNIFICAR FEATURES
    # Pega as features do plano base
    plan_features = {
        assoc.feature.feature_key
        for assoc in subscription_db.plan.included_features
    }
    # Pega as features dos add-ons
    addon_features = {
        addon.feature.feature_key
        for addon in subscription_db.subscribed_addons
    }
    # Junta as duas listas usando a união de conjuntos para evitar duplicatas
    all_features = sorted(list(plan_features.union(addon_features)))

    # 4. A lógica de status dinâmico continua a mesma
    now = datetime.utcnow()
    expiry_date = subscription_db.current_period_end
    grace_period_end = expiry_date + timedelta(days=3)
    dynamic_status = "unknown"
    warning_message = None

    if now <= expiry_date:
        dynamic_status = "active"
        # ... (lógica de mensagem de aviso de vencimento)
    elif now <= grace_period_end:
        dynamic_status = "grace_period"
        warning_message = "Sua assinatura venceu! Renove para não perder o acesso."
    else:
        dynamic_status = "expired"
        warning_message = "Assinatura expirada. Funcionalidades bloqueadas."

    # 5. Construção do payload final com a lista de features unificada
    payload = {
        "plan_name": subscription_db.plan.plan_name,
        "expiry_date": expiry_date.isoformat() + "Z",
        "features": all_features,  # <-- Usa a nova lista completa de features
        "status": dynamic_status,
        "warning_message": warning_message
    }

    is_operational = dynamic_status != "expired"
    return payload, is_operational