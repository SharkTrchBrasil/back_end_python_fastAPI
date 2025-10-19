# src/api/admin/routes/store_operation_config.py

import asyncio
from fastapi import APIRouter

from src.api.admin.socketio.emitters import admin_emit_store_updated, emit_store_updates
from src.api.schemas.store.store_operation_config import StoreOperationConfigBase, StoreOperationConfigOut

from src.core import models
from src.core.database import GetDBDep
from src.core.dependencies import GetStoreDep

router = APIRouter(tags=["Store Configuration"], prefix="/stores/{store_id}/configuration")


@router.put("", response_model=StoreOperationConfigOut)
async def update_store_configuration(
        store: GetStoreDep,
        config_data: StoreOperationConfigBase,
        db: GetDBDep,
):
    """
    ✅ ATUALIZA CONFIGURAÇÕES DE OPERAÇÃO DA LOJA
    """
    # ✅ 1. BUSCA OU CRIA A CONFIGURAÇÃO
    db_config = db.query(models.StoreOperationConfig).filter_by(store_id=store.id).first()
    if not db_config:
        db_config = models.StoreOperationConfig(store_id=store.id)
        db.add(db_config)

    # ✅ 2. ATUALIZA TODOS OS CAMPOS
    update_data = config_data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_config, key, value)

    db.commit()
    db.refresh(db_config)

    # ✅ 3. EMITE ATUALIZAÇÕES (CORRIGIDO - USA A FUNÇÃO CORRETA)
    # Esta função já chama AMBOS os emissores (admin + totem) de forma otimizada
    await emit_store_updates(db, store.id)

    return db_config