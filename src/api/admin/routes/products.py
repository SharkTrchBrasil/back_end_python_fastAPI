import asyncio
from collections import defaultdict
from typing import Optional, List

from pydantic import TypeAdapter

from fastapi import APIRouter, Form
from starlette.responses import JSONResponse

from src.api.admin.schemas.variant_selection import VariantSelectionPayload
from src.api.admin.socketio.emitters import admin_emit_products_updated
from src.api.app.events.socketio_emitters import emit_products_updated

from src.api.shared_schemas.product import ProductOut
from src.core import models
from src.core.aws import upload_file, delete_file
from src.core.database import GetDBDep
from src.core.dependencies import GetStoreDep, GetProductDep

router = APIRouter(prefix="/stores/{store_id}/products", tags=["Products"])


from fastapi import UploadFile, File, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload, selectinload


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
        sold_count=0,

        file_key=file_key,
    )

    db.add(new_product)
    db.commit()
    db.refresh(new_product)

    await asyncio.create_task(emit_products_updated(db, store.id))
    # Este evento atualiza todos os painéis de admin conectados àquela loja
    await admin_emit_products_updated(db, store.id)
    return new_product









@router.get("/minimal", response_model=list[dict])
def get_minimal_products(store_id: int, db: GetDBDep):
    products = db.query(models.Product).filter(models.Product.store_id == store_id).all()
    return [{"id": p.id, "name": p.name} for p in products]


# --- Rota de Listagem (Corrigida) ---
@router.get("", response_model=List[ProductOut])
def get_products(db: GetDBDep, store: GetStoreDep, skip: int = 0, limit: int = 100):
    # ✅ CONSULTA CORRIGIDA para usar a estrutura final e carregar tudo eficientemente
    products = db.query(models.Product).filter(models.Product.store_id == store.id).options(
        selectinload(models.Product.category),
        selectinload(models.Product.variant_links)  # Product -> ProductVariantLink (A Regra)
        .selectinload(models.ProductVariantLink.variant)  # -> Variant (O Template)
        .selectinload(models.Variant.options)  # -> VariantOption (O Item)
        .selectinload(models.VariantOption.linked_product)  # -> Product (Cross-sell)
    ).offset(skip).limit(limit).all()

    # ✅ Não é mais necessário o "product.variants = ...". O schema Pydantic cuida disso.
    return products


# --- Rota de Detalhe (Corrigida) ---
@router.get("/{product_id}", response_model=ProductOut)
def get_product_details(product: GetProductDep, db: GetDBDep):
    # Para garantir que a resposta tenha todos os dados, fazemos a consulta completa aqui
    # ao invés de depender da consulta simples da dependência.
    product_with_details = db.query(models.Product).options(
        selectinload(models.Product.category),
        selectinload(models.Product.variant_links)
        .selectinload(models.ProductVariantLink.variant)
        .selectinload(models.Variant.options)
        .selectinload(models.VariantOption.linked_product)
    ).filter(models.Product.id == product.id).first()

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



@router.get("/variants/{variant_id}/products", response_model=List[int])
async def list_products_linked_to_variant(store_id: int, variant_id: int, db: GetDBDep):
    links = db.query(models.ProductVariantProduct).filter_by(variant_id=variant_id).all()
    product_ids = [link.product_id for link in links]
    return product_ids




@router.post("/{product_id}/variants", status_code=204)
async def save_variants_for_product(
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
    await asyncio.create_task(emit_products_updated(db, store_id))




@router.delete("/{product_id}", status_code=204)
async def delete_product(product_id: int,  store: GetStoreDep, db: GetDBDep, db_product: GetProductDep):
    old_file_key = db_product.file_key
    db.delete(db_product)
    db.commit()
    delete_file(old_file_key)
    await asyncio.create_task(emit_products_updated(db, store.id))
    return
