from fastapi import APIRouter, Depends, HTTPException

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
):
    # Lógica para evitar documentos duplicados para a mesma loja
    # ...
    return supplier_service.create_supplier(db, store, payload)

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
    """
    Busca um fornecedor pelo seu ID.
    """
    supplier = supplier_service.get_supplier_by_id(
        db, supplier_id=supplier_id, store_id=store.id
    )

    if not supplier:
        raise HTTPException(status_code=404, detail="Supplier not found")

    return supplier



@router.patch("/{supplier_id}", response_model=SupplierResponse)
def update_supplier(
        supplier_id: int,
        payload: SupplierUpdate,
        store: GetStoreDep,
        db: GetDBDep,
):
    """
    Atualiza as informações de um fornecedor. Apenas os campos enviados
    no corpo da requisição serão atualizados.
    """
    supplier = supplier_service.get_supplier_by_id(
        db, supplier_id=supplier_id, store_id=store.id
    )

    if not supplier:
        raise HTTPException(status_code=404, detail="Supplier not found")

    # Lógica para checar duplicidade de documento (CNPJ/CPF) se ele for alterado
    # if payload.document and payload.document != supplier.document:
    #    existing = supplier_service.get_by_document(db, document=payload.document, store_id=store.id)
    #    if existing:
    #        raise HTTPException(status_code=400, detail="Document already registered for another supplier")

    return supplier_service.update_supplier(db, supplier=supplier, payload=payload)



@router.delete("/{supplier_id}", status_code=204)
def delete_supplier(
        supplier_id: int,
        store: GetStoreDep,
        db: GetDBDep,
):
    """
    Remove um fornecedor do banco de dados.
    """
    supplier = supplier_service.get_supplier_by_id(
        db, supplier_id=supplier_id, store_id=store.id
    )

    if not supplier:
        raise HTTPException(status_code=404, detail="Supplier not found")

    supplier_service.delete_supplier(db, supplier=supplier)

    # Retorna uma resposta vazia com status 204 No Content
    return