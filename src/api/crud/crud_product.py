from fastapi import HTTPException
from sqlalchemy import delete, func
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



def get_all_products_for_store(
        db,
        store_id: int,
        skip: int = 0,
        limit: int = 50,  # ✅ REDUZIR de 100 para 50
        load_relationships: bool = True  # ✅ NOVO: controla carregamento
):
    """
    ✅ VERSÃO OTIMIZADA: Carrega produtos com controle de relacionamentos
    """
    query = db.query(models.Product)

    # ✅ SÓ CARREGA RELACIONAMENTOS SE NECESSÁRIO
    if load_relationships:
        query = query.options(
            selectinload(models.Product.gallery_images),
            selectinload(models.Product.category_links)
            .selectinload(models.ProductCategoryLink.category),
            # ✅ REMOVIDO: default_options (raramente usado)
            # ✅ SIMPLIFICADO: variant_links (carrega apenas o mínimo)
            selectinload(models.Product.variant_links)
            .selectinload(models.ProductVariantLink.variant),
            # ✅ REMOVIDO: prices detalhados (pode ser carregado sob demanda)
        )

    return query.filter(
        models.Product.store_id == store_id,
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
        store_id: int,
        new_gallery_file_keys: list[str] | None = None
) -> tuple[models.Product, list[str]]:
    print("--- 🛠️  Dentro de crud_product.update_product ---")

    file_keys_to_delete_from_s3 = []


    if 'video_url' in update_data.model_fields_set:
        db_product.video_url = update_data.video_url


    # --- ATUALIZAÇÃO DE CAMPOS SIMPLES (incluindo video_url) ---
    update_dict = update_data.model_dump(
        exclude_unset=True,
        # Exclui os campos de relacionamento que trataremos separadamente
        exclude={'category_links', 'variant_links', 'prices', 'gallery_images_order', 'gallery_images_to_delete', 'video_url'}
    )
    for field, value in update_dict.items():
        setattr(db_product, field, value)

    db.flush()


    # a) Deletar imagens marcadas para exclusão
    if update_data.gallery_images_to_delete:
        print(f"   -> 🔍 Procurando imagens no DB para deletar com IDs: {update_data.gallery_images_to_delete}")
        images_to_delete_query = db.query(models.ProductImage).filter(
            models.ProductImage.product_id == db_product.id,
            models.ProductImage.id.in_(update_data.gallery_images_to_delete)
        )
        images_to_delete = images_to_delete_query.all()

        file_keys_to_delete_from_s3.extend([img.file_key for img in images_to_delete])

        images_to_delete_query.delete(synchronize_session=False)
        db.flush()
        print(f"   -> 🔥 Deletadas {len(images_to_delete)} imagens do produto {db_product.id} no banco.")
    else:
        print("   -> Nenhuma imagem marcada para exclusão.")

    # b) Reordenar imagens existentes
    if update_data.gallery_images_order:
        print(f"   -> 🔄 Reordenando {len(update_data.gallery_images_order)} imagens existentes...")
        for order_info in update_data.gallery_images_order:
            db.query(models.ProductImage).filter(
                models.ProductImage.id == order_info['id'],
                models.ProductImage.product_id == db_product.id
            ).update({'display_order': order_info['order']}, synchronize_session=False)
    else:
        print("   -> Nenhuma instrução de reordenação.")

    # c) Adicionar novas imagens (se houver)
    if new_gallery_file_keys:
        print(f"   -> ✨ Adicionando {len(new_gallery_file_keys)} novas imagens ao DB...")
        max_order = db.query(func.max(models.ProductImage.display_order)).filter(
            models.ProductImage.product_id == db_product.id
        ).scalar() or -1

        for index, file_key in enumerate(new_gallery_file_keys):
            new_image_db = models.ProductImage(
                product_id=db_product.id,
                file_key=file_key,
                display_order=max_order + 1 + index
            )
            db.add(new_image_db)
    else:
        print("   -> Nenhuma imagem nova para adicionar ao DB.")

        # 2. Sincroniza os Vínculos de Categoria
    if update_data.category_links is not None:
        db.query(models.ProductCategoryLink).filter(
            models.ProductCategoryLink.product_id == db_product.id
        ).delete(synchronize_session=False)
        db.flush()
        for link_data in update_data.category_links:
            db.add(models.ProductCategoryLink(product_id=db_product.id, **link_data.model_dump()))

        # 2.5. Sincronização dos Preços de Sabores (Condicional)
    is_customizable_product = False
    if update_data.category_links:
        target_category_id = update_data.category_links[0].category_id
        target_category = db.query(models.Category).get(target_category_id)
        if target_category and target_category.type == CategoryType.CUSTOMIZABLE:
            is_customizable_product = True

    if is_customizable_product and update_data.prices is not None:
        db.query(models.FlavorPrice).filter(
            models.FlavorPrice.product_id == db_product.id
        ).delete(synchronize_session=False)
        db.flush()
        for price_data in update_data.prices:
            db.add(models.FlavorPrice(product_id=db_product.id, **price_data.model_dump()))

    # 3. ✅ LÓGICA DE COMPLEMENTOS CORRIGIDA E MELHORADA
    if update_data.variant_links is not None:
        # Apaga os VÍNCULOS antigos para sincronizar
        db.query(models.ProductVariantLink).filter(
            models.ProductVariantLink.product_id == db_product.id
        ).delete(synchronize_session=False)
        db.flush()

        for link_data in update_data.variant_links:
            variant_data = link_data.variant

            if variant_data.id and variant_data.id > 0:
                # --- É UM GRUPO EXISTENTE ---

                # a. Recria o vínculo do produto com este grupo
                db.add(models.ProductVariantLink(
                    product_id=db_product.id,
                    variant_id=variant_data.id,
                    min_selected_options=link_data.min_selected_options,
                    max_selected_options=link_data.max_selected_options,
                    ui_display_mode=link_data.ui_display_mode,
                    available=link_data.available
                ))
                db.flush()

                # b. ✅ CORREÇÃO: SINCRONIZAÇÃO COMPLETA DAS OPÇÕES (ADIÇÃO, ATUALIZAÇÃO E REMOÇÃO)
                if variant_data.options is not None:
                    # IDs das opções que vieram do frontend
                    incoming_option_ids = {opt.id for opt in variant_data.options if opt.id}

                    # IDs das opções que já existem no banco para este grupo
                    existing_option_ids = {
                        opt_id[0] for opt_id in db.query(models.VariantOption.id).filter(
                            models.VariantOption.variant_id == variant_data.id
                        ).all()
                    }

                    # REMOVER: Opções que estão no banco mas não vieram do frontend
                    options_to_delete_ids = existing_option_ids - incoming_option_ids
                    if options_to_delete_ids:
                        db.query(models.VariantOption).filter(
                            models.VariantOption.id.in_(options_to_delete_ids)
                        ).delete(synchronize_session=False)
                        db.flush()

                    # ADICIONAR/ATUALIZAR: Itera sobre as opções do frontend
                    for option_data in variant_data.options:
                        if option_data.id and option_data.id > 0:
                            # ATUALIZAR opção existente
                            db_option = db.query(models.VariantOption).get(option_data.id)
                            if db_option:
                                option_update_dict = option_data.model_dump(exclude_unset=True)
                                for key, value in option_update_dict.items():
                                    setattr(db_option, key, value)
                                db.add(db_option)
                        else:
                            # ADICIONAR nova opção a um grupo existente
                            db.add(models.VariantOption(
                                variant_id=variant_data.id,
                                store_id=store_id,
                                **option_data.model_dump(exclude={'image', 'id', 'variant_id'})
                            ))
                # Se `variant_data.options` for uma lista vazia `[]`, o código acima irá
                # apagar todas as opções existentes, que é o comportamento esperado.

            else:
                # --- É UM GRUPO NOVO --- (Sua lógica aqui já estava correta)
                new_variant = models.Variant(
                    name=variant_data.name,
                    type=variant_data.type.value,
                    store_id=store_id
                )
                db.add(new_variant)
                db.flush()

                if variant_data.options:
                    for option_data in variant_data.options:


                        db.add(models.VariantOption(
                            variant_id=new_variant.id,
                            store_id=store_id,
                            **option_data.model_dump(exclude={'image', 'id', 'variant_id'})
                        ))


                db.add(models.ProductVariantLink(
                    product_id=db_product.id,
                    variant_id=new_variant.id,
                    min_selected_options=link_data.min_selected_options,
                    max_selected_options=link_data.max_selected_options,
                    ui_display_mode=link_data.ui_display_mode,
                    available=link_data.available
                ))

    # 4. Salva tudo no banco
    db.commit()
    db.refresh(db_product)

    return db_product, file_keys_to_delete_from_s3






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

