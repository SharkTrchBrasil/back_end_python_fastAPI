from fastapi import APIRouter, HTTPException, status

from src.api.admin.socketio.emitters import admin_emit_products_updated
from src.api.app.socketio.socketio_emitters import emit_products_updated
from src.core.database import GetDBDep
from src.core import models
from src.api.schemas import product_variant_link as link_schemas
from src.core.dependencies import GetProductDep  # Supondo que você tenha essas dependências

router = APIRouter(tags=["3. Product Variant Links & Rules"], prefix="/stores/{store_id}/products/{product_id}/variants")

# No seu arquivo de rotas: src/api/routers/product_variant_link.py (ou similar)

@router.post("/{variant_id}", response_model=link_schemas.ProductVariantLink, status_code=status.HTTP_201_CREATED,
             summary="Liga um grupo a um produto com regras ('Copiar')")
async def link_variant_to_product(
        store_id: int,  # ✅ 1. Receba o store_id diretamente da URL
        product: GetProductDep,
        variant_id: int,
        link_data: link_schemas.ProductVariantLinkCreate,
        db: GetDBDep
):

    # Verificar se a ligação já existe
    existing_link = db.query(models.ProductVariantLink).filter_by(product_id=product.id, variant_id=variant_id).first()
    if existing_link:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Este grupo já está ligado a este produto.")

    # Criar a nova ligação com as regras fornecidas
    db_link = models.ProductVariantLink(
        **link_data.model_dump(),
        product_id=product.id,
        variant_id=variant_id
    )
    db.add(db_link)
    db.commit()
    db.refresh(db_link)

    # ✅ 2. Chame os eventos com o store_id correto
    # Este evento provavelmente notifica os apps dos clientes (se aplicável)
    await emit_products_updated(db, store_id)

    # Este evento atualiza todos os painéis de admin conectados àquela loja
    await admin_emit_products_updated(db, store_id)

    return db_link


@router.get("", response_model=list[link_schemas.ProductVariantLink],
            summary="Lista todos os grupos e suas regras para um produto")
def get_links_for_product(product: GetProductDep):
    """Retorna a lista de complementos e suas regras aplicadas a este produto específico."""
    return product.variant_links


@router.patch("/{variant_id}", response_model=link_schemas.ProductVariantLink,
              summary="Atualiza as regras de um grupo em um produto")
def update_link_rules(
        product_id: int,
        variant_id: int,
        update_data: link_schemas.ProductVariantLinkUpdate,
        db: GetDBDep
):
    """Atualiza as regras (min/max, UI mode, etc) de uma ligação existente."""
    db_link = db.query(models.ProductVariantLink).filter_by(product_id=product_id, variant_id=variant_id).first()
    if not db_link:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ligação não encontrada.")

    for field, value in update_data.model_dump(exclude_unset=True).items():
        setattr(db_link, field, value)

    db.commit()
    db.refresh(db_link)

    # ✅ 2. Chame os eventos com o store_id correto
    # Este evento provavelmente notifica os apps dos clientes (se aplicável)
  #  await emit_products_updated(db, store_id)

    # Este evento atualiza todos os painéis de admin conectados àquela loja
   # await admin_emit_store_full_updated(db, store_id=store_id)

    return db_link


@router.delete("/{variant_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Desvincula um grupo de um produto")
def unlink_variant_from_product(
        product_id: int,
        variant_id: int,
        db: GetDBDep
):
    """Remove a ligação entre um produto e um grupo, mas não apaga o template do grupo."""
    db_link = db.query(models.ProductVariantLink).filter_by(product_id=product_id, variant_id=variant_id).first()
    if not db_link:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ligação não encontrada.")

    db.delete(db_link)
    db.commit()