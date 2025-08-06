# seu_arquivo_de_rota.py

from fastapi import APIRouter, HTTPException, Depends, Response
from sqlalchemy.orm import Session  # Importe a Session para type hinting se não tiver
import asyncio
import logging  # Use o logging para depuração

from src.api.admin.socketio.emitters import admin_emit_store_updated
from src.core.database import GetDBDep
from src.core.dependencies import GetStoreDep
from src.core.models import Store as StoreModel, StoreHours as StoreHoursModel
from src.api.shared_schemas.store_hours import StoreHoursCreate
from src.api.app.events.socketio_emitters import emit_store_updated

# Configuração básica de logging
logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

router = APIRouter(prefix="/stores/{store_id}/hours", tags=["Store Hours"])


@router.put("", status_code=204, summary="Atualiza a grade de horários completa da loja")
async def batch_update_store_hours(
        store: StoreModel = Depends(GetStoreDep),  # Tipagem explícita ajuda na clareza
        new_hours: list[StoreHoursCreate] = Body(...), # O '...' torna o corpo obrigatório
        db: Session = Depends(GetDBDep),
):
    store_id = store.id

    # ✅ Usar um bloco try/except explícito para capturar e logar o erro exato
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

    # ✅ 4. CORREÇÃO CRÍTICA: ATUALIZE O OBJETO 'store' NA SESSÃO
    # Isso irá recarregar o objeto 'store' do banco de dados, incluindo a nova
    # relação 'hours' que acabamos de salvar.
    db.refresh(store)

    # 5. Agora, com o objeto 'store' 100% atualizado, emita os eventos com segurança.
    # Usar asyncio.gather é um pouco mais eficiente para executar tarefas concorrentes.
    await asyncio.gather(
        emit_store_updated(db, store.id),
        admin_emit_store_updated(store)  # Agora usa o 'store' com os dados corretos
    )

    return Response(status_code=204)