from sqlalchemy.orm import selectinload

from src.api.schemas.products.category import CategoryCreate
from src.core import models


# ✅ --- FUNÇÃO create_category ATUALIZADA PARA LIDAR COM DADOS ANINHADOS --- ✅
def create_category(db, category_data: CategoryCreate, store_id: int):
    # 1. Separa os dados dos grupos de opções dos dados principais da categoria.
    option_groups_data = category_data.option_groups or []
    category_dict = category_data.model_dump(exclude={'option_groups'})

    # 2. Cria a Categoria principal.
    current_category_count = db.query(models.Category).filter(models.Category.store_id == store_id).count()
    db_category = models.Category(
        **category_dict,
        store_id=store_id,
        priority=current_category_count
    )
    db.add(db_category)

    # 3. Usa db.flush() para obter o ID da nova categoria antes do commit final.
    db.flush()

    # 4. Se foram enviados grupos de opções, itera sobre eles.
    for group_data in option_groups_data:
        items_data = group_data.items or []
        group_dict = group_data.model_dump(exclude={'items'})

        # 5. Cria cada OptionGroup, associando ao ID da categoria.
        db_group = models.OptionGroup(**group_dict, category_id=db_category.id)
        db.add(db_group)
        db.flush()  # Flush para obter o ID do novo grupo

        # 6. Se o grupo tiver itens, itera sobre eles e cria-os.
        for item_data in items_data:
            db_item = models.OptionItem(**item_data.model_dump(), option_group_id=db_group.id)
            db.add(db_item)

    # 7. Commit final: Salva a categoria, os grupos e os itens de uma só vez.
    db.commit()
    db.refresh(db_category)
    return db_category


def get_category(db, category_id: int, store_id: int):
    return db.query(models.Category).options(
        # Carrega os grupos e, dentro de cada grupo, carrega os itens
        selectinload(models.Category.option_groups).selectinload(models.OptionGroup.items)
    ).filter(
        models.Category.id == category_id,
        models.Category.store_id == store_id
    ).first()


def get_all_categories(db, store_id: int):
    return db.query(models.Category).options(
        # Faz o mesmo para a lista completa de categorias
        selectinload(models.Category.option_groups).selectinload(models.OptionGroup.items)
    ).filter(models.Category.store_id == store_id).all()

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