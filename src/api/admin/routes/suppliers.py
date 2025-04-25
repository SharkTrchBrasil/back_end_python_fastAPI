from fastapi import APIRouter, Form, HTTPException, File, UploadFile

from src.api.admin.schemas.supplier import Supplier
from src.core import models
from src.core.aws import upload_file, delete_file
from src.core.database import GetDBDep
from src.core.dependencies import GetCurrentUserDep, GetStoreDep


router = APIRouter(tags=["Suppliers"], prefix="/stores/{store_id}/suppliers")


@router.post("", response_model=Supplier)
def create_supplier(
    db: GetDBDep,
    store: GetStoreDep,
    name: str = Form(...),
    person_type: str = Form(...),  # Pessoa Física ou Jurídica
    phone: str = Form(...),
    mobile: str = Form(...),
    cnpj: str = Form(...),
    ie: str = Form(...),
    is_icms_contributor: bool = Form(...),
    is_ie_exempt: bool = Form(...),
    address: str = Form(...),
    email: str = Form(...),
    notes: str = Form(...),
    priority: int = Form(...),
):
    db_supplier = models.Supplier(
        name=name,
        person_type=person_type,
        phone=phone,
        mobile=mobile,
        cnpj=cnpj,
        ie=ie,
        is_icms_contributor=is_icms_contributor,
        is_ie_exempt=is_ie_exempt,
        address=address,
        email=email,
        notes=notes,
        priority=priority,
        store_id=store.id,
    )

    db.add(db_supplier)
    db.commit()
    return db_supplier


@router.get("", response_model=list[Supplier])
def get_suppliers(
    db: GetDBDep,
    store: GetStoreDep,
):
    db_suppliers = db.query(models.Supplier).filter(models.Supplier.store_id == store.id).all()
    return db_suppliers


@router.get("/{supplier_id}", response_model=Supplier)
def get_supplier(
    db: GetDBDep,
    store: GetStoreDep,
    supplier_id: int,
):
    db_supplier = db.query(models.Supplier).filter(models.Supplier.id == supplier_id, models.Supplier.store_id == store.id).first()
    if not db_supplier:
        raise HTTPException(status_code=404, detail="Supplier not found")
    return db_supplier


@router.patch("/{supplier_id}", response_model=Supplier)
def patch_supplier(
    db: GetDBDep,
    store: GetStoreDep,
    supplier_id: int,
    name: str | None = Form(None),
    person_type: str | None = Form(None),
    phone: str | None = Form(None),
    mobile: str | None = Form(None),
    cnpj: str | None = Form(None),
    ie: str | None = Form(None),
    is_icms_contributor: bool | None = Form(None),
    is_ie_exempt: bool | None = Form(None),
    address: str | None = Form(None),
    email: str | None = Form(None),
    notes: str | None = Form(None),
    priority: int | None = Form(None),
    image: UploadFile | None = File(None)
):
    db_supplier = db.query(models.Supplier).filter(models.Supplier.id == supplier_id, models.Supplier.store_id == store.id).first()
    if not db_supplier:
        raise HTTPException(status_code=404, detail="Supplier not found")

    file_key_to_delete = None

    if name:
        db_supplier.name = name
    if person_type:
        db_supplier.person_type = person_type
    if phone:
        db_supplier.phone = phone
    if mobile:
        db_supplier.mobile = mobile
    if cnpj:
        db_supplier.cnpj = cnpj
    if ie:
        db_supplier.ie = ie
    if is_icms_contributor is not None:
        db_supplier.is_icms_contributor = is_icms_contributor
    if is_ie_exempt is not None:
        db_supplier.is_ie_exempt = is_ie_exempt
    if address:
        db_supplier.address = address
    if email:
        db_supplier.email = email
    if notes:
        db_supplier.notes = notes
    if priority:
        db_supplier.priority = priority
    if image:
        file_key_to_delete = db_supplier.file_key
        new_file_key = upload_file(image)
        db_supplier.file_key = new_file_key

    db.commit()

    if file_key_to_delete:
        delete_file(file_key_to_delete)

    return db_supplier
