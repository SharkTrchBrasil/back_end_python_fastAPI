# em routers/tables.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from src.api.admin.services.table_service import TableService
from src.api.schemas.store.table import AddItemToCommandSchema
from src.core.database import get_db, GetDBDep  # sua função para obter a sessão do db




router = APIRouter(prefix="/tables", tags=["Tables"])


@router.post("/{table_id}/items")
async def add_item_to_table_endpoint(
        table_id: int,
        item: AddItemToCommandSchema,
        db: GetDBDep
):
    service = TableService(db)
    try:
        updated_table = service.add_item_to_table(table_id, item)

        # AGORA, A MÁGICA DO TEMPO REAL
        # Após a conclusão bem-sucedida, você transmite a atualização.
        # A mensagem deve conter os dados completos e atualizados da mesa.
        # await manager.broadcast_to_store(
        #     store_id=updated_table.store_id,
        #     message={"event": "table_updated", "data": TableDetailsSchema.from_orm(updated_table).dict()}
        # )

        return {"message": "Item adicionado com sucesso"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))