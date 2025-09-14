from fastapi import HTTPException
from sqlalchemy import delete
from sqlalchemy.orm import selectinload

from src.api.schemas.products.bulk_actions import BulkCategoryUpdatePayload
from src.api.schemas.products.product import ProductPriceInfo, ProductUpdate
from src.api.schemas.products.product_category_link import ProductCategoryLinkUpdate
from src.core import models
from src.core.models import Product
from src.core.utils.enums import CategoryType, ProductStatus



def update_link_availability(
    db,
    *,
    store_id: int,
    product_id: int,
    category_id: int,
    is_available: bool
) -> models.ProductCategoryLink | None:
    """
    Atualiza a disponibilidade de um vínculo produto-categoria e, se estiver
    ativando o vínculo, garante que o status do produto principal também
    seja ACTIVE.
    """
    # 1. Encontra o vínculo específico que queremos alterar
    db_link = db.query(models.ProductCategoryLink).join(models.Product).filter(
        models.ProductCategoryLink.product_id == product_id,
        models.ProductCategoryLink.category_id == category_id,
        models.Product.store_id == store_id
    ).first()

    if not db_link:
        return None

    # 2. Atualiza o status de disponibilidade do VÍNCULO
    db_link.is_available = is_available

    # 3. LÓGICA INTELIGENTE: Se estamos ATIVANDO o vínculo (is_available=True)...
    if is_available:
        # ...e o produto principal estiver INATIVO...
        if db_link.product.status == ProductStatus.INACTIVE:
            # ...então ativamos o produto principal também!
            db_link.product.status = ProductStatus.ACTIVE
            print(f"Produto '{db_link.product.name}' reativado via cascata.")

    db.add(db_link)
    db.commit()
    db.refresh(db_link)
    return db_link





def get_all_products_for_store(db, store_id: int, skip: int = 0, limit: int = 100):
    """
    Busca todos os produtos de uma loja que NÃO estão arquivados.
    Carrega os relacionamentos necessários para a exibição no painel de admin.
    """
    return db.query(models.Product).options(
        selectinload(models.Product.category_links).selectinload(models.ProductCategoryLink.category),
        selectinload(models.Product.default_options),
        selectinload(models.Product.variant_links)
            .selectinload(models.ProductVariantLink.variant)
            .selectinload(models.Variant.options)
            .selectinload(models.VariantOption.linked_product),
        selectinload(models.Product.prices).selectinload(models.FlavorPrice.size_option),
    ).filter(
        models.Product.store_id == store_id,
        # Filtro crucial para esconder os arquivados
        models.Product.status != ProductStatus.ARCHIVED
    ).order_by(
        models.Product.priority
    ).offset(skip).limit(limit).all()




def update_product_category_link(
        db,
        *,
        store_id: int,
        product_id: int,
        category_id: int,
        payload: ProductCategoryLinkUpdate   # Usa o novo schema
) -> models.ProductCategoryLink | None:
    """
    Atualiza um único vínculo entre produto e categoria. Ideal para pausar/ativar
    um produto em uma categoria específica.
    """
    # Encontra o link específico no banco, garantindo que o produto pertence à loja
    db_link = db.query(models.ProductCategoryLink).join(models.Product).filter(
        models.ProductCategoryLink.product_id == product_id,
        models.ProductCategoryLink.category_id == category_id,
        models.Product.store_id == store_id
    ).first()

    if not db_link:
        return None

    # Pega os dados do payload e atualiza o objeto do banco
    # exclude_unset=True garante que só atualizaremos os campos que vieram na requisição
    update_data = payload.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_link, key, value)

    db.add(db_link)
    db.commit()
    db.refresh(db_link)
    return db_link


def update_product(
        db,
        *,
        db_product: models.Product,
        update_data: ProductUpdate,
        store_id: int
) -> models.Product:
    """
    Atualiza um produto de forma completa, incluindo a sincronização
    de seus vínculos com categorias e preços de sabores.
    """
    # 1. Atualiza os campos simples do produto (nome, estoque, etc.)
    update_dict = update_data.model_dump(
        exclude_unset=True,
        exclude={'category_links', 'variant_links', 'prices'}
    )
    for field, value in update_dict.items():
        setattr(db_product, field, value)
    db.add(db_product)
    db.flush()  # Aplica as mudanças simples imediatamente

    # 2. SINCRONIZAÇÃO DOS VÍNCULOS DE CATEGORIA (SEMPRE ACONTECE)
    #    Isso é crucial para permitir que produtos sejam movidos entre categorias.
    if update_data.category_links is not None:
        # Primeiro, apaga todos os vínculos de categoria antigos para este produto
        db.query(models.ProductCategoryLink).filter(
            models.ProductCategoryLink.product_id == db_product.id
        ).delete(synchronize_session=False)
        db.flush()  # Garante que a exclusão seja registrada na sessão

        # Depois, cria os novos vínculos com base no que veio do frontend
        for link_data in update_data.category_links:
            db.add(models.ProductCategoryLink(product_id=db_product.id, **link_data.model_dump()))

    # 3. SINCRONIZAÇÃO DOS PREÇOS DE SABORES (AGORA CONDICIONAL E CORRETA)
    #    Este bloco só executa se a NOVA categoria for do tipo CUSTOMIZABLE.
    is_customizable_product = False
    if update_data.category_links:
        # Pega a primeira categoria do payload como referência.
        # Numa edição, um sabor só deve estar em uma categoria customizável.
        target_category_id = update_data.category_links[0].category_id
        target_category = db.query(models.Category).get(target_category_id)

        if target_category and target_category.type == CategoryType.CUSTOMIZABLE:
            is_customizable_product = True

    if is_customizable_product and update_data.prices is not None:
        # Apaga todos os preços de sabores antigos para este produto
        db.query(models.FlavorPrice).filter(
            models.FlavorPrice.product_id == db_product.id
        ).delete(synchronize_session=False)
        db.flush()  # Garante que a exclusão seja registrada

        # Cria os novos registros de preço com base no que veio do frontend
        for price_data in update_data.prices:
            db.add(models.FlavorPrice(product_id=db_product.id, **price_data.model_dump()))

    # 4. SINCRONIZAÇÃO DOS VÍNCULOS DE COMPLEMENTOS (pode ser comum a ambos)
    if update_data.variant_links is not None:
        db.query(models.ProductVariantLink).filter(
            models.ProductVariantLink.product_id == db_product.id
        ).delete(synchronize_session=False)
        db.flush()  # Garante que a exclusão seja registrada

        for link_data in update_data.variant_links:
            db.add(models.ProductVariantLink(product_id=db_product.id, **link_data.model_dump()))

    # 5. Salva todas as alterações no banco
    db.commit()
    db.refresh(db_product)
    return db_product





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



def archive_product(db, db_product: models.Product) -> models.Product:
    """Muda o status de um produto para ARCHIVED."""
    db_product.status = ProductStatus.ARCHIVED
    db.commit()
    db.refresh(db_product)
    return db_product

# ✅ NOVA FUNÇÃO PARA ARQUIVAR EM MASSA
def bulk_archive_products(db, store_id: int, product_ids: list[int]):
    """Muda o status de uma lista de produtos para ARCHIVED."""
    db.query(models.Product)\
      .filter(
          models.Product.store_id == store_id,
          models.Product.id.in_(product_ids)
      )\
      .update({"status": ProductStatus.ARCHIVED}, synchronize_session=False)
    db.commit()
    return

