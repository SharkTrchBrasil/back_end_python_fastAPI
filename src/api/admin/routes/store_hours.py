from fastapi import APIRouter, HTTPException, Depends, Response

from src.api.admin.socketio.emitters import admin_emit_store_updated
from src.core.database import GetDBDep
from src.core.dependencies import GetStoreDep  # Assumindo que essa dependência protege a rota
from src.core.models import StoreHours as StoreHoursModel
from src.api.shared_schemas.store_hours import StoreHoursCreate  # Seu schema Pydantic
import asyncio
from src.api.app.events.socketio_emitters import emit_store_updated

# ✅ Roteador simplificado
router = APIRouter(prefix="/stores/{store_id}/hours", tags=["Store Hours"])


# ✅ UMA ÚNICA ROTA PARA GOVERNAR TODAS!
@router.put("", status_code=204, summary="Atualiza a grade de horários completa da loja")
async def batch_update_store_hours(
        store: GetStoreDep,
        new_hours: list[StoreHoursCreate],  # Recebe a lista completa de horários do frontend
        db: GetDBDep,
):

    # 1. Pega o ID da loja de forma segura pela dependência
    store_id = store.id

    # 2. Deleta TODOS os horários antigos da loja em uma única operação.
    # Isso garante que turnos removidos no app sejam removidos aqui também.
    db.query(StoreHoursModel).filter(StoreHoursModel.store_id == store_id).delete(synchronize_session=False)

    # 3. Itera sobre a nova lista de horários recebida e adiciona cada um.
    for hour_data in new_hours:
        db_hour = StoreHoursModel(
            store_id=store_id,
            day_of_week=hour_data.day_of_week,
            open_time=hour_data.open_time,
            close_time=hour_data.close_time,
            shift_number=hour_data.shift_number,
            is_active=hour_data.is_active,
        )
        db.add(db_hour)

    # 4. Comita a transação. Todas as exclusões e criações acontecem de uma vez.
    db.commit()

    # 5. Notifica o frontend que a loja foi atualizada
    # Passamos o objeto 'store' que já temos da dependência
    await asyncio.create_task(emit_store_updated(db, store.id))
    await admin_emit_store_updated(store)
    # 6. Retorna uma resposta de sucesso sem conteúdo.
    return Response(status_code=204)