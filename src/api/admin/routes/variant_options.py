# src/api/admin/routes/variant_options.py

from fastapi import APIRouter, HTTPException, Form, File, UploadFile, status, Request
from pydantic import ValidationError

from src.api.app.socketio.socketio_emitters import emit_products_updated
from src.api.schemas.products.variant_option import (
    VariantOptionCreate, VariantOptionUpdate, VariantOption as VariantOptionOut
)
from src.core import models
from src.core.aws import delete_file, upload_single_file
from src.core.database import GetDBDep
from src.core.dependencies import (
    GetVariantDep, GetVariantOptionDep, GetCurrentUserDep, GetAuditLoggerDep
)
from src.core.utils.enums import AuditAction, AuditEntityType

router = APIRouter(
    tags=["Variant Options"],
    prefix='/stores/{store_id}/variants/{variant_id}/options'
)


# ═══════════════════════════════════════════════════════════════════════════════
# 🔥 PONTO VITAL 1: CRIAR OPÇÃO DE COMPLEMENTO
# ═══════════════════════════════════════════════════════════════════════════════

@router.post("", response_model=VariantOptionOut, status_code=status.HTTP_201_CREATED)
async def create_product_variant_option(
        request: Request,
        db: GetDBDep,
        variant: GetVariantDep,
        user: GetCurrentUserDep,  # ✅ ADICIONAR
        audit: GetAuditLoggerDep,  # ✅ ADICIONAR
        payload_str: str = Form(..., alias="payload"),
        image: UploadFile | None = File(None),

):
    """
    ✅ Cria uma nova opção de complemento com auditoria

    - Registra quem criou
    - Rastreia preço inicial
    - Monitora upload de imagem
    """

    try:
        payload = VariantOptionCreate.model_validate_json(payload_str)
    except ValidationError as e:
        # ✅ LOG DE ERRO DE VALIDAÇÃO
        audit.log_failed_action(
            action=AuditAction.CREATE_VARIANT,
            entity_type=AuditEntityType.VARIANT,
            error=f"Erro de validação ao criar opção: {str(e)}"
        )
        db.commit()

        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Erro de validação: {e}"
        )

    # Faz o upload da imagem, se houver
    file_key = upload_single_file(image) if image else None

    db_option = models.VariantOption(
        **payload.model_dump(),
        variant_id=variant.id,
        store_id=variant.store_id,
        file_key=file_key
    )

    db.add(db_option)
    db.flush()

    # ✅ LOG DE CRIAÇÃO BEM-SUCEDIDA
    audit.log(
        action=AuditAction.CREATE_VARIANT,  # Usa CREATE_VARIANT pois opção faz parte do grupo
        entity_type=AuditEntityType.VARIANT,
        entity_id=variant.id,
        changes={
            "variant_name": variant.name,
            "option_id": db_option.id,
            "option_name": db_option.resolved_name,
            "price": float(db_option.resolved_price) / 100,
            "linked_product_id": db_option.linked_product_id,
            "has_image": bool(file_key)
        },
        description=f"Opção '{db_option.resolved_name}' criada no grupo '{variant.name}'"
    )

    db.commit()
    db.refresh(db_option)

    await emit_products_updated(db, db_option.store_id)
    return db_option


# ═══════════════════════════════════════════════════════════════════════════════
# ROTA DE LEITURA - SEM AUDITORIA
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/{option_id}", response_model=VariantOptionOut)
def get_product_variant_option(option: GetVariantOptionDep):
    """Busca uma opção específica."""
    return option


# ═══════════════════════════════════════════════════════════════════════════════
# 🔥 PONTO VITAL 2: ATUALIZAR OPÇÃO DE COMPLEMENTO
# ═══════════════════════════════════════════════════════════════════════════════

@router.patch("/{option_id}", response_model=VariantOptionOut)
async def patch_product_variant_option(
        request: Request,
        db: GetDBDep,
        option: GetVariantOptionDep,
        user: GetCurrentUserDep,
        audit: GetAuditLoggerDep,
        payload_str: str = Form(..., alias="payload"),
        image: UploadFile | None = File(None),

):
    """
    ✅ Atualiza uma opção de complemento com auditoria de mudanças

    - Rastreia alterações de preço (CRÍTICO!)
    - Monitora mudanças de nome
    - Registra upload/troca de imagem
    """

    try:
        update_data = VariantOptionUpdate.model_validate_json(payload_str)
    except ValidationError as e:
        # ✅ LOG DE ERRO DE VALIDAÇÃO
        audit.log_failed_action(
            action=AuditAction.UPDATE_VARIANT,
            entity_type=AuditEntityType.VARIANT,
            error=f"Erro de validação ao atualizar opção ID {option.id}: {str(e)}"
        )
        db.commit()

        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Erro de validação: {e}"
        )

    # ✅ CAPTURA ESTADO ANTERIOR
    old_values = {
        "name": option.resolved_name,
        "price": float(option.resolved_price) / 100,
        "linked_product_id": option.linked_product_id,
        "file_key": option.file_key
    }

    # Se uma nova imagem foi enviada, atualiza e apaga a antiga
    image_action = None
    if image:
        old_file_key = option.file_key
        option.file_key = upload_single_file(image)

        if old_file_key:
            delete_file(old_file_key)
            image_action = "replaced"
        else:
            image_action = "added"

    # Aplica atualizações
    changes = {}
    for field, value in update_data.model_dump(exclude_unset=True).items():
        old_val = getattr(option, field)
        if old_val != value:
            changes[field] = {
                "from": old_val,
                "to": value
            }
        setattr(option, field, value)

    if image_action:
        changes["image_action"] = image_action

    # ✅ DETECTA MUDANÇA DE PREÇO (CRÍTICO!)
    price_changed = False
    if option.resolved_price != (old_values["price"] * 100):
        price_changed = True
        changes["price_critical"] = {
            "from": old_values["price"],
            "to": float(option.resolved_price) / 100
        }

    # ✅ LOG DE ATUALIZAÇÃO
    action_type = AuditAction.UPDATE_VARIANT

    audit.log(
        action=action_type,
        entity_type=AuditEntityType.VARIANT,
        entity_id=option.variant_id,
        changes={
            "variant_name": option.variant.name,
            "option_id": option.id,
            "option_name": option.resolved_name,
            "old_values": old_values,
            "changes": changes,
            "price_changed": price_changed
        },
        description=f"Opção '{option.resolved_name}' atualizada {'⚠️ PREÇO ALTERADO' if price_changed else ''}"
    )

    db.commit()
    db.refresh(option)

    await emit_products_updated(db, option.store_id)
    return option


# ═══════════════════════════════════════════════════════════════════════════════
# 🔥 PONTO VITAL 3: DELETAR OPÇÃO DE COMPLEMENTO
# ═══════════════════════════════════════════════════════════════════════════════

@router.delete("/{option_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_product_variant_option(
        request: Request,
        db: GetDBDep,
        option: GetVariantOptionDep,
        user: GetCurrentUserDep,  # ✅ ADICIONAR
        audit: GetAuditLoggerDep,  # ✅ ADICIONAR
):
    """
    ✅ Deleta uma opção de complemento com auditoria

    ⚠️ ATENÇÃO: Pode afetar pedidos que usam esta opção
    """

    store_id = option.store_id
    file_key_to_delete = option.file_key

    # ✅ CAPTURA DADOS ANTES DE DELETAR
    option_data = {
        "option_id": option.id,
        "name": option.resolved_name,
        "price": float(option.resolved_price) / 100,
        "linked_product_id": option.linked_product_id,
        "variant_id": option.variant_id,
        "variant_name": option.variant.name,
        "had_image": bool(file_key_to_delete)
    }

    # ✅ LOG DE DELEÇÃO
    audit.log(
        action=AuditAction.DELETE_VARIANT,
        entity_type=AuditEntityType.VARIANT,
        entity_id=option.variant_id,
        changes={
            "deleted_by": user.name,
            "option_data": option_data
        },
        description=f"⚠️ Opção '{option.resolved_name}' DELETADA do grupo '{option.variant.name}'"
    )

    db.delete(option)
    db.commit()

    # Apaga o arquivo do storage (S3) depois de deletar do banco
    if file_key_to_delete:
        delete_file(file_key_to_delete)

    await emit_products_updated(db, store_id)