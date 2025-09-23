# src/api/services/permission_service.py
from sqlalchemy.orm import Session
from src.core import models

def store_has_feature(db: Session, store_id: int, feature_key: str) -> bool:
    """
    Verifica se a assinatura ativa de uma loja inclui uma feature específica.
    """
    # Esta query complexa faz tudo em uma única chamada ao banco
    # Ela junta Loja -> Assinatura -> Plano -> Features do Plano
    result = db.query(models.Store).filter(
        models.Store.id == store_id
    ).join(
        models.Store.subscriptions
    ).join(
        models.StoreSubscription.plan
    ).join(
        models.Plans.included_features
    ).join(
        models.PlansFeature.feature
    ).filter(
        models.StoreSubscription.status.in_(['active', 'new_charge', 'trialing']),
        models.Feature.feature_key == feature_key
    ).first()

    # Se a query encontrou algo, significa que a loja tem a feature.
    return result is not None