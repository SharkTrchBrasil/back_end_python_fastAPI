import asyncio
from decimal import Decimal

from fastapi import APIRouter, Form, HTTPException, File, UploadFile

from src.api import crud
from src.api.admin.socketio.emitters import admin_emit_store_updated, admin_emit_products_updated
from src.api.admin.utils.emit_updates import emit_updates_products
from src.api.app.socketio.socketio_emitters import emit_products_updated, emit_store_updated
from src.api.crud import crud_category, crud_option
from src.api.schemas.category import CategoryCreate, Category, OptionGroup, OptionGroupCreate, OptionItemCreate, \
    OptionItem, CategoryUpdate

from src.core import models
from src.core.aws import upload_file, delete_file
from src.core.database import GetDBDep
from src.core.dependencies import GetStoreDep
from src.core.utils.enums import CashbackType, CategoryType

router = APIRouter(tags=["Categories"], prefix="/stores/{store_id}/categories")


# --- ROTAS PARA CATEGORIAS ---

# ✨ 1. Alterado para async def e emitter adicionado
@router.post("", response_model=Category, status_code=201)
async def create_category_route(store_id: int, category_data: CategoryCreate,     db: GetDBDep,):
    # Primeiro, criamos a categoria no banco
    db_category = crud.crud_category.create_category(db=db, category_data=category_data, store_id=store_id)

    # ✨ Depois de salvar com sucesso, emitimos o evento
    await admin_emit_products_updated(db, store_id)

    # ✨ Por último, retornamos o resultado
    return db_category


@router.get("", response_model=list[Category])
def get_categories_route(store_id: int,     db: GetDBDep,):
    return crud.crud_category.get_all_categories(db, store_id=store_id)


@router.get("/{category_id}", response_model=Category)
def get_category_route(category_id: int, store_id: int,     db: GetDBDep,):
    db_category = crud.crud_category.get_category(db, category_id=category_id, store_id=store_id)
    if not db_category:
        raise HTTPException(status_code=404, detail="Category not found")
    return db_category


# --- ROTAS PARA GRUPOS DE OPÇÕES ---

# ✨ 2. Alterado para async def e emitter adicionado
@router.post("/{category_id}/option-groups", response_model=OptionGroup, status_code=201)
async def create_option_group_route(category_id: int, group_data: OptionGroupCreate,     db: GetDBDep,):
    # Precisamos saber o store_id para emitir o evento. Buscamos a categoria pai.
    category = crud.crud_category.get_category(db, category_id=category_id)
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")

    db_group = crud.crud_option.create_option_group(db=db, group_data=group_data, category_id=category_id)

    # Emitimos o evento para a loja correta
    await emit_updates_products(db, category.store_id)

    return db_group


# --- ROTAS PARA ITENS DE OPÇÃO ---

# ✨ 3. Alterado para async def e emitter adicionado
@router.post("/option-groups/{group_id}/items", response_model=OptionItem, status_code=201)
async def create_option_item_route(group_id: int, item_data: OptionItemCreate,     db: GetDBDep,):
    # Lógica similar para encontrar o store_id através do grupo pai
    group = crud.crud_option.get_option_group(db, group_id=group_id)
    if not group:
        raise HTTPException(status_code=404, detail="Option group not found")

    db_item = crud.crud_option.create_option_item(db=db, item_data=item_data, group_id=group_id)

    await emit_updates_products(db, group.category.store_id)

    return db_item



@router.get("", response_model=list[Category])
def get_categories(
        db: GetDBDep,
        store: GetStoreDep,
):
    db_categories = db.query(models.Category).filter(models.Category.store_id == store.id).all()
    return db_categories


@router.get("/{category_id}", response_model=Category)
def get_category(
        db: GetDBDep,
        store: GetStoreDep,
        category_id: int,
):
    db_category = db.query(models.Category).filter(
        models.Category.id == category_id,
        models.Category.store_id == store.id
    ).first()

    if not db_category:
        raise HTTPException(status_code=404, detail="Category not found")

    return db_category


# ...

@router.patch("/{category_id}", response_model=Category)
async def patch_category(
        category_id: int,
        update_data: CategoryUpdate,
        db: GetDBDep,
        store: GetStoreDep,
):
    db_category = crud.crud_category.get_category(db, category_id=category_id, store_id=store.id)

    if not db_category:
        raise HTTPException(status_code=404, detail="Category not found")

    update_dict = update_data.model_dump(exclude_unset=True)

    # ✨ LÓGICA ATUALIZADA ✨
    # Se 'is_active' está sendo alterado, usamos a função especial
    if 'is_active' in update_dict:
        crud.crud_category.update_category_status(
            db=db,
            db_category=db_category,
            is_active=update_data.is_active
        )
        # Removemos para não ser atualizado de novo
        update_dict.pop('is_active')

    # Atualiza os outros campos normalmente
    for key, value in update_dict.items():
        setattr(db_category, key, value)

    db.commit()
    db.refresh(db_category)

    # O evento de socket vai notificar o frontend sobre todas as mudanças
    await admin_emit_store_updated(db, store.id)

    return db_category


@router.delete("/{category_id}", status_code=204)
async def delete_category(
        category_id: int,
        db: GetDBDep,
        store: GetStoreDep,
):
    # 1. Busca a categoria no banco de dados
    category = db.query(models.Category).filter(
        models.Category.id == category_id,
        models.Category.store_id == store.id
    ).first()

    if not category:
        raise HTTPException(status_code=404, detail="Category not found")

    # 2. (Opcional, mas recomendado) Guarda a chave da imagem da categoria para deletar depois
    file_key_to_delete = category.file_key

    # 3. Deleta a categoria do banco.
    #    O SQLAlchemy/Banco de Dados irá automaticamente remover os 'product_links'
    #    graças à configuração 'cascade', mas NÃO irá deletar os produtos.
    db.delete(category)
    db.commit()

    # 4. Se havia uma imagem da categoria, deleta do seu serviço de arquivos (ex: S3)
    if file_key_to_delete:
        delete_file(file_key_to_delete)

    # 5. Emite o evento para notificar a UI que os dados da loja mudaram
    await emit_updates_products(db, store.id)  # ou admin_emit_store_updated

    # Com status_code=204, a resposta não tem corpo, então não há 'return'.
