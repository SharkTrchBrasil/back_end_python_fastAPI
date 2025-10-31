# src/api/routes/admin/table.py
from fastapi import APIRouter, HTTPException, status, Request
from datetime import datetime

from src.api.admin.services.table_service import TableService
from src.core import models
from src.core.utils.enums import TableStatus
from src.api.schemas.tables.table import SaloonOut, CreateSaloonRequest, UpdateSaloonRequest, TableOut, \
    CreateTableRequest, UpdateTableRequest, OpenTableRequest, CloseTableRequest, AddItemToTableRequest, \
    RemoveItemFromTableRequest, AssignEmployeeRequest, TableActivityReport, SplitPaymentRequest, \
    TableDashboardOut

from src.core.database import GetDBDep
from src.core.dependencies import GetStoreDep, GetCurrentUserDep, GetAuditLoggerDep
from src.core.utils.enums import Roles, AuditAction, AuditEntityType

router = APIRouter(tags=["Tables"], prefix="/stores/{store_id}/tables")


# ========== ROTAS DE SALÕES ==========

@router.post("/saloons", response_model=SaloonOut, status_code=status.HTTP_201_CREATED)
async def create_saloon(
    request: CreateSaloonRequest,
    db: GetDBDep,
    store: GetStoreDep,
    user: GetCurrentUserDep,
    audit: GetAuditLoggerDep,
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

        audit.log(
            action=AuditAction.CREATE_TABLE,
            entity_type=AuditEntityType.TABLE,
            entity_id=saloon.id,
            changes=request.model_dump(),
            description=f"Criou salão '{saloon.name}'"
        )
        db.commit()
        return saloon
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.patch("/saloons/{saloon_id}", response_model=SaloonOut)
async def update_saloon(
    saloon_id: int,
    request: UpdateSaloonRequest,
    db: GetDBDep,
    store: GetStoreDep,
    user: GetCurrentUserDep,
    audit: GetAuditLoggerDep,
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

        audit.log(
            action=AuditAction.UPDATE_TABLE,
            entity_type=AuditEntityType.TABLE,
            entity_id=saloon.id,
            changes=request.model_dump(exclude_none=True),
            description=f"Atualizou salão '{saloon.name}'"
        )
        db.commit()
        return saloon
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.delete("/saloons/{saloon_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_saloon(
    saloon_id: int,
    db: GetDBDep,
    store: GetStoreDep,
    user: GetCurrentUserDep,
    audit: GetAuditLoggerDep,
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

        audit.log(
            action=AuditAction.DELETE_TABLE,
            entity_type=AuditEntityType.TABLE,
            entity_id=saloon_id,
            description=f"Deletou salão {saloon_id}"
        )
        db.commit()
        return None
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ========== ROTAS DE MESAS ==========

@router.post("", response_model=TableOut, status_code=status.HTTP_201_CREATED)
async def create_table(
    request: CreateTableRequest,
    db: GetDBDep,
    store: GetStoreDep,
    user: GetCurrentUserDep,
    audit: GetAuditLoggerDep,
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

        audit.log(
            action=AuditAction.CREATE_TABLE,
            entity_type=AuditEntityType.TABLE,
            entity_id=table.id,
            changes=request.model_dump(),
            description=f"Criou mesa '{table.name}'"
        )
        db.commit()
        return table
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.patch("/{table_id}", response_model=TableOut)
async def update_table(
    table_id: int,
    request: UpdateTableRequest,
    db: GetDBDep,
    store: GetStoreDep,
    user: GetCurrentUserDep,
    audit: GetAuditLoggerDep,
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

        audit.log(
            action=AuditAction.UPDATE_TABLE,
            entity_type=AuditEntityType.TABLE,
            entity_id=table.id,
            changes=request.model_dump(exclude_none=True),
            description=f"Atualizou mesa '{table.name}'"
        )
        db.commit()
        return table
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.delete("/{table_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_table(
    table_id: int,
    db: GetDBDep,
    store: GetStoreDep,
    user: GetCurrentUserDep,
    audit: GetAuditLoggerDep,
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

        audit.log(
            action=AuditAction.DELETE_TABLE,
            entity_type=AuditEntityType.TABLE,
            entity_id=table_id,
            description=f"Deletou mesa {table_id}"
        )
        db.commit()
        return None
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ========== ROTAS DE ABERTURA/FECHAMENTO ==========

@router.post("/open", status_code=status.HTTP_200_OK)
async def open_table(
    request: OpenTableRequest,
    db: GetDBDep,
    store: GetStoreDep,
    user: GetCurrentUserDep,
    audit: GetAuditLoggerDep,
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

        audit.log(
            action=AuditAction.OPEN_TABLE,
            entity_type=AuditEntityType.TABLE,
            entity_id=command.table_id,
            changes=request.model_dump(exclude_none=True),
            description=f"Abriu mesa {command.table_id or 'avulsa'} com comanda {command.id}"
        )
        db.commit()
        return {"message": "Mesa aberta com sucesso", "command_id": command.id}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/close", status_code=status.HTTP_200_OK)
async def close_table(
    request: CloseTableRequest,
    db: GetDBDep,
    store: GetStoreDep,
    user: GetCurrentUserDep,
    audit: GetAuditLoggerDep,
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

        audit.log(
            action=AuditAction.CLOSE_TABLE,
            entity_type=AuditEntityType.TABLE,
            entity_id=request.table_id,
            changes=request.model_dump(),
            description=f"Fechou mesa {request.table_id} e comanda {request.command_id}"
        )
        db.commit()
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


# ========== ROTAS AVANÇADAS: TRANSFER / SPLIT / MERGE / MOVE ==========

@router.post("/transfer-items", status_code=status.HTTP_200_OK)
async def transfer_items(
    body: dict,
    db: GetDBDep,
    store: GetStoreDep,
    user: GetCurrentUserDep,
    audit: GetAuditLoggerDep,
):
    """Transfere itens entre comandas"""
    required = ["from_command_id", "to_command_id", "order_product_ids"]
    if not all(k in body for k in required):
        raise HTTPException(status_code=422, detail="Parâmetros ausentes")

    service = TableService(db)
    try:
        ok = service.transfer_items_between_commands(
            store.id,
            int(body["from_command_id"]),
            int(body["to_command_id"]),
            list(map(int, body["order_product_ids"]))
        )

        from src.api.admin.socketio import emitters
        import asyncio
        asyncio.create_task(emitters.admin_emit_tables_and_commands(db=db, store_id=store.id))

        audit.log(
            action=AuditAction.TRANSFER_COMMAND,
            entity_type=AuditEntityType.ORDER,
            changes={
                "from_command_id": body["from_command_id"],
                "to_command_id": body["to_command_id"],
                "order_product_ids": body["order_product_ids"],
            },
            description="Transferiu itens entre comandas"
        )
        db.commit()
        return {"status": "ok" if ok else "noop"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/split-items", status_code=status.HTTP_201_CREATED)
async def split_items(
    body: dict,
    db: GetDBDep,
    store: GetStoreDep,
    user: GetCurrentUserDep,
    audit: GetAuditLoggerDep,
):
    """Cria nova comanda com itens selecionados"""
    required = ["source_command_id", "order_product_ids"]
    if not all(k in body for k in required):
        raise HTTPException(status_code=422, detail="Parâmetros ausentes")

    service = TableService(db)
    try:
        new_cmd = service.split_items_to_new_command(
            store.id,
            int(body["source_command_id"]),
            list(map(int, body["order_product_ids"])),
            int(body["target_table_id"]) if body.get("target_table_id") is not None else None,
        )

        from src.api.admin.socketio import emitters
        import asyncio
        asyncio.create_task(emitters.admin_emit_tables_and_commands(db=db, store_id=store.id))

        audit.log(
            action=AuditAction.CREATE_COMMAND,
            entity_type=AuditEntityType.ORDER,
            entity_id=new_cmd.id,
            changes={k: body[k] for k in body.keys()},
            description="Dividiu itens para nova comanda"
        )
        db.commit()
        return {"message": "Comanda criada", "command_id": new_cmd.id}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/merge-commands", status_code=status.HTTP_200_OK)
async def merge_commands(
    body: dict,
    db: GetDBDep,
    store: GetStoreDep,
    user: GetCurrentUserDep,
    audit: GetAuditLoggerDep,
):
    """Agrupa comandas (source -> target)"""
    required = ["source_command_id", "target_command_id"]
    if not all(k in body for k in required):
        raise HTTPException(status_code=422, detail="Parâmetros ausentes")

    service = TableService(db)
    try:
        ok = service.merge_commands(
            store.id,
            int(body["source_command_id"]),
            int(body["target_command_id"])
        )

        from src.api.admin.socketio import emitters
        import asyncio
        asyncio.create_task(emitters.admin_emit_tables_and_commands(db=db, store_id=store.id))

        audit.log(
            action=AuditAction.MERGE_COMMANDS,
            entity_type=AuditEntityType.ORDER,
            changes={"source": body["source_command_id"], "target": body["target_command_id"]},
            description="Unificou comandas"
        )
        db.commit()
        return {"status": "ok" if ok else "noop"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/move-table", response_model=TableOut)
async def move_table(
    body: dict,
    db: GetDBDep,
    store: GetStoreDep,
    user: GetCurrentUserDep,
    audit: GetAuditLoggerDep,
):
    """Move mesa para outro salão"""
    required = ["table_id", "new_saloon_id"]
    if not all(k in body for k in required):
        raise HTTPException(status_code=422, detail="Parâmetros ausentes")

    service = TableService(db)
    try:
        table = service.move_table_to_saloon(store.id, int(body["table_id"]), int(body["new_saloon_id"]))

        from src.api.admin.socketio import emitters
        import asyncio
        asyncio.create_task(emitters.admin_emit_tables_and_commands(db=db, store_id=store.id))

        audit.log(
            action=AuditAction.UPDATE_TABLE,
            entity_type=AuditEntityType.TABLE,
            entity_id=table.id,
            changes={"new_saloon_id": body["new_saloon_id"]},
            description=f"Moveu mesa {table.id} para salão {body['new_saloon_id']}"
        )
        db.commit()
        return table
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/command-adjustments", status_code=status.HTTP_200_OK)
async def command_adjustments(
    body: dict,
    db: GetDBDep,
    store: GetStoreDep,
    user: GetCurrentUserDep,
    audit: GetAuditLoggerDep,
):
    """Aplica ajustes (desconto/notas) na comanda"""
    if "command_id" not in body:
        raise HTTPException(status_code=422, detail="command_id é obrigatório")

    service = TableService(db)
    try:
        cmd = service.apply_command_adjustments(
            store.id,
            int(body["command_id"]),
            float(body["discount_value"]) if body.get("discount_value") is not None else None,
            body.get("notes")
        )

        from src.api.admin.socketio import emitters
        import asyncio
        asyncio.create_task(emitters.admin_emit_tables_and_commands(db=db, store_id=store.id))

        audit.log(
            action=AuditAction.UPDATE_TABLE,
            entity_type=AuditEntityType.ORDER,
            entity_id=cmd.id,
            changes={k: body[k] for k in body.keys()},
            description="Aplicou ajustes na comanda"
        )
        db.commit()
        return {"status": "ok", "command_id": cmd.id}
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


# ========== NOVAS ROTAS PARA FUNCIONALIDADES AVANÇADAS ==========

@router.post("/assign-employee", status_code=status.HTTP_200_OK)
async def assign_employee_to_table(
    request: AssignEmployeeRequest,
    db: GetDBDep,
    store: GetStoreDep,
    user: GetCurrentUserDep,
    audit: GetAuditLoggerDep,
):
    """Atribui um funcionário a uma mesa"""
    service = TableService(db)
    
    try:
        table = service.assign_employee_to_table(
            store.id, 
            request.table_id, 
            request.employee_id,
            performed_by=user.id
        )
        
        # Emite evento via socket
        from src.api.admin.socketio import emitters
        import asyncio
        asyncio.create_task(
            emitters.admin_emit_tables_and_commands(db=db, store_id=store.id)
        )
        
        audit.log(
            action=AuditAction.UPDATE_TABLE,
            entity_type=AuditEntityType.TABLE,
            entity_id=request.table_id,
            changes={
                "employee_id": request.employee_id,
                "action": "assign_employee" if request.employee_id else "unassign_employee"
            },
            description=f"{'Atribuiu' if request.employee_id else 'Removeu'} funcionário da mesa {request.table_id}"
        )
        db.commit()
        return {
            "message": "Funcionário atribuído com sucesso" if request.employee_id else "Funcionário desatribuído",
            "table": TableOut.from_orm(table)
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/dashboard", response_model=TableDashboardOut)
async def get_tables_dashboard(
    db: GetDBDep,
    store: GetStoreDep,
    user: GetCurrentUserDep,
):
    """Retorna dashboard visual das mesas com status colorido"""
    service = TableService(db)
    
    try:
        dashboard_data = service.get_table_dashboard(store.id)
        return TableDashboardOut(**dashboard_data)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao gerar dashboard: {str(e)}")


@router.get("/{table_id}/activity-report", response_model=TableActivityReport)
async def get_table_activity_report(
    table_id: int,
    db: GetDBDep,
    store: GetStoreDep,
    user: GetCurrentUserDep,
    start_date: datetime | None = None,
    end_date: datetime | None = None,
):
    """Gera relatório de atividades de uma mesa"""
    from datetime import datetime
    
    service = TableService(db)
    
    try:
        report = service.get_table_activity_report(
            store.id, 
            table_id,
            start_date,
            end_date
        )
        return TableActivityReport(**report)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao gerar relatório: {str(e)}")


@router.post("/split-payment", status_code=status.HTTP_201_CREATED)
async def split_payment(
    request: SplitPaymentRequest,
    db: GetDBDep,
    store: GetStoreDep,
    user: GetCurrentUserDep,
    audit: GetAuditLoggerDep,
):
    """Divide o pagamento de uma comanda entre múltiplos clientes"""
    service = TableService(db)
    
    try:
        partial_payments = service.split_payment(
            store.id,
            request.command_id,
            request.split_type,
            request.splits
        )
        
        # Emite evento via socket
        from src.api.admin.socketio import emitters
        import asyncio
        asyncio.create_task(
            emitters.admin_emit_tables_and_commands(db=db, store_id=store.id)
        )
        
        audit.log(
            action=AuditAction.SPLIT_ORDER_PAYMENT,
            entity_type=AuditEntityType.COMMAND,
            entity_id=request.command_id,
            changes=request.model_dump(),
            description=f"Dividiu pagamento da comanda {request.command_id} - {request.split_type}"
        )
        db.commit()
        
        return {
            "message": "Pagamento dividido com sucesso",
            "partial_payments": [
                {
                    "id": p.id,
                    "amount": p.amount,
                    "received_by": p.received_by,
                    "notes": p.notes
                } for p in partial_payments
            ]
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/statistics/today")
async def get_today_statistics(
    db: GetDBDep,
    store: GetStoreDep,
    user: GetCurrentUserDep,
):
    """Retorna estatísticas do dia atual das mesas"""
    from sqlalchemy import func
    from datetime import date
    
    today = date.today()
    
    # Query para estatísticas agregadas
    stats = db.query(
        func.sum(models.Tables.total_orders_today).label("total_orders"),
        func.sum(models.Tables.total_revenue_today).label("total_revenue"),
        func.count(models.Tables.id).label("total_tables"),
        func.sum(func.case([(models.Tables.status == TableStatus.OCCUPIED, 1)], else_=0)).label("occupied_count")
    ).filter(
        models.Tables.store_id == store.id,
        models.Tables.is_deleted == False
    ).first()
    
    # Busca top mesas por receita
    top_tables = db.query(
        models.Tables.id,
        models.Tables.name,
        models.Tables.total_revenue_today,
        models.Tables.total_orders_today
    ).filter(
        models.Tables.store_id == store.id,
        models.Tables.is_deleted == False,
        models.Tables.total_revenue_today > 0
    ).order_by(models.Tables.total_revenue_today.desc()).limit(5).all()
    
    return {
        "date": today.isoformat(),
        "total_orders": stats.total_orders or 0,
        "total_revenue": stats.total_revenue or 0,
        "total_tables": stats.total_tables or 0,
        "occupied_tables": stats.occupied_count or 0,
        "occupation_rate": (stats.occupied_count / stats.total_tables * 100) if stats.total_tables else 0,
        "top_tables": [
            {
                "id": t.id,
                "name": t.name,
                "revenue": t.total_revenue_today,
                "orders": t.total_orders_today
            } for t in top_tables
        ]
    }