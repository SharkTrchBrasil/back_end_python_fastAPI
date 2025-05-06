from fastapi import APIRouter


from src.api.admin.schemas.store_types import StoreTypes
from src.core import models

from src.core.database import GetDBDep
from src.core.dependencies import GetCurrentUserDep, GetStoreDep

router = APIRouter(tags=["Segments"], prefix="/stores/segments")



@router.get("", response_model=list[StoreTypes])
def get_store_types(
    db: GetDBDep,
    store: GetStoreDep,
):
    db_categories = db.query(models.StoreType).all()
    return db_categories

