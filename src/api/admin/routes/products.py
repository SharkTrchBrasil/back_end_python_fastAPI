from typing import List
from fastapi import APIRouter, Form, UploadFile, File, HTTPException
import json
from pydantic import ValidationError
from sqlalchemy.orm import selectinload
from starlette import status

from src.api.admin.utils.emit_updates import emit_updates_products
from src.api.crud.crud_product import update_product_availability
from src.api.schemas.products.bulk_actions import BulkCategoryUpdatePayload, BulkDeletePayload, BulkStatusUpdatePayload
from src.api.schemas.products.product import (
    ProductOut,
    ProductUpdate,
    FlavorWizardCreate,
    SimpleProductWizardCreate,
    FlavorPriceUpdate  # Precisaremos de um novo schema para o update de preço
)
from src.api.schemas.products.product_category_link import ProductCategoryLinkUpdate, ProductCategoryLinkOut
from src.core import models
from src.core.aws import upload_file, delete_file
from src.core.database import GetDBDep
from src.core.dependencies import GetStoreDep, GetProductDep

router = APIRouter(prefix="/stores/{store_id}/products", tags=["Products"])


# ===================================================================
# ROTA 1: CRIAR PRODUTO SIMPLES (Ex: Bebidas, Lanches)
# ===================================================================
# Em seu arquivo de rotas de produtos

@router.post("/simple-product", response_model=ProductOut, status_code=201)
async def create_simple_product(
        store: GetStoreDep,
        db: GetDBDep,
        payload_str: str = Form(..., alias="payload"),
        image: UploadFile | None = File(None),
):
    """Cria um produto do tipo GENERAL com preços definidos por categoria."""
    try:
        payload = SimpleProductWizardCreate.model_validate_json(payload_str)
    except ValidationError as e:
        raise HTTPException(status_code=422, detail=f"JSON inválido: {e}")

    file_key = upload_file(image) if image else None

    # Pega os dados principais do produto, excluindo as listas aninhadas
    product_data = payload.model_dump(exclude={'category_links', 'variant_links', 'tags'})

    # Cria a instância do produto no banco
    new_product = models.Product(
        **product_data,
        store_id=store.id,
        file_key=file_key,
        tags=payload.tags or []
    )
    db.add(new_product)
    db.flush()  # Para obter o new_product.id

    # Itera e salva os links com as categorias e seus preços
    for link_data in payload.category_links:
        db.add(models.ProductCategoryLink(product_id=new_product.id, **link_data.model_dump()))

    # ✅ ADICIONADO: Loop para salvar os links de variantes (complementos)
    for link_data in payload.variant_links:
        db.add(models.ProductVariantLink(product_id=new_product.id, **link_data.model_dump()))

    # Salva tudo no banco de uma vez
    db.commit()
    db.refresh(new_product)

    # Notifica os clientes sobre a mudança
    await emit_updates_products(db, store.id)

    return new_product

# ===================================================================
# ROTA 2: CRIAR "SABOR" (PRODUTO CUSTOMIZÁVEL)
# ===================================================================
@router.post("/flavor-product", response_model=ProductOut, status_code=201)
async def create_flavor_product(
        store: GetStoreDep,
        db: GetDBDep,
        payload_str: str = Form(..., alias="payload"),
        image: UploadFile | None = File(None),
):
    """Cria um produto do tipo 'sabor' com preços definidos por tamanho."""
    try:
        payload = FlavorWizardCreate.model_validate_json(payload_str)
    except ValidationError as e:
        raise HTTPException(status_code=422, detail=f"JSON inválido: {e}")

    parent_category = db.query(models.Category).filter(models.Category.id == payload.parent_category_id,
                                                       models.Category.store_id == store.id).first()
    if not parent_category:
        raise HTTPException(status_code=404, detail="Categoria pai não encontrada.")

    file_key = upload_file(image) if image else None
    product_data = payload.model_dump(exclude={'prices', 'parent_category_id'})

    new_product = models.Product(**product_data, store_id=store.id, file_key=file_key)
    db.add(new_product)
    db.flush()

    db.add(models.ProductCategoryLink(product_id=new_product.id, category_id=payload.parent_category_id, price=0))

    for price_data in payload.prices:
        db.add(models.FlavorPrice(product_id=new_product.id, **price_data.model_dump()))

    db.commit()
    db.refresh(new_product)
    await emit_updates_products(db, store.id)
    return new_product


# ===================================================================
# ROTA 3: ATUALIZAÇÃO UNIFICADA DE DADOS BÁSICOS (PATCH)
# ===================================================================
@router.patch("/{product_id}", response_model=ProductOut)
async def update_product(
        store: GetStoreDep,
        db: GetDBDep,
        db_product: GetProductDep,
        payload_str: str = Form(..., alias="payload"),
        image: UploadFile | None = File(None),
):
    """Atualiza os dados básicos de QUALQUER tipo de produto."""
    try:
        update_data = ProductUpdate.model_validate_json(payload_str)
    except ValidationError as e:
        raise HTTPException(status_code=422, detail=f"JSON inválido: {e}")

    update_dict = update_data.model_dump(exclude_unset=True)

    if 'available' in update_dict:
        update_product_availability(db=db, db_product=db_product, is_available=update_data.available)
        update_dict.pop('available')

    for field, value in update_dict.items():
        setattr(db_product, field, value)

    if image:
        if db_product.file_key:
            delete_file(db_product.file_key)
        db_product.file_key = upload_file(image)

    db.commit()
    db.refresh(db_product)
    await emit_updates_products(db, store.id)
    return db_product


# ===================================================================
# ROTAS PARA ATUALIZAÇÃO DE PREÇOS
# ===================================================================

@router.patch("/{product_id}/categories/{category_id}", response_model=ProductCategoryLinkOut)
async def update_simple_product_price(
        store: GetStoreDep,
        product_id: int,
        category_id: int,
        update_data: ProductCategoryLinkUpdate,
        db: GetDBDep,
):
    """Atualiza o preço/promoção de um produto simples em uma categoria específica."""
    db_link = db.query(models.ProductCategoryLink).filter(
        models.ProductCategoryLink.product_id == product_id,
        models.ProductCategoryLink.category_id == category_id
    ).first()
    if not db_link:
        raise HTTPException(status_code=404, detail="Vínculo produto-categoria não encontrado.")

    for field, value in update_data.model_dump(exclude_unset=True).items():
        setattr(db_link, field, value)

    db.commit()
    db.refresh(db_link)
    await emit_updates_products(db, store.id)
    return db_link


@router.patch("/prices/{flavor_price_id}", response_model=ProductOut)
async def update_flavor_price(
        store: GetStoreDep,
        flavor_price_id: int,
        update_data: FlavorPriceUpdate,
        db: GetDBDep,
):
    """Atualiza o preço de um sabor para um tamanho específico."""
    db_price_link = db.query(models.FlavorPrice).join(models.Product).filter(
        models.FlavorPrice.id == flavor_price_id,
        models.Product.store_id == store.id
    ).first()
    if not db_price_link:
        raise HTTPException(status_code=404, detail="Preço para este tamanho não encontrado.")

    db_price_link.price = update_data.price
    db.commit()

    product_to_return = db.query(models.Product).get(db_price_link.product_id)
    db.refresh(product_to_return)
    await emit_updates_products(db, store.id)
    return product_to_return

@router.post("/{product_id}/view", status_code=204)
def record_product_view(product: GetProductDep, store: GetStoreDep, db: GetDBDep):
    db.add(models.ProductView(product_id=product.id, store_id=store.id))
    db.commit()
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
    ).order_by(models.Product.priority).offset(skip).limit(limit).all()
    return products

@router.get("/{product_id}", response_model=ProductOut)
def get_product_details(product: GetProductDep):
    # A dependência GetProductDep já faz o trabalho de buscar o produto.
    # Para garantir que as relações estejam carregadas para o ProductOut,
    # o ideal é que a própria dependência já use o `selectinload`.
    return product
# --- ROTA PARA ATUALIZAR PREÇO/PROMOÇÃO EM UMA CATEGORIA ---

@router.patch(
    "/{product_id}/categories/{category_id}",
    response_model=ProductCategoryLinkOut,
    summary="Atualiza o preço/promoção de um produto em uma categoria específica"
)
async def update_product_category_link(
    store: GetStoreDep,
    product_id: int,
    category_id: int,
    update_data: ProductCategoryLinkUpdate,
    db: GetDBDep,
):
    db_link = db.query(models.ProductCategoryLink).join(models.Product).filter(
        models.Product.store_id == store.id,
        models.ProductCategoryLink.product_id == product_id,
        models.ProductCategoryLink.category_id == category_id
    ).first()
    if not db_link:
        raise HTTPException(status_code=404, detail="Este produto não está vinculado a esta categoria.")
    for field, value in update_data.model_dump(exclude_unset=True).items():
        setattr(db_link, field, value)
    db.commit()
    db.refresh(db_link)
    await emit_updates_products(db, store.id)
    return db_link


@router.delete("/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_product(store: GetStoreDep, db: GetDBDep, db_product: GetProductDep):
    old_file_key = db_product.file_key
    db.delete(db_product)
    db.commit()
    # ✅ Adicionada checagem de segurança
    if old_file_key:
        delete_file(old_file_key)
    await emit_updates_products(db, store.id)
    return

# --- ROTA PARA ATUALIZAR PREÇO/PROMOÇÃO EM UMA CATEGORIA --

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

    await emit_updates_products(db, store.id)
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

    await emit_updates_products(db, store.id)

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

    await emit_updates_products(db, store.id)
    return