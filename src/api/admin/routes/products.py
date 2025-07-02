import asyncio
from typing import Optional, List

from fastapi import APIRouter, Form

from src.api.admin.schemas.variant_selection import VariantSelectionPayload
from src.api.app.routes.realtime import refresh_product_list
from src.api.shared_schemas.product import ProductOut
from src.core import models
from src.core.aws import upload_file, delete_file
from src.core.database import GetDBDep
from src.core.dependencies import GetStoreDep, GetProductDep

router = APIRouter(prefix="/stores/{store_id}/products", tags=["Products"])


from fastapi import UploadFile, File, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload


@router.post("", response_model=ProductOut)
async def create_product(
    db: GetDBDep,
    store: GetStoreDep,

    name: str = Form(...),
    description: str | None = Form(None),
    base_price: int = Form(...),
    cost_price: int | None = Form(None),
    promotion_price: int | None = Form(None),
    featured: bool = Form(False),
    activate_promotion: bool = Form(False),
    available: bool = Form(True),
    category_id: int | None = Form(None),
    ean: str | None = Form(None),

    stock_quantity: int | None = Form(None),
    control_stock: bool = Form(False),
    min_stock: int | None = Form(None),
    max_stock: int | None = Form(None),
    unit: str | None = Form(None),
    variant_ids: Optional[List[int]] = Form(None),
    image: UploadFile | None = File(None),
):
    category = db.query(models.Category).filter(
        models.Category.id == category_id,
        models.Category.store_id == store.id
    ).first()

    if not category:
        raise HTTPException(status_code=400, detail="Category not found")


    file_key = None
    if image is not None:
        file_key = upload_file(image)

    new_product = models.Product(
        name=name,
        description=description,
        base_price=base_price,
        cost_price=cost_price,
        promotion_price=promotion_price,
        featured=featured,
        activate_promotion=activate_promotion,
        available=available,
        category_id=category_id,
        store_id=store.id,
        ean=ean,

        stock_quantity=stock_quantity,
        control_stock=control_stock,
        min_stock=min_stock,
        max_stock=max_stock,
        unit=unit,

        file_key=file_key,
    )

    if variant_ids:
        variants = db.query(models.Variant).filter(
            models.Variant.id.in_(variant_ids),
            models.Variant.store_id == store.id  # garante que são da loja certa
        ).all()
        new_product.variants = variants
    else:
        new_product.variants = []  # <- Isso evita o erro de validação

    db.add(new_product)
    db.commit()
    db.refresh(new_product)

    await asyncio.create_task(refresh_product_list(db, store.id))

    return new_product















# @router.post("", response_model=ProductOut)
# def create_product(
#     db: Session = Depends(GetDBDep),
#     store = Depends(GetStoreDep),
#     image: UploadFile = File(...),
#     variant_ids: Optional[List[int]] = Form([]),
#     product_data: ProductCreate = Depends(ProductCreate),
# ):
#     # Valida categoria
#     category = db.query(models.Category).filter(
#         models.Category.id == product_data.category_id,
#         models.Category.store_id == store.id
#     ).first()
#     if not category:
#         raise HTTPException(status_code=400, detail="Category not found")
#
#     # Upload da imagem
#     file_key = upload_file(image)
#
#     # Cria produto com dados do formulário e a chave da imagem
#     db_product = models.Product(
#         **product_data.model_dump(exclude_unset=True),
#         store_id=store.id,
#         file_key=file_key
#     )
#
#     # Associa variantes ao produto (se houver)
#     if variant_ids:
#         variants = db.query(models.Variant).filter(models.Variant.id.in_(variant_ids)).all()
#         db_product.variants = variants
#
#     db.add(db_product)
#     db.commit()
#     db.refresh(db_product)
#     return db_product


@router.get("", response_model=list[ProductOut])
def get_products(db: GetDBDep, store: GetStoreDep, skip: int = 0, limit: int = 50):
    query = db.query(models.Product).filter(models.Product.store_id == store.id).options(
        joinedload(models.Product.category),
        joinedload(models.Product.variant_links)
        .joinedload(models.ProductVariantProduct.variant)
        .joinedload(models.Variant.options)
    )
    products = query.offset(skip).limit(limit).all()
    for product in products:
        product.variants = [link.variant for link in product.variant_links]
    return products


@router.get("/{product_id}", response_model=ProductOut)
def get_product(
        product: GetProductDep
):
    return product


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
    variant_ids: Optional[List[int]] = Form(None),
    image: UploadFile | None = File(None),
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

    if category_id is not None:
        category = db.query(models.Category).filter(
            models.Category.id == category_id,
            models.Category.store_id == store.id
        ).first()
        if not category:
            raise HTTPException(status_code=400, detail="Category not found")
        db_product.category_id = category_id

    if variant_ids is not None:
        variants = db.query(models.Variant).filter(
            models.Variant.id.in_(variant_ids),
            models.Variant.store_id == store.id
        ).all()
        db_product.variants = variants

    if image:
        old_file_key = db_product.file_key
        new_file_key = upload_file(image)
        db_product.file_key = new_file_key
        db.commit()
        delete_file(old_file_key)
    else:
        db.commit()

    db.refresh(db_product)
    await asyncio.create_task(refresh_product_list(db, store.id))
    return db_product



@router.get("/stores/{store_id}/products/{product_id}/variants", response_model=List[int])

def list_variants_for_product(store_id: int, product_id: int, db: GetDBDep):
    links = db.query(models.ProductVariantProduct).filter_by(product_id=product_id).all()
    variant_ids = [link.variant_id for link in links]
    return variant_ids




@router.post("/stores/{store_id}/products/{product_id}/variants", status_code=204)
def save_variants_for_product(
    store_id: int,
    product_id: int,
    payload: VariantSelectionPayload,
    db: GetDBDep
):
    # Remove os vínculos antigos
    db.query(models.ProductVariantProduct).filter_by(product_id=product_id).delete()

    # Adiciona os vínculos novos
    for variant_id in payload.variant_ids:
        db.add(models.ProductVariantProduct(product_id=product_id, variant_id=variant_id))

    db.commit()















@router.delete("/{product_id}", status_code=204)
async def delete_product(product_id: int,  store: GetStoreDep, db: GetDBDep, db_product: GetProductDep):
    old_file_key = db_product.file_key
    db.delete(db_product)
    db.commit()
    delete_file(old_file_key)
    await asyncio.create_task(refresh_product_list(db, store.id))
    return

# @router.patch("/{product_id}", response_model=Product)
# def patch_product(
#         db: GetDBDep,
#         db_product: GetProductDep,
#         name: str | None = Form(None),
#         description: str | None = Form(None),
#         base_price: int | None = Form(None),
#         cost_price: int | None = Form(None),
#         available: bool | None = Form(None),
#         category_id: int | None = Form(None),
#
#         promotion_price: int | None = Form(None),
#
#         featured: bool | None = Form(None),
#
#
#         activate_promotion: bool | None = Form(None),
#
#
#
#
#         ean: str | None = Form(None),
#         code: str | None = Form(None),
#         auto_code: bool | None = Form(None),
#         extra_code: str | None = Form(None),
#         stock_quantity: int | None = Form(None),
#         control_stock: bool | None = Form(None),
#         min_stock: int | None = Form(None),
#         max_stock: int | None = Form(None),
#         unit: str | None = Form(None),
#         allow_fraction: bool | None = Form(None),
#         observation: str | None = Form(None),
#         location: str | None = Form(None),
#         image: UploadFile | None = File(None),
# ):
#     if name: db_product.name = name
#     if description: db_product.description = description
#     if base_price is not None: db_product.base_price = base_price
#     if cost_price is not None: db_product.cost_price = cost_price
#     if available is not None: db_product.available = available
#
#     if promotion_price is not None: db_product.promotion_price = promotion_price
#     if activate_promotion is not None: db_product.activate_promotion = activate_promotion
#     if featured is not None: db_product.featured = featured
#
#     if category_id:
#         category = db.query(models.Category).filter(
#             models.Category.id == category_id,
#             models.Category.store_id == db_product.store_id
#         ).first()
#
#         if not category:
#             raise HTTPException(status_code=400, detail="Category not found")
#         db_product.category_id = category_id
#
#
#
#     if ean is not None:
#         db_product.ean = ean
#     if code is not None:
#         db_product.code = code
#     if auto_code is not None:
#         db_product.auto_code = auto_code
#     if extra_code is not None:
#         db_product.extra_code = extra_code
#     if stock_quantity is not None:
#         db_product.stock_quantity = stock_quantity
#     if control_stock is not None:
#         db_product.control_stock = control_stock
#     if min_stock is not None:
#         db_product.min_stock = min_stock
#     if max_stock is not None:
#         db_product.max_stock = max_stock
#     if unit is not None:
#         db_product.unit = unit
#     if allow_fraction is not None:
#         db_product.allow_fraction = allow_fraction
#     if observation is not None:
#         db_product.observation = observation
#     if location is not None:
#         db_product.location = location
#
#     file_to_delete = None
#     if image:
#         file_to_delete = db_product.file_key
#         file_key = upload_file(image)
#         db_product.file_key = file_key
#
#     db.commit()
#
#     if file_to_delete:
#         delete_file(file_to_delete)
#
#     return db_product