from typing import List
from fastapi import APIRouter, Form, UploadFile, File, HTTPException

from pydantic import ValidationError


from starlette import status

from src.api.admin.routes import product_category_link
from src.api.admin.utils.emit_updates import emit_updates_products
from src.api.crud import crud_product

from src.api.schemas.products.bulk_actions import BulkDeletePayload, BulkStatusUpdatePayload, BulkCategoryUpdatePayload

from src.api.schemas.products.product import (
    ProductOut,
    ProductUpdate,
    FlavorWizardCreate,
    SimpleProductWizardCreate,
    FlavorPriceUpdate  # Precisaremos de um novo schema para o update de preço
)
from src.api.schemas.products.product_category_link import ProductCategoryLinkUpdate, ProductCategoryLinkOut
from src.core import models
from src.core.aws import delete_file, upload_single_file, delete_multiple_files
from src.core.database import GetDBDep
from src.core.dependencies import GetStoreDep, GetProductDep
from src.core.utils.enums import ProductStatus

router = APIRouter(prefix="/stores/{store_id}/products", tags=["Products"])


# ===================================================================
# ROTA 1: CRIAR PRODUTO SIMPLES (Ex: Bebidas, Lanches)
# ===================================================================

@router.post("/simple-product", response_model=ProductOut, status_code=201)
async def create_simple_product(
        store: GetStoreDep,
        db: GetDBDep,
        payload_str: str = Form(..., alias="payload"),

        images: List[UploadFile] = File([], alias="images"),
):
    """Cria um produto simples com imagem de capa e galeria."""
    try:
        payload = SimpleProductWizardCreate.model_validate_json(payload_str)
    except ValidationError as e:
        raise HTTPException(status_code=422, detail=f"JSON inválido: {e}")


    # 2. Cria o produto principal com os dados do payload
    product_data = payload.model_dump(exclude={'category_links', 'variant_links'})
    new_product = models.Product(**product_data, store_id=store.id)
    db.add(new_product)
    db.flush()


    if images:
        for index, image_file in enumerate(images):
            gallery_file_key = upload_single_file(image_file, folder="products/gallery")
            if gallery_file_key:
                db.add(models.ProductImage(
                    product_id=new_product.id,
                    file_key=gallery_file_key,
                    display_order=index
                ))

    # 4. Cria os vínculos com categorias e complementos (sua lógica original)
    if payload.category_links:
        for link_data in payload.category_links:
            db.add(models.ProductCategoryLink(product_id=new_product.id, **link_data.model_dump()))

    # 3. ✅ LÓGICA INTELIGENTE PARA GRUPOS DE COMPLEMENTOS (variant_links)
    if payload.variant_links:
        for link_data in payload.variant_links:
            variant_data = link_data.variant

            # Se o ID da variante for > 0, é um grupo existente. Apenas vincula.
            if variant_data.id and variant_data.id > 0:
                db.add(models.ProductVariantLink(
                    product_id=new_product.id,
                    variant_id=variant_data.id,
                    min_selected_options=link_data.min_selected_options,
                    max_selected_options=link_data.max_selected_options,
                    ui_display_mode=link_data.ui_display_mode,
                    available=link_data.available
                ))
            else:
                # Se o ID for negativo/nulo, é um GRUPO NOVO. Precisamos criar tudo.

                # a. Cria o Variant (o grupo)
                new_variant = models.Variant(
                    name=variant_data.name,
                    type=variant_data.type.value,
                    store_id=store.id
                )
                db.add(new_variant)
                db.flush()  # Para obter o ID do novo variant

                # b. Cria as VariantOptions (os itens do grupo)
                if variant_data.options:
                    for option_data in variant_data.options:
                        db.add(models.VariantOption(
                            variant_id=new_variant.id,
                            **option_data.model_dump(exclude={'image', 'variant_id'})
                        ))

                # c. Cria o Vínculo entre o produto e o grupo recém-criado
                db.add(models.ProductVariantLink(
                    product_id=new_product.id,
                    variant_id=new_variant.id,
                    min_selected_options=link_data.min_selected_options,
                    max_selected_options=link_data.max_selected_options,
                    ui_display_mode=link_data.ui_display_mode,
                    available=link_data.available
                ))

    # 4. Salva tudo no banco de dados
    db.commit()
    db.refresh(new_product)
    await emit_updates_products(db, store.id)
    return new_product


# ===================================================================
# ROTA 2: CRIAR "SABOR" (PRODUTO CUSTOMIZÁVEL)
# ===================================================================
@router.post("/flavor-product", response_model=ProductOut, status_code=201)
async def create_flavor_product(
        store: GetStoreDep,
        db: GetDBDep,
        payload_str: str = Form(..., alias="payload"),

        images: List[UploadFile] = File([], alias="images"),
):
    """Cria um produto do tipo 'sabor' com imagem de capa e galeria."""
    try:
        payload = FlavorWizardCreate.model_validate_json(payload_str)
    except ValidationError as e:
        raise HTTPException(status_code=422, detail=f"JSON inválido: {e}")

    parent_category = db.query(models.Category).filter(models.Category.id == payload.parent_category_id,
                                                       models.Category.store_id == store.id).first()
    if not parent_category:
        raise HTTPException(status_code=404, detail="Categoria pai não encontrada.")



    # 2. Prepara os dados do produto para criação
    product_data = payload.model_dump(exclude={'prices', 'parent_category_id'})

    # ✅ 3. Cria o novo produto usando a chave da imagem de capa
    new_product = models.Product(**product_data, store_id=store.id)
    db.add(new_product)
    db.flush()

    # 2. Faz o upload de TODAS as imagens recebidas e as salva na galeria.
    #    A ordem em que o frontend envia determinará a 'display_order'.
    if images:
        for index, image_file in enumerate(images):
            gallery_file_key = upload_single_file(image_file, folder="products/gallery")
            if gallery_file_key:
                db.add(models.ProductImage(
                    product_id=new_product.id,
                    file_key=gallery_file_key,
                    display_order=index
                ))

    # 5. Cria o vínculo com a categoria pai e os preços (sua lógica original)
    db.add(models.ProductCategoryLink(product_id=new_product.id, category_id=payload.parent_category_id, price=0))

    for price_data in payload.prices:
        db.add(models.FlavorPrice(product_id=new_product.id, **price_data.model_dump()))

    # 6. Salva tudo no banco
    db.commit()
    db.refresh(new_product)
    await emit_updates_products(db, store.id)
    return new_product


# ===================================================================
# ROTA 3: ATUALIZAÇÃO UNIFICADA DE DADOS BÁSICOS (PATCH)
# ===================================================================


@router.patch("/{product_id}", response_model=ProductOut)
async def update_product(
        store: GetStoreDep,
        db: GetDBDep,
        db_product: GetProductDep,
        payload_str: str = Form(..., alias="payload"),
        # ✅ RECEBE A LISTA DE NOVAS IMAGENS
        images: List[UploadFile] = File([], alias="images"),
):
    try:
        update_data = ProductUpdate.model_validate_json(payload_str)
    except ValidationError as e:
        raise HTTPException(status_code=422, detail=f"JSON inválido: {e}")

    # ✅ Processar as novas imagens
    new_gallery_file_keys = []

    if images:
        for image_file in images:
            file_key = upload_single_file(image_file, folder="products/gallery")
            if file_key:
                new_gallery_file_keys.append(file_key)
                print(f"✅ Nova imagem salva no S3: {file_key}")

    # --- Chama a função do CRUD, passando as novas chaves ---
    updated_product, file_keys_to_delete = crud_product.update_product(
        db=db,
        db_product=db_product,
        update_data=update_data,
        store_id=store.id,
        new_gallery_file_keys=new_gallery_file_keys  # ✅ Passa as novas chaves
    )

    # --- Deleta do S3 os arquivos marcados para exclusão ---
    if file_keys_to_delete:
        delete_multiple_files(file_keys_to_delete)

    await emit_updates_products(db, store.id)
    return updated_product




# ===================================================================
# ROTAS PARA ATUALIZAÇÃO DE PREÇOS
# ===================================================================

@router.patch("/{product_id}/categories/{category_id}", response_model=ProductCategoryLinkOut)
async def update_simple_product_price(
        store: GetStoreDep,
        product_id: int,
        category_id: int,
        update_data: ProductCategoryLinkUpdate,
        db: GetDBDep,
):
    """Atualiza o preço/promoção de um produto simples em uma categoria específica."""
    db_link = db.query(models.ProductCategoryLink).filter(
        models.ProductCategoryLink.product_id == product_id,
        models.ProductCategoryLink.category_id == category_id
    ).first()
    if not db_link:
        raise HTTPException(status_code=404, detail="Vínculo produto-categoria não encontrado.")

    for field, value in update_data.model_dump(exclude_unset=True).items():
        setattr(db_link, field, value)

    db.commit()
    db.refresh(db_link)
    await emit_updates_products(db, store.id)
    return db_link


@router.patch("/prices/{flavor_price_id}", response_model=ProductOut)
async def update_flavor_price(
        store: GetStoreDep,
        flavor_price_id: int,
        update_data: FlavorPriceUpdate,
        db: GetDBDep,
):
    """Atualiza o preço de um sabor para um tamanho específico."""
    db_price_link = db.query(models.FlavorPrice).join(models.Product).filter(
        models.FlavorPrice.id == flavor_price_id,
        models.Product.store_id == store.id
    ).first()
    if not db_price_link:
        raise HTTPException(status_code=404, detail="Preço para este tamanho não encontrado.")

    db_price_link.price = update_data.price
    db.commit()

    product_to_return = db.query(models.Product).get(db_price_link.product_id)
    db.refresh(product_to_return)
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
    # ✅ A FUNÇÃO DO CRUD AGORA TEM O FILTRO EMBUTIDO
    products = crud_product.get_all_products_for_store(
        db=db,
        store_id=store.id,
        skip=skip,
        limit=limit
    )
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



@router.patch(
    "/{product_id}/categories/{category_id}/availability",
    response_model=ProductCategoryLinkOut,
    summary="Ativa ou pausa um produto em uma categoria específica"
)
async def toggle_product_availability_in_category(
        store: GetStoreDep,
        product_id: int,
        category_id: int,
        payload: ProductCategoryLinkUpdate,  # Reutilizamos o schema, esperando { "is_available": true/false }
        db: GetDBDep,
):
    """
    Atualiza a disponibilidade de um produto em uma categoria específica.
    Se o produto estiver sendo ativado no vínculo, também garante que o
    status geral do produto seja ACTIVE.
    """
    # Chama a nova função do CRUD que contém a lógica inteligente
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





@router.patch("/{product_id}/archive", status_code=status.HTTP_204_NO_CONTENT)
async def archive_product(
    store: GetStoreDep,
    db: GetDBDep,
    db_product: GetProductDep
):
    """
    Arquiva um produto (soft delete), mudando seu status para ARCHIVED.
    O produto não será mais listado nas telas principais.
    """
    if db_product.status == ProductStatus.ARCHIVED:
        # Se já está arquivado, não faz nada.
        return

    # Chama a função do CRUD para fazer a alteração
    crud_product.archive_product(db=db, db_product=db_product)

    await emit_updates_products(db, store.id)
    return
# Em seu arquivo de rotas de produtos

# @router.post("/bulk-delete", status_code=204)
# async def bulk_delete_products(
#     store: GetStoreDep,
#     db: GetDBDep,
#     payload: BulkDeletePayload,
# ):
#     """
#     Remove uma lista de produtos. A exclusão em cascata é gerenciada
#     pelo banco de dados através da configuração ON DELETE CASCADE.
#     """
#     if not payload.product_ids:
#         return
#
#     # 1. Busca os produtos para pegar os file_keys antes de deletar.
#     products_to_delete = db.query(models.Product).filter(
#         models.Product.store_id == store.id,
#         models.Product.id.in_(payload.product_ids)
#     ).all()
#
#     if not products_to_delete:
#         return
#
#     file_keys_to_delete = [p.file_key for p in products_to_delete if p.file_key]
#     valid_product_ids = [p.id for p in products_to_delete]
#
#     # 2. Executa UM ÚNICO comando de exclusão em massa. O banco cuida do resto.
#     db.query(models.Product).filter(models.Product.id.in_(valid_product_ids)).delete(synchronize_session=False)
#
#     # 3. Commita a transação.
#     db.commit()
#
#     # 4. Apaga os arquivos do S3.
#     for key in file_keys_to_delete:
#         try:
#             delete_file(key)
#         except Exception as e:
#             print(f"Alerta: Falha ao deletar o arquivo {key} do S3. Erro: {e}")
#
#     # 5. Notifica a UI.
#     await emit_updates_products(db, store.id)
#     return


# ✅ ADICIONE A NOVA ROTA PARA ARQUIVAR EM MASSA
@router.post("/bulk-archive", status_code=status.HTTP_204_NO_CONTENT)
async def bulk_archive_products(
    store: GetStoreDep,
    db: GetDBDep,
    payload: BulkDeletePayload, # Podemos reutilizar o mesmo payload
):
    """
    Arquiva uma lista de produtos de uma vez.
    """
    if not payload.product_ids:
        return

    # Chama a função do CRUD que faz a atualização em massa
    crud_product.bulk_archive_products(
        db=db,
        store_id=store.id,
        product_ids=payload.product_ids
    )

    await emit_updates_products(db, store.id)
    return

@router.post("/bulk-update-category", response_model=dict, status_code=200)
async def bulk_update_product_category(
        store: GetStoreDep,
        db: GetDBDep,
        payload: BulkCategoryUpdatePayload,  # <-- Usa o schema que espera a lista de produtos com preços
):
    """
    MOVE uma lista de produtos para uma nova categoria, apagando TODOS
    os vínculos antigos e criando novos com os preços e códigos PDV fornecidos pelo frontend.
    """

    # 1. Chama a nova e poderosa função do CRUD que faz o trabalho pesado
    #    de apagar os vínculos antigos e criar os novos com os dados do payload.
    crud_product.bulk_update_product_category(
        db=db,
        store_id=store.id,
        payload=payload
    )

    # 2. Após o sucesso da operação no banco, emite o evento para que
    #    as telas do admin e do totem sejam atualizadas em tempo real.
    await emit_updates_products(db, store.id)

    # 3. Retorna uma mensagem de sucesso para o app.
    return {"message": "Produtos movidos e reprecificados com sucesso"}



@router.post("/bulk-update-status", status_code=204)
async def bulk_update_product_status(
    store: GetStoreDep,
    db: GetDBDep,
    payload: BulkStatusUpdatePayload,
):
    """
    Ativa ou desativa (muda o status para ACTIVE ou INACTIVE) uma lista de produtos.
    """
    if not payload.product_ids:
        return


    new_status = ProductStatus.ACTIVE if payload.available else ProductStatus.INACTIVE  # <--- Linha corrigida


    db.query(models.Product)\
      .filter(
          models.Product.store_id == store.id,
          models.Product.id.in_(payload.product_ids)
      )\
      .update(
          {"status": new_status}, # ✅ Atualiza a coluna 'status'
          synchronize_session=False
      )

    db.commit()
    await emit_updates_products(db, store.id)
    return


@router.delete(
    "/{product_id}/categories/{category_id}",
    status_code=204,
    summary="Remove a product from a specific category"
)
async def remove_product_from_category_route(
    product_id: int,
    category_id: int,
    store: GetStoreDep,
    db: GetDBDep,
):
    """
    Desvincula um produto de uma categoria sem apagar o produto do sistema.
    O produto pode se tornar "órfão" se esta for sua última categoria.
    """
    rows_deleted = crud_product.remove_product_from_category(
        db=db,
        store_id=store.id,
        product_id=product_id,
        category_id=category_id
    )

    if rows_deleted == 0:
        # Isso pode acontecer se o link já foi removido ou nunca existiu.
        # Não é um erro crítico, mas é bom saber.
        print(f"Nenhum vínculo encontrado para o produto {product_id} na categoria {category_id}.")

    # Sempre notifica a UI para refletir a mudança
    await emit_updates_products(db, store.id)
    return




@router.post("/bulk-add-update-links", status_code=status.HTTP_200_OK)
async def bulk_add_products_to_category(
    *,
    db: GetDBDep,
    store: GetStoreDep,
    # Podemos reutilizar o mesmo Pydantic model que a rota de "mover" usa
    payload: BulkCategoryUpdatePayload
):
    """
    Adiciona ou atualiza múltiplos produtos em uma categoria,
    SEM remover seus vínculos com outras categorias.
    """
    crud_product.bulk_add_or_update_links(
        db=db,
        store_id=store.id,
        target_category_id=payload.target_category_id,
        products_data=payload.products
    )

    # Sempre notifica a UI para refletir a mudança
    await emit_updates_products(db, store.id)
    return





@router.delete("/{variant_id}", status_code=204)
def unlink_variant_from_product(
    db: GetDBDep,
    store: GetStoreDep,
    product: GetProductDep,
    variant_id: int,
):
    """
    Remove o vínculo entre um produto específico e um grupo de complementos.
    """
    # Busca o vínculo específico no banco de dados
    link_to_delete = db.query(models.ProductVariantLink).filter(
        models.ProductVariantLink.product_id == product.id,
        models.ProductVariantLink.variant_id == variant_id
    ).first()

    # Se o vínculo não existir, retorna um erro 404
    if not link_to_delete:
        raise HTTPException(status_code=404, detail="Vínculo entre produto e grupo não encontrado.")

    # Se encontrou, deleta o vínculo e salva as alterações
    db.delete(link_to_delete)
    db.commit()

    return None # Retorna 204 No Content em caso de sucesso






















router.include_router(
    product_category_link.router,
    prefix="/{product_id}/categories"
)