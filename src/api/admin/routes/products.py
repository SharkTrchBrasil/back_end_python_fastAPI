# src/api/admin/routes/products.py
import logging
import math
from typing import List, Optional
from fastapi import APIRouter, HTTPException, Request, Form, UploadFile, File, Query
from pydantic import ValidationError
from starlette import status

log = logging.getLogger(__name__)

from src.api.admin.routes import product_category_link
from src.api.admin.socketio.emitters import emit_updates_products
from src.api.crud import crud_product
from src.api.schemas.products.bulk_actions import BulkDeletePayload, BulkStatusUpdatePayload, BulkCategoryUpdatePayload
from src.api.schemas.products.product import (
    ProductOut,
    ProductUpdate,
    FlavorWizardCreate,
    SimpleProductWizardCreate,
    FlavorPriceUpdate
)
from src.api.schemas.products.product_category_link import ProductCategoryLinkUpdate, ProductCategoryLinkOut
from src.core import models
from src.core.aws import delete_file, upload_single_file, delete_multiple_files, S3_PUBLIC_BASE_URL
from src.core.database import GetDBDep
from src.core.dependencies import GetStoreDep, GetProductDep, GetCurrentUserDep, GetAuditLoggerDep
from src.core.utils.enums import ProductStatus, AuditAction, AuditEntityType

router = APIRouter(prefix="/stores/{store_id}/products", tags=["Products"])


# ===================================================================
# 🔥 PONTO VITAL 1: CRIAR PRODUTO SIMPLES
# ===================================================================
@router.post("/simple-product", response_model=ProductOut, status_code=201)
async def create_simple_product(
        request: Request,  # ✅ ADICIONAR
        store: GetStoreDep,
        db: GetDBDep,
        current_user: GetCurrentUserDep,  # ✅ ADICIONAR
        audit: GetAuditLoggerDep,  # ✅ ADICIONAR
        payload_str: str = Form(..., alias="payload"),
        images: List[UploadFile] = File([], alias="images"),
        video: UploadFile | None = File(None, alias="video"),
):
    """Cria um produto simples com imagem de capa e galeria."""
    try:
        payload = SimpleProductWizardCreate.model_validate_json(payload_str)
    except ValidationError as e:
        # ✅ LOG DE FALHA DE VALIDAÇÃO
        audit.log_failed_action(
            action=AuditAction.CREATE_PRODUCT,
            entity_type=AuditEntityType.PRODUCT,
            error=f"JSON inválido: {str(e)}"
        )
        db.commit()
        raise HTTPException(status_code=422, detail=f"JSON inválido: {e}")

    if video:
        video_key = upload_single_file(video, folder="products/videos")
        if video_key:
            payload.video_url = f"{S3_PUBLIC_BASE_URL}/{video_key}"

    product_data = payload.model_dump(exclude={'category_links', 'variant_links'})
    new_product = models.Product(**product_data, store_id=store.id)

    db.add(new_product)
    db.flush()

    # Upload de imagens
    uploaded_images_count = 0
    if images:
        for index, image_file in enumerate(images):
            gallery_file_key = upload_single_file(image_file, folder="products/gallery")
            if gallery_file_key:
                db.add(models.ProductImage(
                    product_id=new_product.id,
                    file_key=gallery_file_key,
                    display_order=index
                ))
                uploaded_images_count += 1

    # Vínculos com categorias
    category_links_data = []
    if payload.category_links:
        for link_data in payload.category_links:
            db.add(models.ProductCategoryLink(product_id=new_product.id, **link_data.model_dump()))
            category_links_data.append(link_data.model_dump())

    # Vínculos com variantes
    variant_links_created = []
    new_variants_created = []

    if payload.variant_links:
        for link_data in payload.variant_links:
            variant_data = link_data.variant

            if variant_data.id and variant_data.id > 0:
                # Variante existente
                db.add(models.ProductVariantLink(
                    product_id=new_product.id,
                    variant_id=variant_data.id,
                    min_selected_options=link_data.min_selected_options,
                    max_selected_options=link_data.max_selected_options,
                    ui_display_mode=link_data.ui_display_mode,
                    available=link_data.available
                ))
                variant_links_created.append({
                    "variant_id": variant_data.id,
                    "variant_name": variant_data.name,
                    "is_new": False
                })
            else:
                # ✅ Nova variante - Verifica se já existe uma variante com o mesmo nome na loja
                existing_variant = db.query(models.Variant).filter(
                    models.Variant.store_id == store.id,
                    models.Variant.name == variant_data.name
                ).first()

                if existing_variant:
                    # ✅ Variante já existe - reutiliza ela
                    log(f'[Product Creation] Variante "{variant_data.name}" já existe (ID: {existing_variant.id}). Reutilizando...')
                    variant_id_to_use = existing_variant.id
                    is_new_variant = False
                    options_count = len(existing_variant.options) if existing_variant.options else 0
                else:
                    # ✅ Variante não existe - cria nova
                    new_variant = models.Variant(
                        name=variant_data.name,
                        type=variant_data.type.value,
                        store_id=store.id
                    )
                    db.add(new_variant)
                    db.flush()

                    options_count = 0
                    if variant_data.options:
                        for option_data in variant_data.options:
                            db.add(models.VariantOption(
                                variant_id=new_variant.id,
                                store_id=store.id,
                                **option_data.model_dump(exclude={'image', 'variant_id'})
                            ))
                            options_count += 1

                    variant_id_to_use = new_variant.id
                    is_new_variant = True

                # ✅ Cria o vínculo do produto com a variante (nova ou existente)
                db.add(models.ProductVariantLink(
                    product_id=new_product.id,
                    variant_id=variant_id_to_use,
                    min_selected_options=link_data.min_selected_options,
                    max_selected_options=link_data.max_selected_options,
                    ui_display_mode=link_data.ui_display_mode,
                    available=link_data.available
                ))

                if is_new_variant:
                    new_variants_created.append({
                        "variant_id": variant_id_to_use,
                        "variant_name": variant_data.name,
                        "options_count": options_count,
                        "is_new": True
                    })
                else:
                    variant_links_created.append({
                        "variant_id": variant_id_to_use,
                        "variant_name": variant_data.name,
                        "is_new": False
                    })

    # ✅ LOG DE CRIAÇÃO BEM-SUCEDIDA
    audit.log(
        action=AuditAction.CREATE_PRODUCT,
        entity_type=AuditEntityType.PRODUCT,
        entity_id=new_product.id,
        changes={
            "product_name": new_product.name,
            "product_type": new_product.product_type.value if hasattr(new_product.product_type, 'value') else str(
                new_product.product_type),
            "status": new_product.status.value,
            "images_count": uploaded_images_count,
            "video_added": bool(video),
            "categories": category_links_data,
            "variants_linked": variant_links_created,
            "new_variants_created": new_variants_created
        },
        description=f"Produto simples '{new_product.name}' criado com {uploaded_images_count} imagens"
    )

    db.commit()
    db.refresh(new_product)
    await emit_updates_products(db, store.id)
    return new_product


# ===================================================================
# 🔥 PONTO VITAL 2: CRIAR PRODUTO SABOR (FLAVOR)
# ===================================================================
@router.post("/flavor-product", response_model=ProductOut, status_code=201)
async def create_flavor_product(
        request: Request,  # ✅ ADICIONAR
        store: GetStoreDep,
        db: GetDBDep,
        current_user: GetCurrentUserDep,  # ✅ ADICIONAR
        audit: GetAuditLoggerDep,  # ✅ ADICIONAR
        payload_str: str = Form(..., alias="payload"),
        video: UploadFile | None = File(None, alias="video"),
        images: List[UploadFile] = File([], alias="images"),
):
    """Cria um produto do tipo 'sabor' com imagem de capa e galeria."""
    try:
        payload = FlavorWizardCreate.model_validate_json(payload_str)
    except ValidationError as e:
        audit.log_failed_action(
            action=AuditAction.CREATE_PRODUCT,
            entity_type=AuditEntityType.PRODUCT,
            error=f"JSON inválido para flavor product: {str(e)}"
        )
        db.commit()
        raise HTTPException(status_code=422, detail=f"JSON inválido: {e}")

    parent_category = db.query(models.Category).filter(
        models.Category.id == payload.parent_category_id,
        models.Category.store_id == store.id
    ).first()

    if not parent_category:
        audit.log_failed_action(
            action=AuditAction.CREATE_PRODUCT,
            entity_type=AuditEntityType.PRODUCT,
            error=f"Categoria pai não encontrada: {payload.parent_category_id}"
        )
        db.commit()
        raise HTTPException(status_code=404, detail="Categoria pai não encontrada.")

    if video:
        video_key = upload_single_file(video, folder="products/videos")
        if video_key:
            payload.video_url = f"{S3_PUBLIC_BASE_URL}/{video_key}"

    product_data = payload.model_dump(exclude={'prices', 'parent_category_id'})
    new_product = models.Product(**product_data, store_id=store.id)
    db.add(new_product)
    db.flush()

    # Upload de imagens
    uploaded_images_count = 0
    if images:
        for index, image_file in enumerate(images):
            gallery_file_key = upload_single_file(image_file, folder="products/gallery")
            if gallery_file_key:
                db.add(models.ProductImage(
                    product_id=new_product.id,
                    file_key=gallery_file_key,
                    display_order=index
                ))
                uploaded_images_count += 1

    # Vínculo com categoria pai
    db.add(models.ProductCategoryLink(
        product_id=new_product.id,
        category_id=payload.parent_category_id,
        price=0
    ))

    # Preços por tamanho
    prices_data = []
    for price_data in payload.prices:
        db.add(models.FlavorPrice(product_id=new_product.id, **price_data.model_dump()))
        prices_data.append(price_data.model_dump())

    # ✅ LOG DE CRIAÇÃO BEM-SUCEDIDA
    audit.log(
        action=AuditAction.CREATE_PRODUCT,
        entity_type=AuditEntityType.PRODUCT,
        entity_id=new_product.id,
        changes={
            "product_name": new_product.name,
            "product_type": "flavor",
            "parent_category_id": payload.parent_category_id,
            "parent_category_name": parent_category.name,
            "images_count": uploaded_images_count,
            "video_added": bool(video),
            "prices_count": len(prices_data),
            "prices": prices_data
        },
        description=f"Produto sabor '{new_product.name}' criado com {len(prices_data)} tamanhos"
    )

    db.commit()
    db.refresh(new_product)
    await emit_updates_products(db, store.id)
    return new_product


# ===================================================================
# 🔥 PONTO VITAL 3: ATUALIZAR PRODUTO
# ===================================================================
@router.patch("/{product_id}", response_model=ProductOut)
async def update_product(
        request: Request,  # ✅ ADICIONAR
        store: GetStoreDep,
        db: GetDBDep,
        current_user: GetCurrentUserDep,  # ✅ ADICIONAR
        audit: GetAuditLoggerDep,  # ✅ ADICIONAR
        db_product: GetProductDep,
        payload_str: str = Form(..., alias="payload"),
        images: List[UploadFile] = File([], alias="images"),
        video: UploadFile | None = File(None, alias="video"),
):
    """Atualiza um produto existente."""

    # ✅ CAPTURA ESTADO ANTERIOR
    old_values = {
        "name": db_product.name,
        "status": db_product.status.value,
        "video_url": db_product.video_url,
        "gallery_count": len(db_product.gallery_images) if db_product.gallery_images else 0
    }

    try:
        update_data = ProductUpdate.model_validate_json(payload_str)
    except ValidationError as e:
        audit.log_failed_action(
            action=AuditAction.UPDATE_PRODUCT,
            entity_type=AuditEntityType.PRODUCT,
            entity_id=db_product.id,
            error=f"JSON inválido: {str(e)}"
        )
        db.commit()
        raise HTTPException(status_code=422, detail=f"JSON inválido: {e}")

    new_gallery_file_keys = []
    file_keys_to_delete_s3 = []
    changes = {}

    # Processamento de vídeo
    video_action = None
    if video:
        if db_product.video_url:
            old_video_key = db_product.video_url.split('/')[-1]
            file_keys_to_delete_s3.append(f"products/videos/{old_video_key}")
            video_action = "replaced"
        else:
            video_action = "added"

        video_key = upload_single_file(video, folder="products/videos")
        if video_key:
            update_data.video_url = f"{S3_PUBLIC_BASE_URL}/{video_key}"
            changes["video_action"] = video_action

    elif update_data.video_url is None and db_product.video_url is not None:
        old_video_key = db_product.video_url.split('/')[-1]
        file_keys_to_delete_s3.append(f"products/videos/{old_video_key}")
        changes["video_action"] = "removed"

    # Processamento de imagens
    new_images_count = 0
    if images:
        for image_file in images:
            file_key = upload_single_file(image_file, folder="products/gallery")
            if file_key:
                new_gallery_file_keys.append(file_key)
                new_images_count += 1
        changes["new_images_added"] = new_images_count

    # Atualização via CRUD
    updated_product, file_keys_to_delete = crud_product.update_product(
        db=db,
        db_product=db_product,
        update_data=update_data,
        store_id=store.id,
        new_gallery_file_keys=new_gallery_file_keys
    )

    # Rastreia mudanças de campos
    if updated_product.name != old_values["name"]:
        changes["name_changed"] = {
            "from": old_values["name"],
            "to": updated_product.name
        }

    if updated_product.status.value != old_values["status"]:
        changes["status_changed"] = {
            "from": old_values["status"],
            "to": updated_product.status.value
        }

    new_gallery_count = len(updated_product.gallery_images) if updated_product.gallery_images else 0
    if new_gallery_count != old_values["gallery_count"]:
        changes["gallery_images_count"] = {
            "from": old_values["gallery_count"],
            "to": new_gallery_count
        }

    # ✅ LOG DE ATUALIZAÇÃO BEM-SUCEDIDA
    audit.log(
        action=AuditAction.UPDATE_PRODUCT,
        entity_type=AuditEntityType.PRODUCT,
        entity_id=updated_product.id,
        changes=changes,
        description=f"Produto '{updated_product.name}' atualizado"
    )

    # Limpeza de arquivos antigos
    if file_keys_to_delete:
        delete_multiple_files(file_keys_to_delete)

    db.commit()
    await emit_updates_products(db, store.id)
    return updated_product


# ===================================================================
# 🔥 PONTO VITAL 4: ATUALIZAR PREÇO EM CATEGORIA
# ===================================================================
@router.patch("/{product_id}/categories/{category_id}", response_model=ProductCategoryLinkOut)
async def update_simple_product_price(
        request: Request,  # ✅ ADICIONAR
        store: GetStoreDep,
        product_id: int,
        category_id: int,
        update_data: ProductCategoryLinkUpdate,
        db: GetDBDep,
        current_user: GetCurrentUserDep,  # ✅ ADICIONAR
        audit: GetAuditLoggerDep,  # ✅ ADICIONAR
):
    """Atualiza o preço/promoção de um produto simples em uma categoria específica."""
    db_link = db.query(models.ProductCategoryLink).filter(
        models.ProductCategoryLink.product_id == product_id,
        models.ProductCategoryLink.category_id == category_id
    ).first()

    if not db_link:
        audit.log_failed_action(
            action=AuditAction.UPDATE_PRODUCT_PRICE,
            entity_type=AuditEntityType.PRODUCT,
            entity_id=product_id,
            error=f"Vínculo produto-categoria não encontrado: product={product_id}, category={category_id}"
        )
        db.commit()
        raise HTTPException(status_code=404, detail="Vínculo produto-categoria não encontrado.")

    # ✅ CAPTURA ESTADO ANTERIOR
    old_values = {
        "price": db_link.price,
        "is_on_promotion": db_link.is_on_promotion,
        "promotional_price": db_link.promotional_price
    }

    changes = {}
    for field, value in update_data.model_dump(exclude_unset=True).items():
        if getattr(db_link, field) != value:
            changes[field] = {
                "from": getattr(db_link, field),
                "to": value
            }
        setattr(db_link, field, value)

    # ✅ LOG DE ATUALIZAÇÃO DE PREÇO
    audit.log(
        action=AuditAction.UPDATE_PRODUCT_PRICE,
        entity_type=AuditEntityType.PRODUCT,
        entity_id=product_id,
        changes={
            "category_id": category_id,
            "old_values": old_values,
            "changes": changes
        },
        description=f"Preço do produto ID {product_id} atualizado na categoria ID {category_id}"
    )

    db.commit()
    db.refresh(db_link)
    await emit_updates_products(db, store.id)
    return db_link


# ===================================================================
# 🔥 PONTO VITAL 5: ATUALIZAR PREÇO DE SABOR
# ===================================================================
@router.patch("/prices/{flavor_price_id}", response_model=ProductOut)
async def update_flavor_price(
        request: Request,  # ✅ ADICIONAR
        store: GetStoreDep,
        flavor_price_id: int,
        update_data: FlavorPriceUpdate,
        db: GetDBDep,
        current_user: GetCurrentUserDep,  # ✅ ADICIONAR
        audit: GetAuditLoggerDep,  # ✅ ADICIONAR
):
    """Atualiza o preço de um sabor para um tamanho específico."""
    db_price_link = db.query(models.FlavorPrice).join(models.Product).filter(
        models.FlavorPrice.id == flavor_price_id,
        models.Product.store_id == store.id
    ).first()

    if not db_price_link:
        audit.log_failed_action(
            action=AuditAction.UPDATE_PRODUCT_PRICE,
            entity_type=AuditEntityType.PRODUCT,
            error=f"Preço de sabor não encontrado: {flavor_price_id}"
        )
        db.commit()
        raise HTTPException(status_code=404, detail="Preço para este tamanho não encontrado.")

    old_price = db_price_link.price
    db_price_link.price = update_data.price

    # ✅ LOG DE ATUALIZAÇÃO DE PREÇO DE SABOR
    audit.log(
        action=AuditAction.UPDATE_PRODUCT_PRICE,
        entity_type=AuditEntityType.PRODUCT,
        entity_id=db_price_link.product_id,
        changes={
            "flavor_price_id": flavor_price_id,
            "size_option_id": db_price_link.size_option_id,
            "old_price": old_price,
            "new_price": update_data.price
        },
        description=f"Preço de sabor atualizado: R$ {old_price / 100:.2f} → R$ {update_data.price / 100:.2f}"
    )

    db.commit()
    product_to_return = db.query(models.Product).get(db_price_link.product_id)
    db.refresh(product_to_return)
    await emit_updates_products(db, store.id)
    return product_to_return


# ===================================================================
# 🔥 PONTO VITAL 6: ARQUIVAR PRODUTO
# ===================================================================
@router.patch("/{product_id}/archive", status_code=status.HTTP_204_NO_CONTENT)
async def archive_product(
        request: Request,  # ✅ ADICIONAR
        store: GetStoreDep,
        db: GetDBDep,
        current_user: GetCurrentUserDep,  # ✅ ADICIONAR
        audit: GetAuditLoggerDep,  # ✅ ADICIONAR
        db_product: GetProductDep
):
    """Arquiva um produto (soft delete)."""
    if db_product.status == ProductStatus.ARCHIVED:
        return

    old_status = db_product.status.value
    crud_product.archive_product(db=db, db_product=db_product)

    # ✅ LOG DE ARQUIVAMENTO
    audit.log(
        action=AuditAction.ARCHIVE_PRODUCT,
        entity_type=AuditEntityType.PRODUCT,
        entity_id=db_product.id,
        changes={
            "product_name": db_product.name,
            "old_status": old_status,
            "new_status": "ARCHIVED"
        },
        description=f"Produto '{db_product.name}' arquivado"
    )

    db.commit()
    await emit_updates_products(db, store.id)
    return


# ===================================================================
# 🔥 PONTO VITAL 7: ARQUIVAR PRODUTOS EM MASSA
# ===================================================================
@router.post("/bulk-archive", status_code=status.HTTP_204_NO_CONTENT)
async def bulk_archive_products(
        request: Request,  # ✅ ADICIONAR
        store: GetStoreDep,
        db: GetDBDep,
        current_user: GetCurrentUserDep,  # ✅ ADICIONAR
        audit: GetAuditLoggerDep,
        payload: BulkDeletePayload,
):
    """Arquiva uma lista de produtos de uma vez."""
    if not payload.product_ids:
        return

    # Busca nomes dos produtos antes de arquivar
    products_to_archive = db.query(models.Product.id, models.Product.name).filter(
        models.Product.id.in_(payload.product_ids),
        models.Product.store_id == store.id
    ).all()

    product_names = {p.id: p.name for p in products_to_archive}

    crud_product.bulk_archive_products(
        db=db,
        store_id=store.id,
        product_ids=payload.product_ids
    )

    # ✅ LOG BULK DE ARQUIVAMENTO
    audit.log_bulk(
        action=AuditAction.BULK_ARCHIVE_PRODUCTS,
        entity_type=AuditEntityType.PRODUCT,
        entity_ids=payload.product_ids,
        changes={"product_names": product_names},
        description=f"{len(payload.product_ids)} produtos arquivados em massa"
    )

    db.commit()
    await emit_updates_products(db, store.id)
    return


# ===================================================================
# 🔥 PONTO VITAL 8: MOVER PRODUTOS PARA CATEGORIA
# ===================================================================
@router.post("/bulk-update-category", response_model=dict, status_code=200)
async def bulk_update_product_category(
        request: Request,  # ✅ ADICIONAR
        store: GetStoreDep,
        db: GetDBDep,
        current_user: GetCurrentUserDep,  # ✅ ADICIONAR
        audit: GetAuditLoggerDep,  # ✅ ADICIONAR
        payload: BulkCategoryUpdatePayload,
):
    """Move uma lista de produtos para uma nova categoria."""

    # Busca o nome da categoria de destino
    target_category = db.query(models.Category).filter(
        models.Category.id == payload.target_category_id,
        models.Category.store_id == store.id
    ).first()

    if not target_category:
        audit.log_failed_action(
            action=AuditAction.BULK_UPDATE_CATEGORY,
            entity_type=AuditEntityType.PRODUCT,
            error=f"Categoria de destino não encontrada: {payload.target_category_id}"
        )
        db.commit()
        raise HTTPException(status_code=404, detail="Categoria de destino não encontrada.")

    # Coleta IDs e nomes dos produtos
    product_ids = [p.product_id for p in payload.products]
    products_info = db.query(models.Product.id, models.Product.name).filter(
        models.Product.id.in_(product_ids),
        models.Product.store_id == store.id
    ).all()

    product_names = {p.id: p.name for p in products_info}

    crud_product.bulk_update_product_category(
        db=db,
        store_id=store.id,
        payload=payload
    )

    # ✅ LOG BULK DE MOVIMENTAÇÃO
    audit.log_bulk(
        action=AuditAction.BULK_UPDATE_CATEGORY,
        entity_type=AuditEntityType.PRODUCT,
        entity_ids=product_ids,
        changes={
            "target_category_id": payload.target_category_id,
            "target_category_name": target_category.name,
            "products_moved": product_names,
            "prices_updated": [p.model_dump() for p in payload.products]
        },
        description=f"{len(product_ids)} produtos movidos para categoria '{target_category.name}'"
    )

    db.commit()
    await emit_updates_products(db, store.id)
    return {"message": "Produtos movidos e reprecificados com sucesso"}


# ===================================================================
# 🔥 PONTO VITAL 9: ATUALIZAR STATUS EM MASSA
# ===================================================================
@router.post("/bulk-update-status", status_code=204)
async def bulk_update_product_status(
        request: Request,  # ✅ ADICIONAR
        store: GetStoreDep,
        db: GetDBDep,
        current_user: GetCurrentUserDep,  # ✅ ADICIONAR
        audit: GetAuditLoggerDep,  # ✅ ADICIONAR
        payload: BulkStatusUpdatePayload,
):
    """Ativa ou desativa uma lista de produtos."""
    if not payload.product_ids:
        return

    new_status = ProductStatus.ACTIVE if payload.available else ProductStatus.INACTIVE

    # Busca nomes dos produtos
    products_info = db.query(models.Product.id, models.Product.name).filter(
        models.Product.id.in_(payload.product_ids),
        models.Product.store_id == store.id
    ).all()

    product_names = {p.id: p.name for p in products_info}

    db.query(models.Product).filter(
        models.Product.store_id == store.id,
        models.Product.id.in_(payload.product_ids)
    ).update(
        {"status": new_status},
        synchronize_session=False
    )

    # ✅ LOG BULK DE ATUALIZAÇÃO DE STATUS
    audit.log_bulk(
        action=AuditAction.BULK_UPDATE_STATUS,
        entity_type=AuditEntityType.PRODUCT,
        entity_ids=payload.product_ids,
        changes={
            "new_status": new_status.value,
            "product_names": product_names
        },
        description=f"{len(payload.product_ids)} produtos {('ativados' if payload.available else 'desativados')}"
    )

    db.commit()
    await emit_updates_products(db, store.id)
    return


# ===================================================================
# 🔥 PONTO VITAL 10: REMOVER PRODUTO DE CATEGORIA
# ===================================================================
@router.delete("/{product_id}/categories/{category_id}", status_code=204)
async def remove_product_from_category_route(
        request: Request,  # ✅ ADICIONAR
        product_id: int,
        category_id: int,
        store: GetStoreDep,
        db: GetDBDep,
        current_user: GetCurrentUserDep,  # ✅ ADICIONAR
        audit: GetAuditLoggerDep,  # ✅ ADICIONAR
):
    """Desvincula um produto de uma categoria."""

    # Busca informações antes de remover
    product = db.query(models.Product).filter(
        models.Product.id == product_id,
        models.Product.store_id == store.id
    ).first()

    category = db.query(models.Category).filter(
        models.Category.id == category_id,
        models.Category.store_id == store.id
    ).first()

    if not product or not category:
        audit.log_failed_action(
            action=AuditAction.REMOVE_PRODUCT_FROM_CATEGORY,
            entity_type=AuditEntityType.PRODUCT,
            entity_id=product_id,
            error=f"Produto ou categoria não encontrados: product={product_id}, category={category_id}"
        )
        db.commit()
        raise HTTPException(status_code=404, detail="Produto ou categoria não encontrados.")

    rows_deleted = crud_product.remove_product_from_category(
        db=db,
        store_id=store.id,
        product_id=product_id,
        category_id=category_id
    )

    if rows_deleted > 0:
        # ✅ LOG DE REMOÇÃO
        audit.log(
            action=AuditAction.REMOVE_PRODUCT_FROM_CATEGORY,
            entity_type=AuditEntityType.PRODUCT,
            entity_id=product_id,
            changes={
                "product_name": product.name,
                "category_id": category_id,
                "category_name": category.name
            },
            description=f"Produto '{product.name}' removido da categoria '{category.name}'"
        )
        db.commit()

    await emit_updates_products(db, store.id)
    return


# ===================================================================
# 🔥 PONTO VITAL 11: ADICIONAR PRODUTOS A CATEGORIA
# ===================================================================
@router.post("/bulk-add-update-links", status_code=status.HTTP_200_OK)
async def bulk_add_products_to_category(
        request: Request,  # ✅ ADICIONAR
        db: GetDBDep,
        store: GetStoreDep,
        current_user: GetCurrentUserDep,  # ✅ ADICIONAR
        audit: GetAuditLoggerDep,  # ✅ ADICIONAR
        payload: BulkCategoryUpdatePayload
):
    """Adiciona ou atualiza múltiplos produtos em uma categoria."""

    # Busca informações da categoria
    target_category = db.query(models.Category).filter(
        models.Category.id == payload.target_category_id,
        models.Category.store_id == store.id
    ).first()

    if not target_category:
        audit.log_failed_action(
            action=AuditAction.ADD_PRODUCT_TO_CATEGORY,
            entity_type=AuditEntityType.PRODUCT,
            error=f"Categoria não encontrada: {payload.target_category_id}"
        )
        db.commit()
        raise HTTPException(status_code=404, detail="Categoria não encontrada.")

    # Coleta IDs e nomes dos produtos
    product_ids = [p.product_id for p in payload.products]
    products_info = db.query(models.Product.id, models.Product.name).filter(
        models.Product.id.in_(product_ids),
        models.Product.store_id == store.id
    ).all()

    product_names = {p.id: p.name for p in products_info}

    crud_product.bulk_add_or_update_links(
        db=db,
        store_id=store.id,
        target_category_id=payload.target_category_id,
        products_data=payload.products
    )

    # ✅ LOG BULK DE ADIÇÃO
    audit.log_bulk(
        action=AuditAction.ADD_PRODUCT_TO_CATEGORY,
        entity_type=AuditEntityType.PRODUCT,
        entity_ids=product_ids,
        changes={
            "category_id": payload.target_category_id,
            "category_name": target_category.name,
            "products_added": product_names
        },
        description=f"{len(product_ids)} produtos adicionados à categoria '{target_category.name}'"
    )

    db.commit()
    await emit_updates_products(db, store.id)
    return {"message": "Produtos adicionados/atualizados com sucesso"}


# ===================================================================
# 🔥 PONTO VITAL 12: DESVINCULAR VARIANTE DE PRODUTO
# ===================================================================
@router.delete("/{product_id}/variants/{variant_id}", status_code=204)
def unlink_variant_from_product(
        request: Request,  # ✅ ADICIONAR
        db: GetDBDep,
        store: GetStoreDep,
        product: GetProductDep,
        variant_id: int,
        current_user: GetCurrentUserDep,  # ✅ ADICIONAR
        audit: GetAuditLoggerDep,  # ✅ ADICIONAR
):
    """Remove o vínculo entre um produto e um grupo de complementos."""

    # Busca informações da variante
    variant = db.query(models.Variant).filter(
        models.Variant.id == variant_id,
        models.Variant.store_id == store.id
    ).first()

    link_to_delete = db.query(models.ProductVariantLink).filter(
        models.ProductVariantLink.product_id == product.id,
        models.ProductVariantLink.variant_id == variant_id
    ).first()

    if not link_to_delete:
        audit.log_failed_action(
            action=AuditAction.UNLINK_VARIANT_FROM_PRODUCT,
            entity_type=AuditEntityType.PRODUCT,
            entity_id=product.id,
            error=f"Vínculo não encontrado: product={product.id}, variant={variant_id}"
        )
        db.commit()
        raise HTTPException(status_code=404, detail="Vínculo entre produto e grupo não encontrado.")

    db.delete(link_to_delete)

    # ✅ LOG DE DESVINCULAÇÃO
    audit.log(
        action=AuditAction.UNLINK_VARIANT_FROM_PRODUCT,
        entity_type=AuditEntityType.PRODUCT,
        entity_id=product.id,
        changes={
            "product_name": product.name,
            "variant_id": variant_id,
            "variant_name": variant.name if variant else "Desconhecido"
        },
        description=f"Grupo de complementos '{variant.name if variant else variant_id}' desvinculado do produto '{product.name}'"
    )

    db.commit()
    return None


# ===================================================================
# ROTAS SEM AUDITORIA (NÃO SÃO CRÍTICAS)
# ===================================================================

@router.post("/{product_id}/view", status_code=204)
def record_product_view(product: GetProductDep, store: GetStoreDep, db: GetDBDep):
    """Registra uma visualização de produto (métrica)."""
    db.add(models.ProductView(product_id=product.id, store_id=store.id))
    db.commit()
    return


@router.get("/minimal", response_model=dict)
def get_minimal_products(
        store: GetStoreDep,
        db: GetDBDep,
        search: Optional[str] = Query(None, description="Busca por nome"),
        page: int = Query(1, ge=1),
        size: int = Query(50, ge=1, le=200),
):
    """Lista produtos mínimos com paginação."""
    query = db.query(models.Product.id, models.Product.name).filter(
        models.Product.store_id == store.id,
        models.Product.status != ProductStatus.ARCHIVED
    )

    if search:
        search_pattern = f"%{search}%"
        query = query.filter(models.Product.name.ilike(search_pattern))

    total = query.count()
    products = query.offset((page - 1) * size).limit(size).all()

    return {
        "items": [{"id": p.id, "name": p.name} for p in products],
        "total": total,
        "page": page,
        "size": size,
        "pages": math.ceil(total / size)
    }


@router.get("", response_model=List[ProductOut])
def get_products(db: GetDBDep, store: GetStoreDep, skip: int = 0, limit: int = 100):
    """Lista todos os produtos da loja."""
    products = crud_product.get_all_products_for_store(
        db=db,
        store_id=store.id,
        skip=skip,
        limit=limit
    )
    return products


@router.get("/search", response_model=dict)
def search_products_lightweight(
        store: GetStoreDep,
        db: GetDBDep,
        q: str = Query(..., min_length=2, description="Termo de busca"),
        limit: int = Query(20, ge=1, le=50),
):
    """Busca rápida para autocomplete."""
    search_pattern = f"%{q}%"

    products = db.query(
        models.Product.id,
        models.Product.name,
        models.Product.status
    ).filter(
        models.Product.store_id == store.id,
        models.Product.name.ilike(search_pattern),
        models.Product.status != ProductStatus.ARCHIVED
    ).limit(limit).all()

    return {
        "items": [
            {
                "id": p.id,
                "name": p.name,
                "status": p.status.value
            }
            for p in products
        ],
        "count": len(products)
    }


@router.get("/{product_id}", response_model=ProductOut)
def get_product_details(product: GetProductDep):
    """Retorna os detalhes completos de um produto."""
    return product


@router.patch(
    "/{product_id}/categories/{category_id}",
    response_model=ProductCategoryLinkOut,
    summary="Atualiza o preço/promoção de um produto em uma categoria específica"
)
async def update_product_category_link(
        store: GetStoreDep,
        product_id: int,
        category_id: int,
        update_data: ProductCategoryLinkUpdate,
        db: GetDBDep,
):
    """Atualiza link produto-categoria (já tem auditoria na rota update_simple_product_price)."""
    db_link = db.query(models.ProductCategoryLink).join(models.Product).filter(
        models.Product.store_id == store.id,
        models.ProductCategoryLink.product_id == product_id,
        models.ProductCategoryLink.category_id == category_id
    ).first()
    if not db_link:
        raise HTTPException(status_code=404, detail="Este produto não está vinculado a esta categoria.")
    for field, value in update_data.model_dump(exclude_unset=True).items():
        setattr(db_link, field, value)
    db.commit()
    db.refresh(db_link)
    await emit_updates_products(db, store.id)
    return db_link


@router.patch(
    "/{product_id}/categories/{category_id}/availability",
    response_model=ProductCategoryLinkOut,
    summary="Ativa ou pausa um produto em uma categoria específica"
)
async def toggle_product_availability_in_category(
        store: GetStoreDep,
        product_id: int,
        category_id: int,
        payload: ProductCategoryLinkUpdate,
        db: GetDBDep,
):
    """Atualiza disponibilidade de um produto em uma categoria."""
    db_link = crud_product.update_link_availability(
        db=db,
        store_id=store.id,
        product_id=product_id,
        category_id=category_id,
        is_available=payload.is_available
    )
    if not db_link:
        raise HTTPException(status_code=404, detail="Vínculo produto-categoria não encontrado.")

    await emit_updates_products(db, store.id)
    return db_link


router.include_router(
    product_category_link.router,
    prefix="/{product_id}/categories"
)