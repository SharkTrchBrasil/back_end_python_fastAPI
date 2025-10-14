# src/api/routes/admin/table.py
from fastapi import APIRouter, HTTPException, status

from src.api.admin.services.table_service import TableService
from src.api.schemas.tables.table import SaloonOut, CreateSaloonRequest, UpdateSaloonRequest, TableOut, \
    CreateTableRequest, UpdateTableRequest, OpenTableRequest, CloseTableRequest, AddItemToTableRequest, \
    RemoveItemFromTableRequest

from src.core.database import GetDBDep
from src.core.dependencies import GetStoreDep

router = APIRouter(tags=["Tables"], prefix="/stores/{store_id}/tables")


# ========== ROTAS DE SALÕES ==========

@router.post("/saloons", response_model=SaloonOut, status_code=status.HTTP_201_CREATED)
async def create_saloon(
    request: CreateSaloonRequest,
    db: GetDBDep,
    store: GetStoreDep,
):
    """Cria um novo salão/ambiente"""
    service = TableService(db)

    try:
        saloon = service.create_saloon(store.id, request)

        # Emite evento via socket
        from src.api.admin.socketio import emitters
        import asyncio
        asyncio.create_task(
            emitters.admin_emit_tables_and_commands(db=db, store_id=store.id)
        )

        return saloon
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.patch("/saloons/{saloon_id}", response_model=SaloonOut)
async def update_saloon(
    saloon_id: int,
    request: UpdateSaloonRequest,
    db: GetDBDep,
    store: GetStoreDep,
):
    """Atualiza um salão existente"""
    service = TableService(db)

    try:
        saloon = service.update_saloon(saloon_id, store.id, request)

        # Emite evento via socket
        from src.api.admin.socketio import emitters
        import asyncio
        asyncio.create_task(
            emitters.admin_emit_tables_and_commands(db=db, store_id=store.id)
        )

        return saloon
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.delete("/saloons/{saloon_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_saloon(
    saloon_id: int,
    db: GetDBDep,
    store: GetStoreDep,
):
    """Deleta um salão"""
    service = TableService(db)

    try:
        service.delete_saloon(saloon_id, store.id)

        # Emite evento via socket
        from src.api.admin.socketio import emitters
        import asyncio
        asyncio.create_task(
            emitters.admin_emit_tables_and_commands(db=db, store_id=store.id)
        )

        return None
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ========== ROTAS DE MESAS ==========

@router.post("", response_model=TableOut, status_code=status.HTTP_201_CREATED)
async def create_table(
    request: CreateTableRequest,
    db: GetDBDep,
    store: GetStoreDep,
):
    """Cria uma nova mesa"""
    service = TableService(db)

    try:
        table = service.create_table(store.id, request)

        # Emite evento via socket
        from src.api.admin.socketio import emitters
        import asyncio
        asyncio.create_task(
            emitters.admin_emit_tables_and_commands(db=db, store_id=store.id)
        )

        return table
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.patch("/{table_id}", response_model=TableOut)
async def update_table(
    table_id: int,
    request: UpdateTableRequest,
    db: GetDBDep,
    store: GetStoreDep,
):
    """Atualiza informações de uma mesa"""
    service = TableService(db)

    try:
        table = service.update_table(table_id, store.id, request)

        # Emite evento via socket
        from src.api.admin.socketio import emitters
        import asyncio
        asyncio.create_task(
            emitters.admin_emit_tables_and_commands(db=db, store_id=store.id)
        )

        return table
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.delete("/{table_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_table(
    table_id: int,
    db: GetDBDep,
    store: GetStoreDep,
):
    """Deleta uma mesa"""
    service = TableService(db)

    try:
        service.delete_table(table_id, store.id)

        # Emite evento via socket
        from src.api.admin.socketio import emitters
        import asyncio
        asyncio.create_task(
            emitters.admin_emit_tables_and_commands(db=db, store_id=store.id)
        )

        return None
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ========== ROTAS DE ABERTURA/FECHAMENTO ==========

@router.post("/open", status_code=status.HTTP_200_OK)
async def open_table(
    request: OpenTableRequest,
    db: GetDBDep,
    store: GetStoreDep,
):
    """Abre uma mesa criando uma comanda"""
    service = TableService(db)

    try:
        command = service.open_table(store.id, request)

        # Emite evento via socket
        from src.api.admin.socketio import emitters
        import asyncio
        asyncio.create_task(
            emitters.admin_emit_tables_and_commands(db=db, store_id=store.id)
        )

        return {"message": "Mesa aberta com sucesso", "command_id": command.id}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/close", status_code=status.HTTP_200_OK)
async def close_table(
    request: CloseTableRequest,
    db: GetDBDep,
    store: GetStoreDep,
):
    """Fecha uma mesa e sua comanda"""
    service = TableService(db)

    try:
        table = service.close_table(store.id, request.table_id, request.command_id)

        # Emite evento via socket
        from src.api.admin.socketio import emitters
        import asyncio
        asyncio.create_task(
            emitters.admin_emit_tables_and_commands(db=db, store_id=store.id)
        )

        return {"message": "Mesa fechada com sucesso"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ========== ROTAS DE ITENS ==========

@router.post("/add-item", status_code=status.HTTP_201_CREATED)
async def add_item_to_table(
    request: AddItemToTableRequest,
    db: GetDBDep,
    store: GetStoreDep,
):
    """Adiciona um item ao pedido de uma mesa"""
    service = TableService(db)

    try:
        order = service.add_item_to_table(store.id, request)

        # Emite evento via socket para atualizar a mesa
        from src.api.admin.socketio import emitters
        import asyncio
        asyncio.create_task(
            emitters.admin_emit_tables_and_commands(db=db, store_id=store.id)
        )

        return {
            "message": "Item adicionado com sucesso",
            "order_id": order.id,
            "total": order.total_price
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/remove-item", status_code=status.HTTP_200_OK)
async def remove_item_from_table(
    request: RemoveItemFromTableRequest,
    db: GetDBDep,
    store: GetStoreDep,
):
    """Remove um item do pedido de uma mesa"""
    service = TableService(db)

    try:
        service.remove_item_from_table(store.id, request.order_product_id, request.command_id)

        # Emite evento via socket
        from src.api.admin.socketio import emitters
        import asyncio
        asyncio.create_task(
            emitters.admin_emit_tables_and_commands(db=db, store_id=store.id)
        )

        return {"message": "Item removido com sucesso"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))