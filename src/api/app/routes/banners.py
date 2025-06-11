from fastapi import APIRouter, Depends

from src.api.shared_schemas.banner import BannerOut
from src.core import models
from src.core.database import GetDBDep
from src.core.dependencies import GetStoreDep, GetStoreFromTotemTokenDep

router = APIRouter(tags=["Banners APP"], prefix="/stores/{store_id}/banners")


@router.get("", response_model=list[BannerOut])
def get_banners(
    db: GetDBDep,
    store: models.Store = Depends(GetStoreFromTotemTokenDep),
):
    banners = db.query(models.Banner).filter(
        models.Banner.store_id == store.id
    ).all()

    return banners