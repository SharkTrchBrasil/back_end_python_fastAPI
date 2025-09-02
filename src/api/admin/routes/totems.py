from fastapi import APIRouter, HTTPException

from src.api.schemas.store.totem import Totem
from src.core import models
from src.core.database import GetDBDep
from src.core.dependencies import GetCurrentUserDep, GetStoreDep

router = APIRouter(tags=["Totems"], prefix="/stores/{store_id}")

@router.post("/authorize-totem")
def authorize_totem(
    db: GetDBDep,
    store: GetStoreDep,
    public_key: str,
    user: GetCurrentUserDep,
):
    totem = db.query(models.TotemAuthorization).filter(models.TotemAuthorization.public_key == public_key).first()
    if totem is None:
        raise HTTPException(status_code=404)
    totem.store_id = store.id
    totem.granted = True
    totem.granted_by_id = user.id
    db.commit()


@router.get("/totems", response_model=list[Totem])
def get_totems(
    db: GetDBDep,
    store: GetStoreDep,
):
    return db.query(models.TotemAuthorization).filter(models.TotemAuthorization.store_id == store.id,
                                                      models.TotemAuthorization.granted.is_(True)).all()


@router.delete("/totems/{totem_id}")
def revoke_totem(
        db: GetDBDep,
        store: GetStoreDep,
        totem_id: int,
):
    totem = db.query(models.TotemAuthorization).filter(models.TotemAuthorization.id == totem_id,
                                                       models.TotemAuthorization.store_id == store.id).first()
    if totem is None:
        raise HTTPException(status_code=404)

    totem.granted = False
    totem.store_id = None
    totem.granted_by_id = None
    db.commit()