import asyncio
from typing import List


from fastapi import APIRouter, Form
import json
from pydantic import ValidationError
from starlette import status

from src.api.admin.socketio.emitters import admin_emit_products_updated, admin_emit_store_updated
from src.api.admin.utils.emit_updates import emit_updates_products
from src.api.app.socketio.socketio_emitters import emit_products_updated
from src.api.schemas.bulk_actions import ProductCategoryUpdatePayload, BulkDeletePayload, BulkCategoryUpdatePayload, \
    BulkStatusUpdatePayload
from src.api.schemas.product import ProductWizardCreate, ProductOut, ProductUpdate
from src.api.schemas.product_category_link import ProductCategoryLinkOut, ProductCategoryLinkUpdate

from src.core import models
from src.core.aws import upload_file, delete_file
from src.core.database import GetDBDep
from src.core.dependencies import GetStoreDep, GetProductDep
from src.core.utils.enums import CashbackType

router = APIRouter(prefix="/stores/{store_id}/products", tags=["Products"])


from fastapi import UploadFile, File, HTTPException
from sqlalchemy.orm import selectinload




@router.post("/wizard", response_model=ProductOut)
async def create_product_from_wizard(
    store: GetStoreDep,
    db: GetDBDep,
    # ✅ 2. Receba o payload como uma string de um campo de formulário
    payload_str: str = Form(..., alias="payload"),
    image: UploadFile | None = File(None),
):
    """
    Cria um produto completo a partir do wizard, recebendo
    um payload JSON como string dentro de um multipart/form-data.
    """
    try:
        payload = ProductWizardCreate.model_validate_json(payload_str)
    except (ValidationError, json.JSONDecodeError) as e:
        raise HTTPException(status_code=422, detail=f"Erro de validação no payload JSON: {e}")
    if not payload.category_links:
        raise HTTPException(status_code=400, detail="O produto deve pertencer a pelo menos uma categoria.")
    main_category_id = payload.category_links[0].category_id
    category = db.query(models.Category).filter(models.Category.id == main_category_id,
                                                models.Category.store_id == store.id).first()
    if not category:
        raise HTTPException(status_code=404, detail=f"Categoria principal com id {main_category_id} não encontrada.")
    current_product_count_in_category = db.query(models.ProductCategoryLink).join(models.Product,
                                                                                  models.Product.id == models.ProductCategoryLink.product_id).filter(
        models.ProductCategoryLink.category_id == main_category_id, models.Product.store_id == store.id).count()
    new_priority = current_product_count_in_category
    file_key = upload_file(image) if image is not None else None
    new_product_data = payload.model_dump(exclude={'category_links', 'variant_links'})
    new_product = models.Product(**new_product_data, store_id=store.id, file_key=file_key, priority=new_priority)
    db.add(new_product)
    db.flush()

    # 4. Vinculando as Categorias (usando a tabela de junção)
    for link_data in payload.category_links:
        new_category_link = models.ProductCategoryLink(
            product_id=new_product.id,
            **link_data.model_dump()  # <-- Passa tudo de uma vez
        )
        db.add(new_category_link)

    # 5. Processamento dos Grupos de Complementos (Variant Links)
    for link_data in payload.variant_links:
        variant_to_link: models.Variant

        if link_data.variant_id < 0 and link_data.new_variant_data:  # ID negativo indica um novo grupo
            new_variant = models.Variant(
                name=link_data.new_variant_data.name,
                type=link_data.new_variant_data.type,
                store_id=store.id
            )
            db.add(new_variant)
            db.flush()

            # Este é o loop correto que salva todos os detalhes da opção
            for option_data in link_data.new_variant_data.options:
                new_option = models.VariantOption(
                    variant_id=new_variant.id,
                    store_id=store.id,
                    **option_data.model_dump()
                )
                db.add(new_option)

            variant_to_link = new_variant
        else:
            existing_variant = db.query(models.Variant).get(link_data.variant_id)
            if not existing_variant or existing_variant.store_id != store.id:
                raise HTTPException(404, f"Variant with id {link_data.variant_id} not found.")
            variant_to_link = existing_variant

        # passar todos os dados do payload (min, max, ui_display_mode, etc.) de uma vez.
        new_link = models.ProductVariantLink(
            **link_data.model_dump(exclude={'new_variant_data', 'variant_id'}),
            product_id=new_product.id,
            variant_id=variant_to_link.id
        )
        db.add(new_link)

    # 6. Salva tudo no banco de dados
    db.commit()

    # ✅ --- AJUSTE FINAL: BUSCA E RETORNO DO OBJETO COMPLETO --- ✅
    # Em vez de apenas dar um refresh, fazemos uma nova busca pelo produto
    # recém-criado, já carregando todas as relações que o ProductOut precisa.
    product_to_return = db.query(models.Product).options(
        selectinload(models.Product.category_links).selectinload(models.ProductCategoryLink.category),
        selectinload(models.Product.variant_links).selectinload(models.ProductVariantLink.variant).selectinload(
            models.Variant.options)
    ).filter(models.Product.id == new_product.id).first()

    # 7. Emite os eventos e retorna o objeto completo e validado
    await emit_updates_products(db, store.id)
    return product_to_return





@router.post("/{product_id}/view", status_code=204)
def record_product_view(product: GetProductDep, store: GetStoreDep, db: GetDBDep):
    db.add(models.ProductView(product_id=product.id, store_id=store.id))
    db.commit()
    return


@router.get("/minimal", response_model=list[dict])
def get_minimal_products(store_id: int, db: GetDBDep):
    products = db.query(models.Product).filter(models.Product.store_id == store_id).all()
    return [{"id": p.id, "name": p.name} for p in products]


@router.get("", response_model=List[ProductOut])
def get_products(db: GetDBDep, store: GetStoreDep, skip: int = 0, limit: int = 100):
    products = db.query(models.Product).filter(models.Product.store_id == store.id).options(
        selectinload(models.Product.category_links).selectinload(models.ProductCategoryLink.category),
        selectinload(models.Product.variant_links).selectinload(models.ProductVariantLink.variant).selectinload(models.Variant.options)
    ).order_by(models.Product.priority).offset(skip).limit(limit).all()
    return products

@router.get("/{product_id}", response_model=ProductOut)
def get_product_details(product: GetProductDep):
    # A dependência GetProductDep já faz o trabalho de buscar o produto.
    # Para garantir que as relações estejam carregadas para o ProductOut,
    # o ideal é que a própria dependência já use o `selectinload`.
    return product
# --- ROTA PARA ATUALIZAR PREÇO/PROMOÇÃO EM UMA CATEGORIA ---

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

# --- ROTAS ADICIONAIS E EM MASSA ---

# ... seus outros imports ...
from src.api.crud import crud_product # ✨ Importe o crud_product

@router.patch("/{product_id}", response_model=ProductOut)
async def patch_product(
        db: GetDBDep,
        db_product: GetProductDep,
        payload_str: str = Form(..., alias="payload"),
        image: UploadFile | None = File(None),
):
    """Atualiza os dados de um produto."""
    try:
        update_data = ProductUpdate.model_validate_json(payload_str)
    except ValidationError as e:
        raise HTTPException(status_code=422, detail=f"Erro de validação: {e}")

    # Converte os dados recebidos em um dicionário
    update_dict = update_data.model_dump(exclude_unset=True)

    # ✨ LÓGICA DE ATUALIZAÇÃO EM CASCATA ADICIONADA AQUI ✨
    # 1. Verificamos se o status 'available' foi enviado na requisição
    if 'available' in update_dict:
        # 2. Se sim, chamamos a função CRUD especial que lida com a cascata
        crud_product.update_product_availability(
            db=db,
            db_product=db_product,
            is_available=update_data.available
        )
        # 3. Removemos 'available' do dicionário para não ser atualizado de novo pelo loop genérico
        update_dict.pop('available')

    # O loop agora atualiza todos os OUTROS campos que podem ter sido enviados
    for field, value in update_dict.items():
        setattr(db_product, field, value)

    # Lógica para atualizar a imagem (continua a mesma)
    if image:
        old_file_key = db_product.file_key
        db_product.file_key = upload_file(image)
        if old_file_key:
            delete_file(old_file_key)

    db.commit()

    # Recarrega o produto com suas relações para a resposta
    product_to_return = db.query(models.Product).options(
        selectinload(models.Product.category_links).selectinload(models.ProductCategoryLink.category),
        selectinload(models.Product.variant_links).selectinload(models.ProductVariantLink.variant)
    ).filter(models.Product.id == db_product.id).first()

    await emit_updates_products(db, db_product.store_id)
    return product_to_return


@router.delete("/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_product(store: GetStoreDep, db: GetDBDep, db_product: GetProductDep):
    old_file_key = db_product.file_key
    db.delete(db_product)
    db.commit()
    # ✅ Adicionada checagem de segurança
    if old_file_key:
        delete_file(old_file_key)
    await emit_updates_products(db, store.id)
    return

# --- ROTA PARA ATUALIZAR PREÇO/PROMOÇÃO EM UMA CATEGORIA --

@router.post("/bulk-delete", status_code=204)
async def bulk_delete_products(
    store: GetStoreDep,
    db: GetDBDep,
    payload: BulkDeletePayload,
):
    """
    Remove uma lista de produtos de uma vez.
    """
    if not payload.product_ids:
        return

    # IMPORTANTE: Antes de deletar, pegue os file_keys para apagar da AWS/S3
    products_to_delete = db.query(models.Product)\
                           .filter(models.Product.id.in_(payload.product_ids)).all()

    for product in products_to_delete:
        if product.file_key:
            delete_file(product.file_key) # Função que apaga o arquivo da S3

    # Agora, delete os registros do banco
    db.query(models.Product)\
      .filter(
          models.Product.store_id == store.id,
          models.Product.id.in_(payload.product_ids)
      )\
      .delete(synchronize_session=False)

    db.commit()

    await emit_updates_products(db, store.id)
    return


@router.post("/bulk-update-category", status_code=204)
async def bulk_update_product_category(
        store: GetStoreDep,
        db: GetDBDep,
        payload: BulkCategoryUpdatePayload,
):
    """
    Define a categoria de uma lista de produtos para uma nova categoria.
    Esta operação REMOVE os produtos de todas as categorias antigas
    e os vincula APENAS à nova categoria de destino.
    """
    if not payload.product_ids:
        raise HTTPException(status_code=400, detail="Nenhum ID de produto foi fornecido.")

    # 1. Verifica se a categoria de destino existe e pertence à loja
    target_category = db.query(models.Category).filter(
        models.Category.id == payload.target_category_id,
        models.Category.store_id == store.id
    ).first()

    if not target_category:
        raise HTTPException(status_code=404, detail="Categoria de destino não encontrada.")

    # 2. Deleta TODOS os vínculos de categoria existentes para os produtos selecionados.
    # Isso garante que eles não fiquem em categorias antigas.
    db.query(models.ProductCategoryLink) \
        .filter(models.ProductCategoryLink.product_id.in_(payload.product_ids)) \
        .delete(synchronize_session=False)

    # 3. Cria os novos vínculos para cada produto com a categoria de destino.
    new_links = []
    for product_id in payload.product_ids:
        # Verifica se o produto realmente pertence à loja para segurança
        product = db.query(models.Product.id).filter(
            models.Product.id == product_id,
            models.Product.store_id == store.id
        ).first()

        if product:
            new_links.append(
                models.ProductCategoryLink(
                    product_id=product_id,
                    category_id=payload.target_category_id
                    # A lógica de prioridade foi removida, pois agora um produto
                    # não tem uma "prioridade dentro de uma categoria".
                    # A ordem dos produtos é gerenciada na própria categoria.
                )
            )

    if new_links:
        db.add_all(new_links)

    # 4. Salva todas as alterações no banco de dados.
    db.commit()

    # 5. Emite o evento para que as telas sejam atualizadas.
    # (Supondo que você tenha essas funções)

    await emit_updates_products(db, store.id)

    return

@router.post("/bulk-update-status", status_code=204)
async def bulk_update_product_status(
    store: GetStoreDep,
    db: GetDBDep,
    payload: BulkStatusUpdatePayload,
):
    """
    Ativa ou desativa uma lista de produtos de uma vez.
    """
    if not payload.product_ids:
        return # Não faz nada se a lista for vazia

    # Executa uma única query para atualizar todos os produtos de uma vez
    db.query(models.Product)\
      .filter(
          models.Product.store_id == store.id,
          models.Product.id.in_(payload.product_ids)
      )\
      .update({"available": payload.available}, synchronize_session=False)

    db.commit()

    await emit_updates_products(db, store.id)
    return