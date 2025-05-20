from fastapi import APIRouter


from src.api.admin.schemas.product import Product, ProductCreate, ProductUpdate

from src.core import models
from src.core.aws import upload_file, delete_file
from src.core.database import GetDBDep
from src.core.dependencies import GetStoreDep, GetProductDep


router = APIRouter(prefix="/stores/{store_id}/products", tags=["Products"])


from fastapi import UploadFile, File, Depends, HTTPException
from sqlalchemy.orm import Session

@router.post("", response_model=ProductCreate)
async def create_product(
    db: Session = Depends(GetDBDep),
    store = Depends(GetStoreDep),
    image: UploadFile = File(...),
    product_data: ProductCreate = Depends(),
):

    # Validar categoria
    category = db.query(models.Category).filter(
        models.Category.id == product_data.category_id,
        models.Category.store_id == store.id
    ).first()
    if not category:
        raise HTTPException(status_code=400, detail="Category not found")

    # Upload da imagem
    file_key = upload_file(image)

    # Criar o produto
    db_product = models.Product(
        name=product_data.name,
        description=product_data.description,
        base_price=product_data.base_price,
        cost_price=product_data.cost_price,
        available=product_data.available,
        store_id=store.id,
        category_id=product_data.category_id,
        file_key=file_key,
        ean=product_data.ean,
        code=product_data.code,
        auto_code=product_data.auto_code,
        extra_code=product_data.extra_code,
        stock_quantity=product_data.stock_quantity,
        control_stock=product_data.control_stock,
        min_stock=product_data.min_stock,
        max_stock=product_data.max_stock,
        unit=product_data.unit,
        allow_fraction=product_data.allow_fraction,
        observation=product_data.observation,
        location=product_data.location
    )


    if product_data.variant_ids:
        variants = db.query(models.ProductVariant).filter(
            models.ProductVariant.id.in_(product_data.variant_ids)
        ).all()
    else:
        variants = []

    db_product.variants = variants

    db.add(db_product)
    db.commit()
    db.refresh(db_product)

    return db_product



# @router.post("", response_model=Product)
# def create_product(
#         db: GetDBDep,
#         store: GetStoreDep,
#         image: UploadFile = File(...),
#         name: str = Form(...),
#         description: str = Form(...),
#         base_price: int = Form(...),
#         cost_price: int = Form(0),
#         available: bool = Form(...),
#         category_id: int = Form(...),
#
#
#         ean: str = Form(""),
#         code: str = Form(""),
#         auto_code: bool = Form(True),
#         extra_code: str = Form(""),
#         stock_quantity: int = Form(0),
#         control_stock: bool = Form(False),
#         min_stock: int = Form(0),
#         max_stock: int = Form(0),
#         unit: str = Form(""),
#         allow_fraction: bool = Form(False),
#         observation: str = Form(""),
#         location: str = Form(""),
# ):
#     category = db.query(models.Category).filter(
#         models.Category.id == category_id,
#         models.Category.store_id == store.id
#     ).first()
#
#     if not category:
#         raise HTTPException(status_code=400, detail="Category not found")
#
#
#
#
#     file_key = upload_file(image)
#     db_product = models.Product(
#         name=name,
#         description=description,
#         base_price=base_price,
#         cost_price=cost_price,
#         available=available,
#         store_id=store.id,
#         category_id=category_id,
#
#         file_key=file_key,
#         ean=ean,
#         code=code,
#         auto_code=auto_code,
#         extra_code=extra_code,
#         stock_quantity=stock_quantity,
#         control_stock=control_stock,
#         min_stock=min_stock,
#         max_stock=max_stock,
#         unit=unit,
#         allow_fraction=allow_fraction,
#         observation=observation,
#         location=location
#     )
#
#
#     db.add(db_product)
#     db.commit()
#     return db_product
#
#


@router.get("", response_model=list[Product])
def get_products(db: GetDBDep, store: GetStoreDep, skip: int = 0, limit: int = 50):
    query = db.query(models.Product).filter(models.Product.store_id == store.id)
    products = query.offset(skip).limit(limit).all()
    return products




# def get_products(
#         db: GetDBDep,
#         store: GetStoreDep,
# ):
#     db_products = db.query(models.Product).filter(models.Product.store_id == store.id).options(
#         joinedload(models.Product.category),
#         joinedload(models.Product.variants).joinedload(models.ProductVariant.options)
#     ).all()
#     return db_products


@router.get("/{product_id}", response_model=Product)
def get_product(
        product: GetProductDep
):
    return product



@router.patch("/{product_id}", response_model=ProductUpdate)
async def patch_product(
    product_id: int,
    db: Session = Depends(GetDBDep),
    db_product = Depends(GetProductDep),
    product_data: ProductUpdate = Depends(),
    image: UploadFile | None = File(None),
):

    # Atualizar os campos presentes
    for field, value in product_data.dict(exclude_unset=True).items():
        setattr(db_product, field, value)

    # Validar categoria se foi alterada
    if product_data.category_id:
        category = db.query(models.Category).filter(
            models.Category.id == product_data.category_id,
            models.Category.store_id == db_product.store_id
        ).first()
        if not category:
            raise HTTPException(status_code=400, detail="Category not found")
        db_product.category_id = product_data.category_id

    # Atualizar variantes se vier
    if product_data.variant_ids is not None:
        variants = db.query(models.ProductVariant).filter(
            models.ProductVariant.id.in_(product_data.variant_ids)
        ).all()
        db_product.variants = variants

    # Upload de nova imagem e deletar a antiga
    if image:
        old_file_key = db_product.file_key
        new_file_key = upload_file(image)
        db_product.file_key = new_file_key
        db.commit()
        delete_file(old_file_key)
    else:
        db.commit()

    db.refresh(db_product)
    return db_product





@router.delete("/{product_id}", status_code=204)
def delete_product(product_id: int, db: Session = Depends(GetDBDep), db_product = Depends(GetProductDep)):
    old_file_key = db_product.file_key
    db.delete(db_product)
    db.commit()
    delete_file(old_file_key)
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