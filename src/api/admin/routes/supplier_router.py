from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
# ✅ 1. ADIÇÃO DOS IMPORTS NECESSÁRIOS
from src.api.admin.socketio.emitters import admin_emit_financials_updated
from src.api.admin.services.supplier_service import supplier_service
from src.core.database import GetDBDep
from src.core.dependencies import GetStoreDep
from src.core.models import Store, Supplier
from src.api.schemas.supplier import SupplierCreate, SupplierUpdate, SupplierResponse

router = APIRouter(prefix="/stores/{store_id}/suppliers", tags=["Suppliers"])


@router.post("", response_model=SupplierResponse, status_code=201)
def create_supplier(
        payload: SupplierCreate,
        store: GetStoreDep,
        db: GetDBDep,
        # ✅ 2. ADICIONA A DEPENDÊNCIA
        background_tasks: BackgroundTasks,
):
    supplier = supplier_service.create_supplier(db, store, payload)

    # ✅ 3. AGENDA A TAREFA APÓS A CRIAÇÃO
    background_tasks.add_task(admin_emit_financials_updated, db=db, store_id=store.id)

    return supplier


@router.patch("/{supplier_id}", response_model=SupplierResponse)
def update_supplier(
        supplier_id: int,
        payload: SupplierUpdate,
        store: GetStoreDep,
        db: GetDBDep,
        # ✅ 2. ADICIONA A DEPENDÊNCIA
        background_tasks: BackgroundTasks,
):
    supplier = supplier_service.get_supplier_by_id(
        db, supplier_id=supplier_id, store_id=store.id
    )
    if not supplier:
        raise HTTPException(status_code=404, detail="Supplier not found")

    # ✅ 3. CHAMA O SERVIÇO DE UPDATE PRIMEIRO
    updated_supplier = supplier_service.update_supplier(db, supplier=supplier, payload=payload)

    # ✅ DEPOIS, AGENDA A TAREFA
    background_tasks.add_task(admin_emit_financials_updated, db=db, store_id=store.id)

    return updated_supplier


@router.delete("/{supplier_id}", status_code=204)
def delete_supplier(
        supplier_id: int,
        store: GetStoreDep,
        db: GetDBDep,
        # ✅ 2. ADICIONA A DEPENDÊNCIA
        background_tasks: BackgroundTasks,
):
    supplier = supplier_service.get_supplier_by_id(
        db, supplier_id=supplier_id, store_id=store.id
    )
    if not supplier:
        raise HTTPException(status_code=404, detail="Supplier not found")

    # ✅ 3. CHAMA O SERVIÇO DE DELETE PRIMEIRO
    supplier_service.delete_supplier(db, supplier=supplier)

    # ✅ DEPOIS, AGENDA A TAREFA
    background_tasks.add_task(admin_emit_financials_updated, db=db, store_id=store.id)

    return


# --- ROTAS DE LEITURA (GET) NÃO PRECISAM DE ALTERAÇÃO ---

@router.get("", response_model=list[SupplierResponse])
def list_suppliers(
        store: GetStoreDep,
        db: GetDBDep,
):
    return supplier_service.list_suppliers(db, store_id=store.id)


@router.get("/{supplier_id}", response_model=SupplierResponse)
def get_supplier(
        supplier_id: int,
        store: GetStoreDep,
        db: GetDBDep,
):
    supplier = supplier_service.get_supplier_by_id(
        db, supplier_id=supplier_id, store_id=store.id
    )
    if not supplier:
        raise HTTPException(status_code=404, detail="Supplier not found")
    return supplier