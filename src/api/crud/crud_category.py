from sqlalchemy.orm import Session

from src.api.schemas.category import CategoryCreate
from src.core import models

# A criação de categoria agora é super simples!
def create_category(db: Session, category_data: CategoryCreate, store_id: int):
    current_category_count = db.query(models.Category).filter(models.Category.store_id == store_id).count()
    db_category = models.Category(
        name=category_data.name,
        type=category_data.type,
        is_active=category_data.is_active,
        store_id=store_id,
        priority=current_category_count
    )
    db.add(db_category)
    db.commit()
    db.refresh(db_category)
    return db_category

def get_category(db: Session, category_id: int, store_id: int):
    return db.query(models.Category).filter(models.Category.id == category_id, models.Category.store_id == store_id).first()

# Adicione get_all, update, delete aqui...