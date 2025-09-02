from sqlalchemy.orm import Session

from src.api.schemas.category import OptionGroupCreate, OptionItemCreate
from src.core import models

# --- CRUD para Grupos de Opções ---
def create_option_group(db: Session, group_data: OptionGroupCreate, category_id: int):
    current_group_count = db.query(models.OptionGroup).filter(models.OptionGroup.category_id == category_id).count()
    db_group = models.OptionGroup(
        **group_data.model_dump(),
        category_id=category_id,
        priority=current_group_count
    )
    db.add(db_group)
    db.commit()
    db.refresh(db_group)
    return db_group

# --- CRUD para Itens de Opção ---
def create_option_item(db: Session, item_data: OptionItemCreate, group_id: int):
    current_item_count = db.query(models.OptionItem).filter(models.OptionItem.option_group_id == group_id).count()
    db_item = models.OptionItem(
        **item_data.model_dump(),
        option_group_id=group_id,
        priority=current_item_count
    )
    db.add(db_item)
    db.commit()
    db.refresh(db_item)
    return db_item