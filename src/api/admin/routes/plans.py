from fastapi import APIRouter
from sqlalchemy.orm import joinedload

from src.api.schemas.subscriptions.plans import PlanSchema
from src.core import models
from src.core.database import GetDBDep


router = APIRouter(tags=["Subscriptions"], prefix="/plans")



@router.get("", response_model=list[PlanSchema])
def list_plans(db: GetDBDep):
    """Lista todos os planos disponíveis, carregando suas features de forma otimizada."""
    return db.query(models.Plans).options(
        # ✅ Carrega antecipadamente a relação 'included_features',
        # e a partir dela, a relação 'feature'.
        joinedload(models.Plans.included_features)
        .joinedload(models.PlansFeature.feature)
    ).filter(models.Plans.available).all()