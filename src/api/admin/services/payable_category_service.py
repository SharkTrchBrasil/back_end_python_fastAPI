# Em: src/api/services/payable_category_service.py
from sqlalchemy.orm import Session
from src.core.models import PayableCategory, Store
from src.api.schemas.financial.payable_category import PayableCategoryCreate, PayableCategoryUpdate

class PayableCategoryService:
    def get_by_id(self, db: Session, category_id: int, store_id: int) -> PayableCategory | None:
        return db.query(PayableCategory).filter(
            PayableCategory.id == category_id,
            PayableCategory.store_id == store_id
        ).first()

    def list_by_store(self, db: Session, store_id: int) -> list[PayableCategory]:
        return db.query(PayableCategory).filter(PayableCategory.store_id == store_id).order_by(PayableCategory.name).all()

    def create(self, db: Session, store: Store, payload: PayableCategoryCreate) -> PayableCategory:
        category = PayableCategory(**payload.model_dump(), store_id=store.id)
        db.add(category)
        db.commit()
        db.refresh(category)
        return category

    def update(self, db: Session, category: PayableCategory, payload: PayableCategoryUpdate) -> PayableCategory:
        category.name = payload.name
        db.commit()
        db.refresh(category)
        return category

    def delete(self, db: Session, category: PayableCategory):
        db.delete(category)
        db.commit()

payable_category_service = PayableCategoryService()