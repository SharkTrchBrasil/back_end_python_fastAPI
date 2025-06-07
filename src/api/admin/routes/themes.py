import asyncio
from typing import Annotated

from fastapi import APIRouter, Depends

from src.api.app.events.socketio_emitters import emit_theme_updated
from src.api.shared_schemas.store import Roles
from src.api.shared_schemas.store_theme import StoreTheme
from src.core import models
from src.core.database import GetDBDep
from src.core.dependencies import GetStoreDep, GetStore
from src.core.models import Store

router = APIRouter(prefix="/stores/{store_id}/theme", tags=["Theme"])

@router.get("", response_model=StoreTheme | None)
def get_store_theme(
    db: GetDBDep,
    store: Annotated[Store, Depends(GetStore([Roles.OWNER]))]
):
    store_theme = db.query(models.StoreTheme).filter(
        models.StoreTheme.store_id == store.id
    ).first()
    return store_theme


@router.put("", response_model=StoreTheme)
async def update_store_theme(
    db: GetDBDep,
    store: Annotated[Store, Depends(GetStore([Roles.OWNER]))],
    theme: StoreTheme,
):
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
    db.refresh(store_theme)  # 🟢 importante para garantir que os dados retornados estejam atualizados

    await emit_theme_updated(StoreTheme.model_validate(store_theme))

    return store_theme
