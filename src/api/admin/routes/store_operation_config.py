import asyncio

from fastapi import APIRouter

from src.api.admin.socketio.emitters import admin_emit_store_updated
from src.api.app.socketio.socketio_emitters import emit_store_updated
from src.api.schemas.store.store_operation_config import StoreOperationConfigBase, StoreOperationConfigOut

from src.core import models
from src.core.database import GetDBDep
from src.core.dependencies import GetStoreDep

router = APIRouter(tags=["Store Configuration"], prefix="/stores/{store_id}/configuration")


@router.put("", response_model=StoreOperationConfigOut)
async def update_store_configuration(
        store: GetStoreDep,
        config_data: StoreOperationConfigBase,  # ✅ RECEBE UM ÚNICO OBJETO JSON
        db: GetDBDep,
):
    # Busca a configuração existente ou cria uma nova
    db_config = db.query(models.StoreOperationConfig).filter_by(store_id=store.id).first()
    if not db_config:
        db_config = models.StoreOperationConfig(store_id=store.id)
        db.add(db_config)

    # Atualiza todos os campos de uma vez a partir do objeto recebido
    update_data = config_data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_config, key, value)

    db.commit()
    db.refresh(db_config)

    await asyncio.create_task(emit_store_updated(db, store.id))
    await admin_emit_store_updated(db, store.id)
    return db_config