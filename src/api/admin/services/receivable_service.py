from datetime import date
from sqlalchemy.orm import Session

# Adapte os imports para os caminhos corretos do seu projeto
from src.core.models import Store, StoreReceivable, ReceivableCategory
from src.api.schemas.financial.receivable import (
    ReceivableCreate,
    ReceivableUpdate,
    ReceivableCategoryCreate,
    ReceivableCategoryUpdate,
)

# --- Service para Categoria de Recebíveis ---

class ReceivableCategoryService:
    def get_by_id(self, db: Session, category_id: int, store_id: int) -> ReceivableCategory | None:
        return db.query(ReceivableCategory).filter(
            ReceivableCategory.id == category_id,
            ReceivableCategory.store_id == store_id
        ).first()

    def list_by_store(self, db: Session, store_id: int) -> list[ReceivableCategory]:
        return db.query(ReceivableCategory).filter(ReceivableCategory.store_id == store_id).order_by(ReceivableCategory.name).all()

    def create(self, db: Session, store: Store, payload: ReceivableCategoryCreate) -> ReceivableCategory:
        category = ReceivableCategory(**payload.model_dump(), store_id=store.id)
        db.add(category)
        db.commit()
        db.refresh(category)
        return category

    def update(self, db: Session, category: ReceivableCategory, payload: ReceivableCategoryUpdate) -> ReceivableCategory:
        category.name = payload.name
        db.commit()
        db.refresh(category)
        return category

    def delete(self, db: Session, category: ReceivableCategory):
        db.delete(category)
        db.commit()

receivable_category_service = ReceivableCategoryService()


# --- Service para Contas a Receber ---

class ReceivableService:
    def get_receivable_by_id(self, db: Session, receivable_id: int, store_id: int) -> StoreReceivable | None:
        return db.query(StoreReceivable).filter(
            StoreReceivable.id == receivable_id,
            StoreReceivable.store_id == store_id
        ).first()

    def list_receivables(self, db: Session, store_id: int, skip: int = 0, limit: int = 100) -> list[StoreReceivable]:
        # TODO: Adicionar filtros (status, customer_id, datas) como fizemos no PayableService
        return db.query(StoreReceivable).filter(
            StoreReceivable.store_id == store_id
        ).order_by(StoreReceivable.due_date.asc()).offset(skip).limit(limit).all()

    def create_receivable(self, db: Session, store: Store, payload: ReceivableCreate) -> StoreReceivable:
        receivable = StoreReceivable(**payload.model_dump(), store_id=store.id)
        db.add(receivable)
        db.commit()
        db.refresh(receivable)
        return receivable

    def update_receivable(self, db: Session, receivable: StoreReceivable, payload: ReceivableUpdate) -> StoreReceivable:
        update_data = payload.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(receivable, key, value)
        db.commit()
        db.refresh(receivable)
        return receivable

    def delete_receivable(self, db: Session, receivable: StoreReceivable):
        db.delete(receivable)
        db.commit()

    def mark_as_received(self, db: Session, receivable: StoreReceivable) -> StoreReceivable:
        """
        Marca uma conta como recebida.
        """
        # Supondo que 'received' é um dos seus status
        if receivable.status != 'received':
            receivable.status = 'received'
            receivable.received_date = date.today()
            db.commit()
            db.refresh(receivable)
        return receivable

receivable_service = ReceivableService()