from src.core.models import Product


def update_product_availability(db, db_product: Product, is_available: bool):
    """Atualiza a disponibilidade de um produto e, se estiver sendo ativado,
       garante que sua categoria pai também esteja ativa."""

    db_product.available = is_available

    # Se o produto está sendo ativado
    if is_available is True:
        # Itera sobre os links de categoria do produto
        for link in db_product.category_links:
            if link.category.is_active is False:
                print(f"  -> Categoria '{link.category.name}' estava inativa. Ativando via cascata.")
                link.category.is_active = True
                db.add(link.category)  # Adiciona a categoria à sessão para ser salva

    db.add(db_product)
    db.commit()
    db.refresh(db_product)
    return db_product