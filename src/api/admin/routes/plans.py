from fastapi import APIRouter


from src.core import models
from src.core.database import GetDBDep
from src.core.models import Plans

router = APIRouter(tags=["Subscriptions"], prefix="/plans")


@router.get("", response_model=list[Plans])
def list_plans(
        db: GetDBDep,
):
    return db.query(models.Plans).filter(models.Plans.available).all()
