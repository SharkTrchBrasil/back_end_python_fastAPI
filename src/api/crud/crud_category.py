from sqlalchemy.orm import Session

from src.api.schemas.category import CategoryCreate
from src.core import models

# A criação de categoria agora é super simples!
def create_category(db, category_data: CategoryCreate, store_id: int):
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

def get_category(db, category_id: int, store_id: int):
    return db.query(models.Category).filter(models.Category.id == category_id, models.Category.store_id == store_id).first()


def get_all_categories(db, store_id: int):
    return db.query(models.Category).filter(models.Category.store_id == store_id).all()
# Adicione get_all, update, delete aqui...


def update_category_status(db, db_category: models.Category, is_active: bool):
    """Atualiza o status de uma categoria e, se estiver sendo desativada,
       desativa todos os produtos associados."""

    db_category.is_active = is_active

    # Se a categoria está sendo pausada (desativada)
    if is_active is False:
        # Itera sobre os links de produto e desativa cada produto
        for link in db_category.product_links:
            link.product.available = False
            print(f"  -> Desativando produto '{link.product.name}' via cascata.")

    db.add(db_category)
    db.commit()
    db.refresh(db_category)
    return db_category