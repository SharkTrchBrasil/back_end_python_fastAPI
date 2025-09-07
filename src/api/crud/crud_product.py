from fastapi import HTTPException
from sqlalchemy import delete

from src.api import schemas
from src.api.schemas.products.product import ProductPriceInfo, BulkCategoryUpdatePayload
from src.core import models
from src.core.models import Product


# Em seu CRUD de produto

def bulk_add_or_update_links(
        db,
        *,
        store_id: int,
        target_category_id: int,
        products_data: list[ProductPriceInfo]
):
    """
    Adiciona ou atualiza o vínculo de múltiplos produtos a uma categoria,
    definindo um preço específico para cada um nesse vínculo.
    """
    product_ids = [p.product_id for p in products_data]

    # 1. Busca de uma vez todos os links que JÁ EXISTEM para otimizar
    existing_links = db.query(models.ProductCategoryLink).filter(
        models.ProductCategoryLink.product_id.in_(product_ids),
        models.ProductCategoryLink.category_id == target_category_id
    ).all()

    # Cria um mapa para acesso rápido: {product_id: link_object}
    existing_links_map = {link.product_id: link for link in existing_links}

    # 2. Itera sobre os dados recebidos do frontend
    for product_info in products_data:
        # Verifica se o produto já estava na categoria
        if product_info.product_id in existing_links_map:
            # Se sim (UPDATE): atualiza o preço e o cód. PDV do link existente
            link_to_update = existing_links_map[product_info.product_id]
            link_to_update.price = product_info.price
            link_to_update.pos_code = product_info.pos_code
        else:
            # Se não (INSERT): cria um novo vínculo ProductCategoryLink
            new_link = models.ProductCategoryLink(
                product_id=product_info.product_id,
                category_id=target_category_id,
                price=product_info.price,
                pos_code=product_info.pos_code
            )
            db.add(new_link)

    # 3. Salva todas as alterações
    db.commit()
    return {"message": "Produtos adicionados à categoria com sucesso"}


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



def remove_product_from_category(
        db,
        *,
        store_id: int,
        product_id: int,
        category_id: int
) -> int:
    """
    Remove o vínculo entre um produto específico e uma categoria específica.
    Retorna o número de vínculos removidos (0 ou 1).
    """
    # Cria a query para deletar o registro específico na tabela de vínculos
    stmt = (
        delete(models.ProductCategoryLink)
        .where(
            models.ProductCategoryLink.product_id == product_id,
            models.ProductCategoryLink.category_id == category_id,
            # Adiciona uma checagem de segurança extra para garantir que o produto pertence à loja
            models.ProductCategoryLink.product.has(store_id=store_id)
        )
    )

    result = db.execute(stmt)
    db.commit()

    # .rowcount retorna quantas linhas foram afetadas (deletadas)
    return result.rowcount






# ✅ ATUALIZE A FUNÇÃO INTEIRA
def bulk_update_product_category(
        db,
        *,
        store_id: int,
        payload: BulkCategoryUpdatePayload
):
    """
    MOVE uma lista de produtos para uma nova categoria, apagando TODOS os vínculos
    antigos e criando novos com os preços e códigos PDV fornecidos.
    """
    product_ids = [p.product_id for p in payload.products]

    # 1. Validações (essenciais para segurança)
    target_category = db.query(models.Category).filter(
        models.Category.id == payload.target_category_id,
        models.Category.store_id == store_id
    ).first()
    if not target_category:
        raise HTTPException(status_code=404, detail="Categoria de destino não encontrada.")

    # 2. APAGA TODOS os vínculos de categoria existentes para os produtos selecionados.
    db.query(models.ProductCategoryLink) \
        .filter(models.ProductCategoryLink.product_id.in_(product_ids)) \
        .delete(synchronize_session=False)

    # 3. CRIA os novos vínculos para cada produto com os novos dados.
    new_links = []
    for product_data in payload.products:
        new_links.append(
            models.ProductCategoryLink(
                product_id=product_data.product_id,
                category_id=payload.target_category_id,
                price=product_data.price,
                pos_code=product_data.pos_code
            )
        )

    if new_links:
        db.bulk_save_objects(new_links)  # Mais performático para múltiplas inserções

    # 4. Salva tudo no banco de dados.
    db.commit()
    return {"message": "Produtos movidos e reprecificados com sucesso."}