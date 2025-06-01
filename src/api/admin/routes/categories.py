from fastapi import APIRouter, Form, HTTPException, File, UploadFile

from src.api.admin.schemas.category import Category
from src.core import models
from src.core.aws import upload_file, get_presigned_url, delete_file
from src.core.database import GetDBDep
from src.core.dependencies import GetCurrentUserDep, GetStoreDep

router = APIRouter(tags=["Categories"], prefix="/stores/{store_id}/categories")


@router.post("", response_model=Category)
def create_category(
    db: GetDBDep,
    store: GetStoreDep,
    name: str = Form(...),
    priority: int = Form(...),
    image: UploadFile = File(...),
    is_active: bool = Form(True)

):
    file_key = upload_file(image)

    db_category = models.Category(name=name, store=store, priority=priority, file_key=file_key, is_active=is_active)

    db.add(db_category)
    db.commit()
    return db_category

@router.get("", response_model=list[Category])
def get_categories(
    db: GetDBDep,
    store: GetStoreDep,
):
    db_categories = db.query(models.Category).filter(models.Category.store_id == store.id).all()
    return db_categories

@router.get("/{category_id}", response_model=Category)
def get_category(
    db: GetDBDep,
    store: GetStoreDep,
    category_id: int,
):
    db_category = db.query(models.Category).filter(models.Category.id == category_id, models.Category.store_id == store.id).first()
    if not db_category:
        raise HTTPException(status_code=404, detail="Category not found")
    return db_category

@router.patch("/{category_id}", response_model=Category)
def patch_category(
    db: GetDBDep,
    store: GetStoreDep,
    category_id: int,
    name: str | None = Form(None),
    priority: int | None = Form(None),
    image: UploadFile | None = File(None),
    is_active: bool | None = Form(True)
):
    db_category = db.query(models.Category).filter(models.Category.id == category_id,
                                                   models.Category.store_id == store.id).first()
    if not db_category:
        raise HTTPException(status_code=404, detail="Category not found")

    file_key_to_delete = None

    if name:
        db_category.name = name
    if name:
        db_category.is_active = is_active
    if priority:
        db_category.priority = priority
    if image:
        file_key_to_delete = db_category.file_key
        new_file_key = upload_file(image)
        db_category.file_key = new_file_key

    db.commit()

    if file_key_to_delete:
        delete_file(file_key_to_delete)

    return db_category


@router.delete("/{category_id}", status_code=204)
def delete_category(
    category_id: int,
    db: GetDBDep,
    store: GetStoreDep,
):
    category = db.query(models.Category).filter(
        models.Category.id == category_id,
        models.Category.store_id == store.id
    ).first()

    if not category:
        raise HTTPException(status_code=404, detail="Category not found")

    db.delete(category)
    db.commit()



