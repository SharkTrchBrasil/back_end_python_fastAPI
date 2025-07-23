from fastapi import APIRouter

from src.api.admin.schemas.plans import SubscriptionPlan
from src.core import models
from src.core.database import GetDBDep

router = APIRouter(tags=["Subscriptions"], prefix="/plans")


@router.get("", response_model=list[SubscriptionPlan])
def list_plans(
        db: GetDBDep,
):
    return db.query(models.SubscriptionPlan).filter(models.SubscriptionPlan.available).all()
