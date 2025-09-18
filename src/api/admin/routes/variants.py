from fastapi import APIRouter
from sqlalchemy.orm import joinedload

from src.api.app.socketio.socketio_emitters import emit_products_updated
from src.api.crud import crud_variant
from src.api.schemas.products.variant import VariantCreate, Variant, VariantUpdate
from src.api.schemas.products.variant_selection import VariantBulkUpdateStatusPayload, VariantSelectionPayload
from src.core import models
from src.core.database import GetDBDep
from src.core.dependencies import GetVariantDep, GetStoreDep



router = APIRouter(tags=["Variants"], prefix="/stores/{store_id}/variants")

@router.post("", response_model=Variant)
async def create_product_variant(
        db: GetDBDep,
        store: GetStoreDep,
        variant: VariantCreate,
):
    # ✅ PASSO 2: Substitua a lógica antiga...
    # ----------------------------------------------------
    # LÓGICA ANTIGA (REMOVIDA):
    # db_variant = models.Variant(
    #     **variant.model_dump(),
    #     store_id=store.id,
    # )
    # db.add(db_variant)
    # db.commit()
    # ----------------------------------------------------

    # ... Pela chamada à nova função do CRUD.
    db_variant = crud_variant.create_variant(
        db=db,
        store_id=store.id,
        variant_data=variant
    )
    # ----------------------------------------------------

    await emit_products_updated(db, db_variant.store_id)
    return db_variant


@router.get("/{variant_id}", response_model=Variant)
def get_product_variant(
    variant: GetVariantDep
):
    return variant

@router.patch("/{variant_id}", response_model=Variant)
async def patch_product_variant(
    db: GetDBDep,
    variant: GetVariantDep,
    store: GetStoreDep,
    variant_update: VariantUpdate,
):
    for field, value in variant_update.model_dump(exclude_unset=True).items():
        setattr(variant, field, value)

    db.commit()
    await emit_products_updated(db, variant.store_id)
    return variant



@router.get("", response_model=list[Variant])
def list_variants(store_id: int, db: GetDBDep, store: GetStoreDep):
    variants = (
        db.query(models.Variant)
        .options(joinedload(models.Variant.options))  # <-- carrega as opções junto
        .filter(models.Variant.store_id == store.id)
        .all()
    )
    return variants


@router.delete("/{variant_id}", status_code=204)
async def delete_product_variant(
    db: GetDBDep,
    store: GetStoreDep,
    variant: GetVariantDep,
):
    db.delete(variant)
    db.commit()
    await emit_products_updated(db, variant.store_id)

    return None  # necessário com status 204




# ... (suas importações e rotas anteriores)

# ===================================================================
# ROTAS DE AÇÃO EM MASSA - CORRIGIDAS
# ===================================================================

@router.post("/bulk-update-status", status_code=200)
async def bulk_update_links_status( # Nome da função atualizado para clareza
        db: GetDBDep,
        store: GetStoreDep,
        payload: VariantBulkUpdateStatusPayload,
):
    """
    Ativa ou pausa TODOS OS VÍNCULOS de uma lista de grupos de complementos.
    """
    if not payload.variant_ids:
        return {"message": "Nenhum grupo selecionado para atualizar."}

    # ✅ CORREÇÃO: A query agora mira em `ProductVariantLink`
    query = (
        db.query(models.ProductVariantLink)
        # Fazemos um JOIN com Variant para garantir que os vínculos pertencem à loja correta
        .join(models.Variant, models.Variant.id == models.ProductVariantLink.variant_id)
        .filter(
            models.Variant.store_id == store.id,
            models.ProductVariantLink.variant_id.in_(payload.variant_ids)
        )
    )

    # ✅ CORREÇÃO: A atualização agora acontece no campo `available` da tabela de VÍNCULO.
    # Assumindo que seu modelo ProductVariantLink tenha o campo 'available'.
    updated_count = query.update(
        {models.ProductVariantLink.available: payload.is_available},
        synchronize_session=False
    )

    db.commit()
    await emit_products_updated(db, store.id)

    status_text = "ativados" if payload.is_available else "pausados"
    # ✅ CORREÇÃO: Mensagem de resposta reflete a ação correta
    return {"message": f"{updated_count} vínculos de produtos foram {status_text}."}


@router.post("/bulk-unlink", status_code=200) # Rota renomeada para clareza
async def bulk_unlink_variants( # Função renomeada para clareza
        db: GetDBDep,
        store: GetStoreDep,
        payload: VariantSelectionPayload,
):
    """
    Deleta TODOS OS VÍNCULOS de uma lista de grupos de complementos.
    O grupo (Variant) em si não é deletado.
    """
    if not payload.variant_ids:
        return {"message": "Nenhum grupo selecionado para desvincular."}

    # ✅ CORREÇÃO: A query agora mira em `ProductVariantLink`
    query = (
        db.query(models.ProductVariantLink)
        # Novamente, JOIN para garantir a segurança a nível de loja
        .join(models.Variant, models.Variant.id == models.ProductVariantLink.variant_id)
        .filter(
            models.Variant.store_id == store.id,
            models.ProductVariantLink.variant_id.in_(payload.variant_ids)
        )
    )

    # ✅ CORREÇÃO: A deleção agora acontece na tabela de VÍNCULOS
    deleted_count = query.delete(synchronize_session=False)

    db.commit()
    await emit_products_updated(db, store.id)

    # ✅ CORREÇÃO: Mensagem de resposta reflete a ação correta
    return {"message": f"{deleted_count} vínculos de produtos foram removidos."}

