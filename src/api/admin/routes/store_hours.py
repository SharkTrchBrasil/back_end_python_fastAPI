# seu_arquivo_de_rota.py

from fastapi import APIRouter, HTTPException, Response, Body
import asyncio
import logging  # Use o logging para depuração

from src.api.admin.socketio.emitters import admin_emit_store_updated
from src.core.database import GetDBDep
from src.core.dependencies import GetStoreDep
from src.core.models import StoreHours as StoreHoursModel
from src.api.schemas.store_hours import StoreHoursCreate
from src.api.app.socketio.socketio_emitters import emit_store_updated

# Configuração básica de logging
logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

router = APIRouter(prefix="/stores/{store_id}/hours", tags=["Store Hours"])


@router.put("", status_code=204, summary="Atualiza a grade de horários completa da loja")
async def batch_update_store_hours(
        store_id: int,

        db: GetDBDep,
        store: GetStoreDep,
        new_hours: list[StoreHoursCreate] = Body(...),

):
    store_id = store.id

    try:
        # 1. Deleta TODOS os horários antigos da loja.
        db.query(StoreHoursModel).filter(StoreHoursModel.store_id == store_id).delete(synchronize_session=False)

        # 2. Itera sobre a nova lista e prepara os novos objetos.
        #    Usar model_dump() é mais seguro para passar os dados.
        for hour_data in new_hours:
            db_hour = StoreHoursModel(**hour_data.model_dump(), store_id=store_id)
            db.add(db_hour)

        # 3. Comita a transação. Se falhar aqui, o 'except' será acionado.
        db.commit()

    except Exception as e:
        log.exception(f"DATABASE ERROR ao atualizar horários para store_id={store_id}: {e}")
        db.rollback()  # Garante o rollback em caso de falha
        raise HTTPException(
            status_code=500,
            detail="Erro interno ao salvar os horários."
        )


    db.refresh(store)

    await asyncio.gather(
        emit_store_updated(db, store.id),
        admin_emit_store_updated(db, store.id)  # Agora usa o 'store' com os dados corretos
    )

    return Response(status_code=204)