import asyncio
from typing import Optional, List

from fastapi import APIRouter, Form

from src.api.app.routes.realtime import refresh_product_list
from src.api.shared_schemas.product import ProductOut
from src.core import models
from src.core.aws import upload_file, delete_file
from src.core.database import GetDBDep
from src.core.dependencies import GetStoreDep, GetProductDep

router = APIRouter(prefix="/products", tags=["Products"])


from fastapi import UploadFile, File, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload



@router.get("/{product_id}", response_model=ProductOut)
def get_product(product_id: int, db: GetDBDep):
    product = db.query(models.Product).options(
        joinedload(models.Product.category),
        joinedload(models.Product.variant_links)
        .joinedload(models.ProductVariantProduct.variant)
        .joinedload(models.Variant.options)
    ).filter(models.Product.id == product_id).first()

    if not product:
        raise HTTPException(status_code=404, detail="Produto não encontrado")

    product.variants = [link.variant for link in product.variant_links]
    return product


