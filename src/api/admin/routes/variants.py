# src/api/admin/routes/variants.py

from fastapi import APIRouter, Request, HTTPException
from sqlalchemy.orm import joinedload

from src.api.app.socketio.socketio_emitters import emit_products_updated
from src.api.crud import crud_variant
from src.api.schemas.products.variant import VariantCreate, Variant, VariantUpdate
from src.api.schemas.products.variant_selection import VariantBulkUpdateStatusPayload, VariantSelectionPayload
from src.core import models
from src.core.database import GetDBDep
from src.core.dependencies import GetVariantDep, GetStoreDep, GetCurrentUserDep, GetAuditLoggerDep
from src.core.utils.enums import AuditAction, AuditEntityType

router = APIRouter(tags=["Variants"], prefix="/stores/{store_id}/variants")


# ═══════════════════════════════════════════════════════════════════════════════
# 🔥 PONTO VITAL 1: CRIAR GRUPO DE COMPLEMENTOS
# ═══════════════════════════════════════════════════════════════════════════════

@router.post("", response_model=Variant)
async def create_product_variant(
        request: Request,
        db: GetDBDep,
        store: GetStoreDep,
        variant: VariantCreate,
        user: GetCurrentUserDep,  # ✅ ADICIONAR
        audit: GetAuditLoggerDep,  # ✅ ADICIONAR
):
    """
    ✅ Cria um novo grupo de complementos com auditoria completa

    - Registra quem criou
    - Rastreia opções criadas junto
    - Monitora preços e configurações
    """

    db_variant = crud_variant.create_variant(
        db=db,
        store_id=store.id,
        variant_data=variant
    )

    # ✅ LOG DE CRIAÇÃO BEM-SUCEDIDA
    audit.log(
        action=AuditAction.CREATE_VARIANT,
        entity_type=AuditEntityType.VARIANT,
        entity_id=db_variant.id,
        changes={
            "store_name": store.name,
            "variant_name": db_variant.name,
            "variant_type": db_variant.type,
            "options_count": len(variant.options) if variant.options else 0,
            "options": [
                {
                    "name": opt.name_override or (f"Produto #{opt.linked_product_id}" if opt.linked_product_id else "Opção sem nome"),
                    "price": float(opt.price_override) / 100 if opt.price_override else 0,
                    "linked_product_id": opt.linked_product_id
                }
                for opt in (variant.options or [])
            ]
        },
        description=f"Grupo '{db_variant.name}' criado com {len(variant.options or [])} opções"
    )

    db.commit()

    await emit_products_updated(db, db_variant.store_id)
    return db_variant


# ═══════════════════════════════════════════════════════════════════════════════
# ROTA DE LEITURA - SEM AUDITORIA
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/{variant_id}", response_model=Variant)
def get_product_variant(variant: GetVariantDep):
    """Busca um grupo de complementos específico."""
    return variant


@router.get("", response_model=list[Variant])
def list_variants(store_id: int, db: GetDBDep, store: GetStoreDep):
    """Lista todos os grupos de complementos da loja."""
    variants = (
        db.query(models.Variant)
        .options(joinedload(models.Variant.options))
        .filter(models.Variant.store_id == store.id)
        .all()
    )
    return variants


# ═══════════════════════════════════════════════════════════════════════════════
# 🔥 PONTO VITAL 2: ATUALIZAR GRUPO DE COMPLEMENTOS
# ═══════════════════════════════════════════════════════════════════════════════

@router.patch("/{variant_id}", response_model=Variant)
async def patch_product_variant(
        request: Request,
        db: GetDBDep,
        variant: GetVariantDep,
        store: GetStoreDep,
        variant_update: VariantUpdate,
        user: GetCurrentUserDep,  # ✅ ADICIONAR
        audit: GetAuditLoggerDep,  # ✅ ADICIONAR
):
    """
    ✅ Atualiza um grupo de complementos com auditoria de mudanças

    - Rastreia alterações de nome
    - Monitora mudanças de tipo
    - Registra adição/remoção de opções
    """

    # ✅ CAPTURA ESTADO ANTERIOR
    old_values = {
        "name": variant.name,
        "type": variant.type,
        "options_count": len(variant.options) if variant.options else 0,
        "options": [
            {
                "id": opt.id,
                "name": opt.resolved_name,
                "price": float(opt.resolved_price) / 100
            }
            for opt in (variant.options or [])
        ]
    }

    # Aplica atualizações
    updated_variant = crud_variant.update_variant(
        db=db,
        variant_obj=variant,
        variant_data=variant_update
    )

    # ✅ DETECTA MUDANÇAS
    changes = {}

    if updated_variant.name != old_values["name"]:
        changes["name_changed"] = {
            "from": old_values["name"],
            "to": updated_variant.name
        }

    if updated_variant.type != old_values["type"]:
        changes["type_changed"] = {
            "from": old_values["type"],
            "to": updated_variant.type
        }

    new_options_count = len(updated_variant.options) if updated_variant.options else 0
    if new_options_count != old_values["options_count"]:
        changes["options_count"] = {
            "from": old_values["options_count"],
            "to": new_options_count
        }

    # ✅ LOG DE ATUALIZAÇÃO BEM-SUCEDIDA
    audit.log(
        action=AuditAction.UPDATE_VARIANT,
        entity_type=AuditEntityType.VARIANT,
        entity_id=updated_variant.id,
        changes={
            "store_name": store.name,
            "variant_name": updated_variant.name,
            "old_values": old_values,
            "changes": changes
        },
        description=f"Grupo '{updated_variant.name}' atualizado"
    )

    db.commit()

    await emit_products_updated(db, updated_variant.store_id)
    return updated_variant


# ═══════════════════════════════════════════════════════════════════════════════
# 🔥 PONTO VITAL 3: DELETAR GRUPO DE COMPLEMENTOS (CRÍTICO!)
# ═══════════════════════════════════════════════════════════════════════════════

@router.delete("/{variant_id}", status_code=204)
async def delete_product_variant(
        request: Request,
        db: GetDBDep,
        store: GetStoreDep,
        variant: GetVariantDep,
        user: GetCurrentUserDep,  # ✅ ADICIONAR
        audit: GetAuditLoggerDep,  # ✅ ADICIONAR
):
    """
    ✅ Deleta um grupo de complementos com auditoria completa

    ⚠️ ATENÇÃO: Ação irreversível e de ALTO IMPACTO
    - Pode afetar múltiplos produtos
    - Remove todas as opções do grupo
    - Pode quebrar produtos que dependem dele
    """

    # ✅ CAPTURA DADOS ANTES DE DELETAR (para auditoria forense)
    variant_data = {
        "variant_id": variant.id,
        "name": variant.name,
        "type": variant.type,
        "options": [
            {
                "id": opt.id,
                "name": opt.resolved_name,
                "price": float(opt.resolved_price) / 100,
                "linked_product_id": opt.linked_product_id
            }
            for opt in (variant.options or [])
        ]
    }

    # ✅ VERIFICA SE HÁ PRODUTOS VINCULADOS
    linked_products_count = db.query(models.ProductVariantLink).filter(
        models.ProductVariantLink.variant_id == variant.id
    ).count()

    variant_data["linked_products_count"] = linked_products_count

    # ✅ LOG DE DELEÇÃO (CRÍTICO - REGISTRA TUDO)
    audit.log(
        action=AuditAction.DELETE_VARIANT,
        entity_type=AuditEntityType.VARIANT,
        entity_id=variant.id,
        changes={
            "deleted_by": user.name,
            "store_name": store.name,
            "variant_data": variant_data,
            "impact_warning": f"⚠️ ATENÇÃO: {linked_products_count} produtos estavam vinculados a este grupo"
        },
        description=f"⚠️ Grupo '{variant.name}' DELETADO - {linked_products_count} produtos afetados"
    )

    db.delete(variant)
    db.commit()

    await emit_products_updated(db, variant.store_id)

    return None


# ═══════════════════════════════════════════════════════════════════════════════
# 🔥 PONTO VITAL 4: ATUALIZAR STATUS EM MASSA
# ═══════════════════════════════════════════════════════════════════════════════

@router.post("/bulk-update-status", status_code=200)
async def bulk_update_links_status(
        request: Request,
        db: GetDBDep,
        store: GetStoreDep,
        payload: VariantBulkUpdateStatusPayload,
        user: GetCurrentUserDep,  # ✅ ADICIONAR
        audit: GetAuditLoggerDep,  # ✅ ADICIONAR
):
    """
    ✅ Ativa ou pausa TODOS OS VÍNCULOS de uma lista de grupos em massa
    """

    if not payload.variant_ids:
        return {"message": "Nenhum grupo selecionado para atualizar."}

    # ✅ BUSCA NOMES DOS GRUPOS ANTES DE ATUALIZAR
    variants_info = db.query(models.Variant.id, models.Variant.name).filter(
        models.Variant.id.in_(payload.variant_ids),
        models.Variant.store_id == store.id
    ).all()

    variant_names = {v.id: v.name for v in variants_info}

    # Atualiza os vínculos
    query = (
        db.query(models.ProductVariantLink)
        .join(models.Variant, models.Variant.id == models.ProductVariantLink.variant_id)
        .filter(
            models.Variant.store_id == store.id,
            models.ProductVariantLink.variant_id.in_(payload.variant_ids)
        )
    )

    updated_count = query.update(
        {models.ProductVariantLink.available: payload.is_available},
        synchronize_session=False
    )

    # ✅ LOG BULK DE ATUALIZAÇÃO
    audit.log_bulk(
        action=AuditAction.BULK_UPDATE_VARIANT_STATUS,
        entity_type=AuditEntityType.VARIANT,
        entity_ids=payload.variant_ids,
        changes={
            "variant_names": variant_names,
            "new_status": "ativo" if payload.is_available else "pausado",
            "links_updated": updated_count
        },
        description=f"{updated_count} vínculos de produtos {'ativados' if payload.is_available else 'pausados'}"
    )

    db.commit()
    await emit_products_updated(db, store.id)

    status_text = "ativados" if payload.is_available else "pausados"
    return {"message": f"{updated_count} vínculos de produtos foram {status_text}."}


# ═══════════════════════════════════════════════════════════════════════════════
# 🔥 PONTO VITAL 5: DESVINCULAR EM MASSA
# ═══════════════════════════════════════════════════════════════════════════════

@router.post("/bulk-unlink", status_code=200)
async def bulk_unlink_variants(
        request: Request,
        db: GetDBDep,
        store: GetStoreDep,
        payload: VariantSelectionPayload,
        user: GetCurrentUserDep,  # ✅ ADICIONAR
        audit: GetAuditLoggerDep,  # ✅ ADICIONAR
):
    """
    ✅ Deleta TODOS OS VÍNCULOS de uma lista de grupos em massa

    ⚠️ O grupo (Variant) em si não é deletado, apenas os vínculos
    """

    if not payload.variant_ids:
        return {"message": "Nenhum grupo selecionado para desvincular."}

    # ✅ BUSCA NOMES DOS GRUPOS ANTES DE DESVINCULAR
    variants_info = db.query(models.Variant.id, models.Variant.name).filter(
        models.Variant.id.in_(payload.variant_ids),
        models.Variant.store_id == store.id
    ).all()

    variant_names = {v.id: v.name for v in variants_info}

    # Deleta os vínculos
    query = (
        db.query(models.ProductVariantLink)
        .join(models.Variant, models.Variant.id == models.ProductVariantLink.variant_id)
        .filter(
            models.Variant.store_id == store.id,
            models.ProductVariantLink.variant_id.in_(payload.variant_ids)
        )
    )

    deleted_count = query.delete(synchronize_session=False)

    # ✅ LOG BULK DE DESVINCULAÇÃO
    audit.log_bulk(
        action=AuditAction.BULK_UNLINK_VARIANTS,
        entity_type=AuditEntityType.VARIANT,
        entity_ids=payload.variant_ids,
        changes={
            "variant_names": variant_names,
            "links_deleted": deleted_count
        },
        description=f"{deleted_count} vínculos de produtos removidos"
    )

    db.commit()
    await emit_products_updated(db, store.id)

    return {"message": f"{deleted_count} vínculos de produtos foram removidos."}