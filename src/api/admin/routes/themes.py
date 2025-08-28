from typing import Annotated

from fastapi import APIRouter, Depends

from src.api.app.socketio.socketio_emitters import emit_theme_updated
from src.api.schemas import StoreThemeOut
from src.api.schemas.store import StoreThemeIn

from src.core import models
from src.core.database import GetDBDep
from src.core.dependencies import GetStore
from src.core.models import Store
from src.core.utils.enums import Roles

router = APIRouter(prefix="/stores/{store_id}/theme", tags=["Theme"])

@router.get("", response_model=StoreThemeOut | None)
def get_store_theme(
    db: GetDBDep,
    store: Annotated[Store, Depends(GetStore([Roles.OWNER]))]
):


    store_theme = db.query(models.StoreTheme).filter(
        models.StoreTheme.store_id == store.id
    ).first()
    return store_theme


@router.put("", response_model=StoreThemeOut)
async def update_store_theme(
    db: GetDBDep,
    store: Annotated[Store, Depends(GetStore([Roles.OWNER]))],
    theme: StoreThemeIn,
):

    # if not store.subscription.plan.style_guide:
    #     raise HTTPException(status_code=403, detail="This store does not support custom themes.")

    store_theme = db.query(models.StoreTheme).filter(
        models.StoreTheme.store_id == store.id
    ).first()

    if store_theme:
        for key, value in theme.model_dump().items():
            setattr(store_theme, key, value)
    else:
        store_theme = models.StoreTheme(**theme.model_dump(), store_id=store.id)
        db.add(store_theme)

    db.commit()
    db.refresh(store_theme)

    # Passa o ORM para emitir evento
    await emit_theme_updated(store_theme)

    return store_theme  # FastAPI converte automaticamente para StoreThemeOut

