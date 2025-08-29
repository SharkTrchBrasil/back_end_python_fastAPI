from fastapi import APIRouter, HTTPException, status, Depends
from sqlalchemy.orm import Session


# ✅ Importe os seus schemas Pydantic. Use o "Out" para respostas.
from src.api.schemas.product_variant_link import ProductVariantLinkOut, ProductVariantLinkCreate, ProductVariantLinkUpdate

from src.api.admin.socketio.emitters import admin_emit_products_updated
from src.api.app.socketio.socketio_emitters import emit_products_updated
from src.core.database import get_db
from src.core import models
from src.core.models import Product

# ✅ Use um nome mais descritivo para a dependência de banco de dados
GetDBDep = Depends(get_db)

router = APIRouter(
    tags=["Product Variant Links"],
    prefix="/stores/{store_id}/products/{product_id}/variants"
)

# ✅ Função auxiliar para emitir eventos e evitar repetição de código
async def _emit_update_events(db: Session, store_id: int):
    """Emite eventos de atualização para clientes e painéis de admin."""
    await emit_products_updated(db, store_id)
    await admin_emit_products_updated(db, store_id)


@router.post(
    "/{variant_id}",
    response_model=ProductVariantLinkOut, # ✅ Use o schema "Out"
    status_code=status.HTTP_201_CREATED,
    summary="Liga um grupo a um produto com regras"
)
async def link_variant_to_product(
    store_id: int,
    variant_id: int,
    link_data: ProductVariantLinkCreate,
    db:  GetDBDep,
    product: Product # ✅ Usa a dependência
):
    # ✅ VALIDAÇÃO 1: Garante que o grupo de complemento (Variant) existe e pertence à loja.
    variant = db.query(models.Variant).filter_by(id=variant_id, store_id=store_id).first()
    if not variant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Grupo de complemento com ID {variant_id} não encontrado nesta loja."
        )

    # VALIDAÇÃO 2: Verificar se a ligação já existe
    existing_link = db.query(models.ProductVariantLink).filter_by(
        product_id=product.id,
        variant_id=variant_id
    ).first()
    if existing_link:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Este grupo já está ligado a este produto."
        )

    # Criar a nova ligação
    db_link = models.ProductVariantLink(
        **link_data.model_dump(),
        product_id=product.id,
        variant_id=variant_id
    )
    db.add(db_link)
    db.commit()
    db.refresh(db_link)

    await _emit_update_events(db, store_id)
    return db_link


@router.get(
    "",
    response_model=list[ProductVariantLinkOut], # ✅ Use o schema "Out"
    summary="Lista todos os grupos e suas regras para um produto"
)
async def get_links_for_product(
    product: Product # ✅ Usa a dependência
):
    """Retorna a lista de complementos e suas regras aplicadas a este produto específico."""
    return product.variant_links


@router.patch(
    "/{variant_id}",
    response_model=ProductVariantLinkOut, # ✅ Use o schema "Out"
    summary="Atualiza as regras de um grupo em um produto"
)
async def update_link_rules(
    store_id: int,
    variant_id: int,
    update_data: ProductVariantLinkUpdate,
    db: GetDBDep,
    product: Product
):
    """Atualiza as regras (min/max, UI mode, etc) de uma ligação existente."""
    # ✅ Busca o link a partir do produto já validado pela dependência
    db_link = db.query(models.ProductVariantLink).filter_by(
        product_id=product.id,
        variant_id=variant_id
    ).first()
    if not db_link:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ligação não encontrada.")

    for field, value in update_data.model_dump(exclude_unset=True).items():
        setattr(db_link, field, value)

    db.commit()
    db.refresh(db_link)

    # ✅ Emite os eventos após a atualização
    await _emit_update_events(db, store_id)
    return db_link


@router.delete(
    "/{variant_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Desvincula um grupo de um produto"
)
async def unlink_variant_from_product(
    store_id: int,
    variant_id: int,
    db: GetDBDep,
    product: Product
):
    """Remove a ligação entre um produto e um grupo, mas não apaga o template do grupo."""
    # ✅ Busca o link a partir do produto já validado
    db_link = db.query(models.ProductVariantLink).filter_by(
        product_id=product.id,
        variant_id=variant_id
    ).first()
    if not db_link:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ligação não encontrada.")

    db.delete(db_link)
    db.commit()

    # ✅ Emite os eventos após a exclusão
    await _emit_update_events(db, store_id)
    return # Retorno vazio para status 204