import asyncio
from typing import List

from fastapi import APIRouter, Form

from src.api.schemas.variant_selection import VariantSelectionPayload
from src.api.admin.socketio.emitters import admin_emit_products_updated
from src.api.app.socketio.socketio_emitters import emit_products_updated

from src.api.schemas.product import ProductOut, BulkDeletePayload, BulkCategoryUpdatePayload, BulkStatusUpdatePayload, \
    ProductWizardCreate
from src.core import models
from src.core.aws import upload_file, delete_file
from src.core.database import GetDBDep
from src.core.dependencies import GetStoreDep, GetProductDep
from src.core.utils.enums import CashbackType

router = APIRouter(prefix="/stores/{store_id}/products", tags=["Products"])


from fastapi import UploadFile, File, HTTPException
from sqlalchemy.orm import selectinload

# Função helper para os emitters (para não repetir código)
async def _emit_updates(db, store_id: int):
    # await admin_emit_products_updated(db, store_id)
    # await asyncio.create_task(emit_products_updated(db, store_id))
    print(f"Eventos de atualização emitidos para a loja {store_id}")


# ✅ ROTA NOVA E PRINCIPAL: Criar um produto completo via Wizard
@router.post("/wizard", response_model=ProductOut)
async def create_product_from_wizard(
        store: GetStoreDep,
        payload: ProductWizardCreate,  # Recebe um único JSON com todos os dados
        db: GetDBDep,
        image: UploadFile | None = File(None),
):
    """
    Cria um produto completo com categorias e grupos de complementos,
    recebendo todos os dados do wizard do frontend de uma só vez.
    """
    # 1. Validação da Categoria Principal (a primeira da lista)
    if not payload.category_links:
        raise HTTPException(status_code=400, detail="O produto deve pertencer a pelo menos uma categoria.")

    main_category_id = payload.category_links[0].category_id
    category = db.query(models.Category).filter(
        models.Category.id == main_category_id,
        models.Category.store_id == store.id
    ).first()
    if not category:
        raise HTTPException(status_code=404, detail=f"Categoria principal com id {main_category_id} não encontrada.")

    # 2. Upload da Imagem (se houver)
    file_key = None
    if image is not None:
        file_key = upload_file(image)

    # 3. Criação do Objeto Produto (sem salvar ainda)
    new_product_data = payload.model_dump(exclude={'category_links', 'variant_links'})
    new_product = models.Product(
        **new_product_data,
        store_id=store.id,
        file_key=file_key
    )
    db.add(new_product)
    db.flush()  # Aplica a transação para obter o ID do new_product

    # 4. Vinculando as Categorias (usando a tabela de junção)
    for link_data in payload.category_links:
        new_category_link = models.ProductCategoryLink(
            product_id=new_product.id,
            category_id=link_data.category_id,
            price_override=link_data.price_override,
            # ... outros overrides
        )
        db.add(new_category_link)

    # 5. Processamento dos Grupos de Complementos (Variant Links)
    for link_data in payload.variant_links:
        variant_to_link: models.Variant

        if link_data.variant_id < 0 and link_data.new_variant_data:  # ID negativo indica um novo grupo
            new_variant = models.Variant(
                name=link_data.new_variant_data.name,
                type=link_data.new_variant_data.type,
                store_id=store.id
            )
            db.add(new_variant)
            db.flush()

            for option_data in link_data.new_variant_data.options:
                new_option = models.VariantOption(
                    variant_id=new_variant.id,
                    name_override=option_data.name_override,
                    price_override=option_data.price_override,
                )
                db.add(new_option)

            variant_to_link = new_variant
        else:
            existing_variant = db.query(models.Variant).get(link_data.variant_id)
            if not existing_variant or existing_variant.store_id != store.id:
                raise HTTPException(404, f"Variant with id {link_data.variant_id} not found.")
            variant_to_link = existing_variant

        # Cria o vínculo (ProductVariantLink)
        new_link = models.ProductVariantLink(
            product_id=new_product.id,
            variant_id=variant_to_link.id,
            min_selected_options=link_data.min_selected_options,
            max_selected_options=link_data.max_selected_options,
        )
        db.add(new_link)

    # 6. Salva tudo no banco de dados
    db.commit()
    db.refresh(new_product)

    await _emit_updates(db, store.id)
    return new_product





# @router.post("", response_model=ProductOut)
# async def create_product(
#     db: GetDBDep,
#     store: GetStoreDep,
#
#     name: str = Form(...),
#     description: str | None = Form(None),
#     base_price: int = Form(...),
#     cost_price: int | None = Form(None),
#     promotion_price: int | None = Form(None),
#     featured: bool = Form(False),
#     activate_promotion: bool = Form(False),
#     available: bool = Form(True),
#     category_id: int | None = Form(None),
#     ean: str | None = Form(None),
#
#     stock_quantity: int | None = Form(None),
#     control_stock: bool = Form(False),
#     min_stock: int | None = Form(None),
#     max_stock: int | None = Form(None),
#     unit: str | None = Form(None),
#
#     cashback_type: str = Form(default=CashbackType.NONE.value),
#
#     cashback_value: int = Form(default=0),
#
#     image: UploadFile | None = File(None),
# ):
#     category = db.query(models.Category).filter(
#         models.Category.id == category_id,
#         models.Category.store_id == store.id
#     ).first()
#
#     if not category:
#         raise HTTPException(status_code=400, detail="Category not found")
#
#     # --- CÁLCULO DE PRIORIDADE SEQUENCIAL ---
#     # 1. Conta quantos produtos já existem na mesma categoria e loja.
#     current_product_count = db.query(models.Product).filter(
#         models.Product.store_id == store.id,
#         models.Product.category_id == category_id
#     ).count()
#
#     # 2. A contagem atual será a prioridade do novo produto (iniciando em 0).
#     new_product_priority = current_product_count
#     # ----------------------------------------
#
#     file_key = None
#     if image is not None:
#         file_key = upload_file(image)
#
#     new_product = models.Product(
#         name=name,
#         description=description,
#         base_price=base_price,
#         cost_price=cost_price,
#         promotion_price=promotion_price,
#         featured=featured,
#         activate_promotion=activate_promotion,
#         available=available,
#         category_id=category_id,
#         store_id=store.id,
#         ean=ean,
#         priority=new_product_priority,
#
#         stock_quantity=stock_quantity,
#         control_stock=control_stock,
#         min_stock=min_stock,
#         max_stock=max_stock,
#         unit=unit,
#         sold_count=0,
#
#         file_key=file_key,
#         # ✅ ADICIONADO: Passando os valores de cashback para o modelo do banco
#         cashback_type=CashbackType(cashback_type),  # Converte a string de volta para o Enum
#         cashback_value=cashback_value
#     )
#
#     db.add(new_product)
#     db.commit()
#     db.refresh(new_product)
#
#     await asyncio.create_task(emit_products_updated(db, store.id))
#     # Este evento atualiza todos os painéis de admin conectados àquela loja
#     await admin_emit_products_updated(db, store.id)
#     return new_product
#


@router.post("/{product_id}/view", status_code=204)
def record_product_view(
        product: GetProductDep,  # Usa a dependência para garantir que o produto existe
        store: GetStoreDep,  # Usa a dependência para pegar a loja
        db: GetDBDep,
):
    """
    Registra uma única visualização para um produto.

    Este é o endpoint que seu cardápio digital deve chamar toda vez
    que a página de detalhes de um produto for aberta.
    """
    # Cria uma nova entrada na tabela de visualizações
    new_view = models.ProductView(
        product_id=product.id,
        store_id=store.id,
        # customer_id pode ser adicionado aqui se o cliente estiver logado
    )

    db.add(new_view)
    db.commit()

    # Não há necessidade de retornar um corpo, o status 204 (No Content) é suficiente.
    return




@router.get("/minimal", response_model=list[dict])
def get_minimal_products(store_id: int, db: GetDBDep):
    products = db.query(models.Product).filter(models.Product.store_id == store_id).all()
    return [{"id": p.id, "name": p.name} for p in products]


@router.get("", response_model=List[ProductOut])
def get_products(db: GetDBDep, store: GetStoreDep, skip: int = 0, limit: int = 100):
    products = db.query(models.Product).filter(models.Product.store_id == store.id).options(
        selectinload(models.Product.category_links).selectinload(models.ProductCategoryLink.category),
        selectinload(models.Product.variant_links).selectinload(models.ProductVariantLink.variant).selectinload(models.Variant.options)
    ).order_by(models.Product.id.desc()).offset(skip).limit(limit).all()
    return products


@router.get("/{product_id}", response_model=ProductOut)
def get_product_details(product: GetProductDep, db: GetDBDep):
    product_with_details = db.query(models.Product).options(
        selectinload(models.Product.category_links).selectinload(models.ProductCategoryLink.category),
        selectinload(models.Product.variant_links).selectinload(models.ProductVariantLink.variant).selectinload(models.Variant.options)
    ).filter(models.Product.id == product.id).first()
    if not product_with_details:
        raise HTTPException(status_code=404, detail="Product not found")
    return product_with_details

@router.patch("/{product_id}", response_model=ProductOut)
async def patch_product(
    product_id: int,
    db: GetDBDep,
    store: GetStoreDep,
    db_product: GetProductDep,

    name: str | None = Form(None),
    description: str | None = Form(None),
    base_price: int | None = Form(None),
    cost_price: int | None = Form(None),
    promotion_price: int | None = Form(None),
    featured: bool | None = Form(None),
    activate_promotion: bool | None = Form(None),
    available: bool | None = Form(None),
    category_id: int | None = Form(None),
    ean: str | None = Form(None),

    stock_quantity: int | None = Form(None),
    control_stock: bool | None = Form(None),
    min_stock: int | None = Form(None),
    max_stock: int | None = Form(None),
    unit: str | None = Form(None),
    image: UploadFile | None = File(None),

    cashback_type: str | None = Form(None),
    cashback_value: int | None = Form(None),
):
    # Atualizar campos presentes
    if name is not None:
        db_product.name = name
    if description is not None:
        db_product.description = description
    if base_price is not None:
        db_product.base_price = base_price
    if cost_price is not None:
        db_product.cost_price = cost_price
    if promotion_price is not None:
        db_product.promotion_price = promotion_price
    if featured is not None:
        db_product.featured = featured
    if activate_promotion is not None:
        db_product.activate_promotion = activate_promotion
    if available is not None:
        db_product.available = available
    if ean is not None:
        db_product.ean = ean
    if stock_quantity is not None:
        db_product.stock_quantity = stock_quantity
    if control_stock is not None:
        db_product.control_stock = control_stock
    if min_stock is not None:
        db_product.min_stock = min_stock
    if max_stock is not None:
        db_product.max_stock = max_stock
    if unit is not None:
        db_product.unit = unit

    if cashback_type is not None:
        db_product.cashback_type = CashbackType(cashback_type) # Converte string para Enum
    if cashback_value is not None:
        db_product.cashback_value = cashback_value

    if category_id is not None:
        category = db.query(models.Category).filter(
            models.Category.id == category_id,
            models.Category.store_id == store.id
        ).first()
        if not category:
            raise HTTPException(status_code=400, detail="Category not found")
        db_product.category_id = category_id


    if image:
        old_file_key = db_product.file_key
        new_file_key = upload_file(image)
        db_product.file_key = new_file_key
        db.commit()
        delete_file(old_file_key)
    else:
        db.commit()

    db.refresh(db_product)
    await asyncio.create_task(emit_products_updated(db, store.id))

    # Este evento atualiza todos os painéis de admin conectados àquela loja
    await admin_emit_products_updated(db, store.id)
    return db_product




@router.delete("/{product_id}", status_code=204)
async def delete_product(product_id: int,  store: GetStoreDep, db: GetDBDep, db_product: GetProductDep):
    old_file_key = db_product.file_key
    db.delete(db_product)
    db.commit()
    delete_file(old_file_key)
    await asyncio.create_task(emit_products_updated(db, store.id))
    return


@router.post("/bulk-delete", status_code=204)
async def bulk_delete_products(
    store: GetStoreDep,
    db: GetDBDep,
    payload: BulkDeletePayload,
):
    """
    Remove uma lista de produtos de uma vez.
    """
    if not payload.product_ids:
        return

    # IMPORTANTE: Antes de deletar, pegue os file_keys para apagar da AWS/S3
    products_to_delete = db.query(models.Product)\
                           .filter(models.Product.id.in_(payload.product_ids)).all()

    for product in products_to_delete:
        if product.file_key:
            delete_file(product.file_key) # Função que apaga o arquivo da S3

    # Agora, delete os registros do banco
    db.query(models.Product)\
      .filter(
          models.Product.store_id == store.id,
          models.Product.id.in_(payload.product_ids)
      )\
      .delete(synchronize_session=False)

    db.commit()

    await admin_emit_products_updated(db, store.id)
    await asyncio.create_task(emit_products_updated(db, store.id))
    return


@router.post("/bulk-update-category", status_code=204)
async def bulk_update_product_category(
        store: GetStoreDep,
        db: GetDBDep,
        payload: BulkCategoryUpdatePayload,
):
    """
    Define a categoria de uma lista de produtos para uma nova categoria.
    Esta operação REMOVE os produtos de todas as categorias antigas
    e os vincula APENAS à nova categoria de destino.
    """
    if not payload.product_ids:
        raise HTTPException(status_code=400, detail="Nenhum ID de produto foi fornecido.")

    # 1. Verifica se a categoria de destino existe e pertence à loja
    target_category = db.query(models.Category).filter(
        models.Category.id == payload.target_category_id,
        models.Category.store_id == store.id
    ).first()

    if not target_category:
        raise HTTPException(status_code=404, detail="Categoria de destino não encontrada.")

    # 2. Deleta TODOS os vínculos de categoria existentes para os produtos selecionados.
    # Isso garante que eles não fiquem em categorias antigas.
    db.query(models.ProductCategoryLink) \
        .filter(models.ProductCategoryLink.product_id.in_(payload.product_ids)) \
        .delete(synchronize_session=False)

    # 3. Cria os novos vínculos para cada produto com a categoria de destino.
    new_links = []
    for product_id in payload.product_ids:
        # Verifica se o produto realmente pertence à loja para segurança
        product = db.query(models.Product.id).filter(
            models.Product.id == product_id,
            models.Product.store_id == store.id
        ).first()

        if product:
            new_links.append(
                models.ProductCategoryLink(
                    product_id=product_id,
                    category_id=payload.target_category_id
                    # A lógica de prioridade foi removida, pois agora um produto
                    # não tem uma "prioridade dentro de uma categoria".
                    # A ordem dos produtos é gerenciada na própria categoria.
                )
            )

    if new_links:
        db.add_all(new_links)

    # 4. Salva todas as alterações no banco de dados.
    db.commit()

    # 5. Emite o evento para que as telas sejam atualizadas.
    # (Supondo que você tenha essas funções)

    await admin_emit_products_updated(db, store.id)
    await asyncio.create_task(emit_products_updated(db, store.id))

    return

@router.post("/bulk-update-status", status_code=204)
async def bulk_update_product_status(
    store: GetStoreDep,
    db: GetDBDep,
    payload: BulkStatusUpdatePayload,
):
    """
    Ativa ou desativa uma lista de produtos de uma vez.
    """
    if not payload.product_ids:
        return # Não faz nada se a lista for vazia

    # Executa uma única query para atualizar todos os produtos de uma vez
    db.query(models.Product)\
      .filter(
          models.Product.store_id == store.id,
          models.Product.id.in_(payload.product_ids)
      )\
      .update({"available": payload.available}, synchronize_session=False)

    db.commit()

    await admin_emit_products_updated(db, store.id)
    await asyncio.create_task(emit_products_updated(db, store.id))
    return