from fastapi import APIRouter

from src.api.admin.schemas.plans import PlanSchema
from src.core import models
from src.core.database import GetDBDep


router = APIRouter(tags=["Subscriptions"], prefix="/plans")


@router.get("", response_model=list[PlanSchema])
def list_plans(
        db: GetDBDep,
):
    return db.query(models.Plans).filter(models.Plans.available).all()
