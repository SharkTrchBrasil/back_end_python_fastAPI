from fastapi import APIRouter, HTTPException, Form, File, UploadFile, status
from pydantic import ValidationError

from src.api.app.socketio.socketio_emitters import emit_products_updated
from src.api.schemas.products.variant_option import VariantOptionCreate, VariantOptionUpdate, VariantOption as VariantOptionOut
from src.core import models
from src.core.aws import delete_file, upload_single_file  # ✅ Importe as funções de arquivo
from src.core.database import GetDBDep
from src.core.dependencies import GetVariantDep, GetVariantOptionDep

router = APIRouter(tags=["Variant Options"],
                   prefix='/stores/{store_id}/variants/{variant_id}/options')

@router.post("", response_model=VariantOptionOut, status_code=status.HTTP_201_CREATED)
async def create_product_variant_option(
        db: GetDBDep,
        variant: GetVariantDep,
        # ✅ CORREÇÃO: Recebe os dados como texto e a imagem como arquivo
        payload_str: str = Form(..., alias="payload"),
        image: UploadFile | None = File(None),
):
    try:
        # Valida o texto JSON para criar o objeto Pydantic
        payload = VariantOptionCreate.model_validate_json(payload_str)
    except ValidationError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f"Erro de validação: {e}")

    # Faz o upload da imagem, se houver
    file_key = upload_single_file(image) if image else None

    db_option = models.VariantOption(
        **payload.model_dump(),
        store_id=variant.store_id,
        file_key=file_key # ✅ Salva a chave da imagem no banco
    )

    db.add(db_option)
    db.commit()
    db.refresh(db_option) # ✅ Atualiza o objeto para pegar os dados do banco

    await emit_products_updated(db, db_option.store_id)
    return db_option

@router.get("/{option_id}", response_model=VariantOptionOut)
def get_product_variant_option(
    option: GetVariantOptionDep
):
    return option

@router.patch("/{option_id}", response_model=VariantOptionOut)
async def patch_product_variant_option(
    db: GetDBDep,
    option: GetVariantOptionDep,
    # ✅ CORREÇÃO: Recebe os dados e a imagem da mesma forma que o POST
    payload_str: str = Form(..., alias="payload"),
    image: UploadFile | None = File(None),
):
    try:
        update_data = VariantOptionUpdate.model_validate_json(payload_str)
    except ValidationError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f"Erro de validação: {e}")

    # Se uma nova imagem foi enviada, atualiza e apaga a antiga
    if image:
        old_file_key = option.file_key
        option.file_key = upload_single_file(image)
        if old_file_key:
            delete_file(old_file_key)

    for field, value in update_data.model_dump(exclude_unset=True).items():
        setattr(option, field, value)

    db.commit()
    db.refresh(option)
    await emit_products_updated(db, option.store_id)
    return option

@router.delete("/{option_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_product_variant_option(
    db: GetDBDep,
    option: GetVariantOptionDep,
):
    store_id = option.store_id
    file_key_to_delete = option.file_key # ✅ Guarda a chave do arquivo

    db.delete(option)
    db.commit()

    # ✅ Apaga o arquivo do storage (S3) depois de deletar do banco
    if file_key_to_delete:
        delete_file(file_key_to_delete)

    await emit_products_updated(db, store_id)
    # Não precisa de 'return None'