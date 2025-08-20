from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from src.api import schemas
from src.api.admin.socketio.emitters import admin_emit_store_updated
from src.api.app.socketio.socketio_emitters import emit_store_updated
from src.api.schemas.scheduled_pauses import ScheduledPauseOut, ScheduledPauseCreate
from src.core import models
from src.core.database import GetDBDep

router = APIRouter(prefix="/pauses", tags=["Scheduled Pauses"])

# LISTAR TODAS AS PAUSAS DE UMA LOJA
@router.get("/store/{store_id}", response_model=list[ScheduledPauseOut])
def get_pauses_for_store(store_id: int, db: GetDBDep):
    # Futuramente, você pode filtrar aqui para mostrar apenas pausas futuras
    pauses = db.query(models.ScheduledPause).filter(models.ScheduledPause.store_id == store_id).all()
    return pauses

# CRIAR UMA NOVA PAUSA
@router.post("/store/{store_id}", response_model=ScheduledPauseOut)
async def create_pause(store_id: int, pause: ScheduledPauseCreate, db: GetDBDep):
    db_pause = models.ScheduledPause(**pause.model_dump(), store_id=store_id)
    db.add(db_pause)
    db.commit()
    db.refresh(db_pause)

    # TODO: Emitir um evento de socket para notificar a UI da mudança
    await emit_store_updated(db, store_id)
    await admin_emit_store_updated(db, store_id)

    return db_pause

# DELETAR UMA PAUSA
@router.delete("/{pause_id}", status_code=204)
async def delete_pause(pause_id: int, db: GetDBDep):
    db_pause = db.query(models.ScheduledPause).filter(models.ScheduledPause.id == pause_id).first()
    if not db_pause:
        raise HTTPException(status_code=404, detail="Pausa não encontrada")

    store_id_to_update = db_pause.store_id

    db.delete(db_pause)
    db.commit()
    # TODO: Emitir um evento de socket para notificar a UI da mudança
    await emit_store_updated(db, store_id_to_update)
    await admin_emit_store_updated(db, store_id_to_update)
    return {"ok": True}