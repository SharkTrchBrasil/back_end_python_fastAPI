from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from sqlalchemy.orm import joinedload

from src.api.admin.schemas.product import Product
from src.core import models
from src.core.aws import upload_file, delete_file
from src.core.database import GetDBDep
from src.core.dependencies import GetStoreDep, GetProductDep

router = APIRouter(prefix="/stores/{store_id}/products", tags=["Products"])


@router.post("", response_model=Product)
def create_product(
        db: GetDBDep,
        store: GetStoreDep,
        image: UploadFile = File(...),
        name: str = Form(...),
        description: str = Form(...),
        base_price: int = Form(...),
        cost_price: int = Form(0),
        available: bool = Form(...),
        category_id: int = Form(...),
        supplier_id: int = Form(...),

        ean: str = Form(""),
        code: str = Form(""),
        auto_code: bool = Form(True),
        extra_code: str = Form(""),
        stock_quantity: int = Form(0),
        control_stock: bool = Form(False),
        min_stock: int = Form(0),
        max_stock: int = Form(0),
        unit: str = Form(""),
        allow_fraction: bool = Form(False),
        observation: str = Form(""),
        location: str = Form(""),
):
    category = db.query(models.Category).filter(
        models.Category.id == category_id,
        models.Category.store_id == store.id
    ).first()

    if not category:
        raise HTTPException(status_code=400, detail="Category not found")


    supplier = db.query(models.Supplier).filter(
        models.Supplier.id == supplier_id,
        models.Supplier.store_id == store.id
    ).first()

    if not supplier:
        raise HTTPException(status_code=400, detail="Supplier not found")

    file_key = upload_file(image)
    db_product = models.Product(
        name=name,
        description=description,
        base_price=base_price,
        cost_price=cost_price,
        available=available,
        store_id=store.id,
        category_id=category_id,
        supplier_id=supplier_id,
        file_key=file_key,
        ean=ean,
        code=code,
        auto_code=auto_code,
        extra_code=extra_code,
        stock_quantity=stock_quantity,
        control_stock=control_stock,
        min_stock=min_stock,
        max_stock=max_stock,
        unit=unit,
        allow_fraction=allow_fraction,
        observation=observation,
        location=location
    )
    db.add(db_product)
    db.commit()
    return db_product


@router.get("", response_model=list[Product])
def get_products(
        db: GetDBDep,
        store: GetStoreDep,
):
    db_products = db.query(models.Product).filter(models.Product.store_id == store.id).options(
        joinedload(models.Product.category),
        joinedload(models.Product.variants).joinedload(models.ProductVariant.options)
    ).all()
    return db_products


@router.get("/{product_id}", response_model=Product)
def get_product(
        product: GetProductDep
):
    return product

@router.patch("/{product_id}", response_model=Product)
def patch_product(
        db: GetDBDep,
        db_product: GetProductDep,
        name: str | None = Form(None),
        description: str | None = Form(None),
        base_price: int | None = Form(None),
        cost_price: int | None = Form(None),
        available: bool | None = Form(None),
        category_id: int | None = Form(None),
        supplier_id: int | None = Form(None),
        ean: str | None = Form(None),
        code: str | None = Form(None),
        auto_code: bool | None = Form(None),
        extra_code: str | None = Form(None),
        stock_quantity: int | None = Form(None),
        control_stock: bool | None = Form(None),
        min_stock: int | None = Form(None),
        max_stock: int | None = Form(None),
        unit: str | None = Form(None),
        allow_fraction: bool | None = Form(None),
        observation: str | None = Form(None),
        location: str | None = Form(None),
        image: UploadFile | None = File(None),
):
    if name: db_product.name = name
    if description: db_product.description = description
    if base_price is not None: db_product.base_price = base_price
    if cost_price is not None: db_product.cost_price = cost_price
    if available is not None: db_product.available = available
    if category_id:
        category = db.query(models.Category).filter(
            models.Category.id == category_id,
            models.Category.store_id == db_product.store_id
        ).first()

        if not category:
            raise HTTPException(status_code=400, detail="Category not found")
        db_product.category_id = category_id

    if supplier_id:
        supplier = db.query(models.Supplier).filter(
            models.Supplier.id == supplier_id,
            models.Supplier.store_id == db_product.store_id
        ).first()

        if not supplier:
            raise HTTPException(status_code=400, detail="Supplier not found")
        db_product.supplier_id = supplier.id

    if ean is not None:
        db_product.ean = ean
    if code is not None:
        db_product.code = code
    if auto_code is not None:
        db_product.auto_code = auto_code
    if extra_code is not None:
        db_product.extra_code = extra_code
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
    if allow_fraction is not None:
        db_product.allow_fraction = allow_fraction
    if observation is not None:
        db_product.observation = observation
    if location is not None:
        db_product.location = location

    file_to_delete = None
    if image:
        file_to_delete = db_product.file_key
        file_key = upload_file(image)
        db_product.file_key = file_key

    db.commit()

    if file_to_delete:
        delete_file(file_to_delete)

    return db_product