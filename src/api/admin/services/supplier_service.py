from sqlalchemy.orm import Session

from src.api.schemas.payable.supplier import SupplierCreate, SupplierUpdate
from src.core.models import Supplier, Store



class SupplierService:
    def get_supplier_by_id(self, db: Session, supplier_id: int, store_id: int) -> Supplier | None:
        return db.query(Supplier).filter(Supplier.id == supplier_id, Supplier.store_id == store_id).first()

    def list_suppliers(self, db: Session, store_id: int, skip: int = 0, limit: int = 100) -> list[Supplier]:
        return db.query(Supplier).filter(Supplier.store_id == store_id).offset(skip).limit(limit).all()

    def create_supplier(self, db: Session, store: Store, payload: SupplierCreate) -> Supplier:
        supplier = Supplier(**payload.model_dump(), store_id=store.id)
        db.add(supplier)
        db.commit()
        db.refresh(supplier)
        return supplier

    def update_supplier(self, db: Session, supplier: Supplier, payload: SupplierUpdate) -> Supplier:
        update_data = payload.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(supplier, key, value)
        db.commit()
        db.refresh(supplier)
        return supplier

    def delete_supplier(self, db: Session, supplier: Supplier):
        db.delete(supplier)
        db.commit()


supplier_service = SupplierService()