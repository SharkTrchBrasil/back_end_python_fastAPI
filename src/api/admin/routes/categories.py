# src/api/admin/routes/categories.py

from fastapi import APIRouter, HTTPException, UploadFile, File, Request
from sqlalchemy.orm import selectinload

from src.api.admin.socketio.emitters import emit_updates_products
from src.api.crud import crud_category, crud_option
from src.api.schemas.products.category import (
    CategoryCreate, Category, OptionGroup, OptionGroupCreate,
    OptionItemCreate, OptionItem, CategoryUpdate
)
from src.core.aws import delete_file, upload_single_file
from src.core.database import GetDBDep
from src.core.dependencies import GetStoreDep, GetCurrentUserDep, GetAuditLoggerDep
from src.core.utils.enums import AuditAction, AuditEntityType

# Roteador principal com o prefixo da loja
router = APIRouter(tags=["Categories"], prefix="/stores/{store_id}/categories")

# Roteador secundário SEM prefixo, para rotas que operam em recursos aninhados
nested_router = APIRouter(tags=["Categories Nested"])


# ═══════════════════════════════════════════════════════════════════════════════
# 🔥 ROTAS ANINHADAS (OPTION ITEMS)
# ═══════════════════════════════════════════════════════════════════════════════

@nested_router.post("/option-items/{item_id}/image", response_model=OptionItem, status_code=200)
async def upload_option_item_image(
        request: Request,
        item_id: int,
        db: GetDBDep,
        user: GetCurrentUserDep,  # ✅ ADICIONAR
        audit: GetAuditLoggerDep,  # ✅ ADICIONAR
        image_file: UploadFile = File(...)
):
    """
    ✅ Faz upload de imagem para um item de opção (ex: foto da "Borda Catupiry")
    """

    # 1. Busca o item pelo ID
    db_item = crud_option.get_option_item(db, item_id=item_id)
    if not db_item:
        # ✅ LOG DE ERRO
        audit.log_failed_action(
            action=AuditAction.UPDATE_CATEGORY,
            entity_type=AuditEntityType.CATEGORY,
            error=f"Option Item não encontrado: ID {item_id}"
        )
        db.commit()

        raise HTTPException(status_code=404, detail="Option Item not found")

    # 2. A partir do item, encontramos a loja para validação e para o caminho do S3
    store_id = db_item.group.category.store_id

    # ✅ CAPTURA ESTADO ANTERIOR
    old_file_key = db_item.file_key

    # 3. Se já houver uma imagem antiga, apaga ela do S3
    if old_file_key:
        delete_file(old_file_key)

    # 4. Faz o upload do novo arquivo
    folder_path = f"stores/{store_id}/option-items/{db_item.id}"
    file_key = upload_single_file(file=image_file, folder=folder_path)

    if not file_key:
        # ✅ LOG DE ERRO DE UPLOAD
        audit.log_failed_action(
            action=AuditAction.UPDATE_CATEGORY,
            entity_type=AuditEntityType.CATEGORY,
            error=f"Falha no upload de imagem para Option Item ID {item_id}"
        )
        db.commit()

        raise HTTPException(status_code=500, detail="Failed to upload image to S3")

    # 5. Atualiza o banco de dados com a nova file_key
    db_item.file_key = file_key

    # ✅ LOG DE UPLOAD BEM-SUCEDIDO
    audit.log(
        action=AuditAction.UPDATE_CATEGORY,
        entity_type=AuditEntityType.CATEGORY,
        entity_id=db_item.group.category_id,
        changes={
            "option_item_id": item_id,
            "option_item_name": db_item.name,
            "old_file_key": old_file_key,
            "new_file_key": file_key,
            "category_id": db_item.group.category_id,
            "category_name": db_item.group.category.name
        },
        description=f"Imagem do item '{db_item.name}' atualizada na categoria '{db_item.group.category.name}'"
    )

    db.commit()
    db.refresh(db_item)

    # 6. Emite a atualização e retorna o objeto completo
    await emit_updates_products(db, store_id)
    return db_item


@nested_router.post("/option-groups/{group_id}/items", response_model=OptionItem, status_code=201)
async def create_option_item_route(
        request: Request,
        group_id: int,
        item_data: OptionItemCreate,
        db: GetDBDep,
        user: GetCurrentUserDep,  # ✅ ADICIONAR
        audit: GetAuditLoggerDep,  # ✅ ADICIONAR
):
    """
    ✅ Cria um novo item de opção (ex: "Borda Catupiry" no grupo "Bordas")
    """

    group = crud_option.get_option_group(db, group_id=group_id)
    if not group:
        # ✅ LOG DE ERRO
        audit.log_failed_action(
            action=AuditAction.CREATE_CATEGORY,
            entity_type=AuditEntityType.CATEGORY,
            error=f"Option Group não encontrado: ID {group_id}"
        )
        db.commit()

        raise HTTPException(status_code=404, detail="Option group not found")

    db_item = crud_option.create_option_item(db=db, item_data=item_data, group_id=group_id)

    # ✅ LOG DE CRIAÇÃO BEM-SUCEDIDA
    audit.log(
        action=AuditAction.CREATE_CATEGORY,
        entity_type=AuditEntityType.CATEGORY,
        entity_id=group.category_id,
        changes={
            "option_item_id": db_item.id,
            "option_item_name": db_item.name,
            "option_item_price": float(db_item.price) / 100 if db_item.price else 0,
            "group_id": group_id,
            "group_name": group.name,
            "category_id": group.category_id,
            "category_name": group.category.name
        },
        description=f"Item '{db_item.name}' criado no grupo '{group.name}' da categoria '{group.category.name}'"
    )

    db.commit()

    await emit_updates_products(db, group.category.store_id)
    return db_item


# ═══════════════════════════════════════════════════════════════════════════════
# 🔥 PONTO VITAL 1: CRIAR CATEGORIA
# ═══════════════════════════════════════════════════════════════════════════════

@router.post("", response_model=Category, status_code=201)
async def create_category(
        request: Request,
        category_data: CategoryCreate,
        db: GetDBDep,
        store: GetStoreDep,
        user: GetCurrentUserDep,  # ✅ ADICIONAR
        audit: GetAuditLoggerDep,  # ✅ ADICIONAR
):
    """
    ✅ Cria uma nova categoria com auditoria completa

    - Registra quem criou
    - Rastreia grupos de opções criados junto
    - Monitora preços e configurações
    """

    db_category = crud_category.create_category(db=db, category_data=category_data, store_id=store.id)

    # ✅ LOG DE CRIAÇÃO BEM-SUCEDIDA
    audit.log(
        action=AuditAction.CREATE_CATEGORY,
        entity_type=AuditEntityType.CATEGORY,
        entity_id=db_category.id,
        changes={
            "store_name": store.name,
            "category_name": db_category.name,
            "category_type": db_category.type,
            "is_pizza": db_category.is_pizza,
            "option_groups_count": len(category_data.option_groups) if category_data.option_groups else 0,
            "option_groups": [
                {
                    "name": group.name,
                    "min_selection": group.min_selection,
                    "max_selection": group.max_selection,
                    "items_count": len(group.items) if group.items else 0
                }
                for group in (category_data.option_groups or [])
            ]
        },
        description=f"Categoria '{db_category.name}' criada com {len(category_data.option_groups or [])} grupos de opções"
    )

    db.commit()

    await emit_updates_products(db, store.id)
    return db_category


# ═══════════════════════════════════════════════════════════════════════════════
# ROTAS DE LEITURA - SEM AUDITORIA (NÃO SÃO CRÍTICAS)
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("", response_model=list[Category])
def get_categories(db: GetDBDep, store: GetStoreDep):
    """Lista todas as categorias da loja."""
    return crud_category.get_all_categories(db, store_id=store.id)


@router.get("/{category_id}", response_model=Category)
def get_category(category_id: int, db: GetDBDep, store: GetStoreDep):
    """Busca uma categoria específica."""
    db_category = crud_category.get_category(db, category_id=category_id, store_id=store.id)
    if not db_category:
        raise HTTPException(status_code=404, detail="Category not found")
    return db_category


# ═══════════════════════════════════════════════════════════════════════════════
# 🔥 PONTO VITAL 2: ATUALIZAR CATEGORIA
# ═══════════════════════════════════════════════════════════════════════════════

@router.patch("/{category_id}", response_model=Category)
async def update_category(
        request: Request,
        category_id: int,
        update_data: CategoryUpdate,
        db: GetDBDep,
        store: GetStoreDep,
        user: GetCurrentUserDep,  # ✅ ADICIONAR
        audit: GetAuditLoggerDep,  # ✅ ADICIONAR
):
    """
    ✅ Atualiza uma categoria com auditoria de mudanças

    - Rastreia todas as alterações
    - Registra mudanças em grupos de opções
    - Monitora ativação/desativação
    """

    db_category = crud_category.get_category(db, category_id=category_id, store_id=store.id)
    if not db_category:
        # ✅ LOG DE ERRO
        audit.log_failed_action(
            action=AuditAction.UPDATE_CATEGORY,
            entity_type=AuditEntityType.CATEGORY,
            entity_id=category_id,
            error="Categoria não encontrada"
        )
        db.commit()

        raise HTTPException(status_code=404, detail="Category not found")

    # ✅ CAPTURA ESTADO ANTERIOR
    old_values = {
        "name": db_category.name,
        "category_type": db_category.type,
        "is_pizza": db_category.is_pizza,
        "priority": db_category.priority,
        "is_active": db_category.is_active,
        "option_groups_count": len(db_category.option_groups) if db_category.option_groups else 0
    }

    # Aplica atualizações
    updated_category = crud_category.update_category(db=db, db_category=db_category, update_data=update_data)

    # ✅ DETECTA MUDANÇAS
    changes = {}

    if updated_category.name != old_values["name"]:
        changes["name_changed"] = {
            "from": old_values["name"],
            "to": updated_category.name
        }

    if updated_category.is_active != old_values["is_active"]:
        changes["status_changed"] = {
            "from": "ativa" if old_values["is_active"] else "inativa",
            "to": "ativa" if updated_category.is_active else "inativa"
        }

    if updated_category.priority != old_values["priority"]:
        changes["priority_changed"] = {
            "from": old_values["priority"],
            "to": updated_category.priority
        }

    new_groups_count = len(updated_category.option_groups) if updated_category.option_groups else 0
    if new_groups_count != old_values["option_groups_count"]:
        changes["option_groups_count"] = {
            "from": old_values["option_groups_count"],
            "to": new_groups_count
        }

    # ✅ LOG DE ATUALIZAÇÃO BEM-SUCEDIDA
    action_type = (
        AuditAction.ACTIVATE_CATEGORY if changes.get("status_changed", {}).get("to") == "ativa" and old_values[
            "is_active"] == False
        else AuditAction.DEACTIVATE_CATEGORY if changes.get("status_changed", {}).get("to") == "inativa" and old_values[
            "is_active"] == True
        else AuditAction.UPDATE_CATEGORY
    )

    audit.log(
        action=action_type,
        entity_type=AuditEntityType.CATEGORY,
        entity_id=category_id,
        changes={
            "store_name": store.name,
            "category_name": updated_category.name,
            "old_values": old_values,
            "changes": changes
        },
        description=f"Categoria '{updated_category.name}' atualizada"
    )

    db.commit()

    await emit_updates_products(db, store.id)
    return updated_category


# ═══════════════════════════════════════════════════════════════════════════════
# 🔥 PONTO VITAL 3: DELETAR CATEGORIA (CRÍTICO!)
# ═══════════════════════════════════════════════════════════════════════════════

@router.delete("/{category_id}", status_code=204)
async def delete_category(
        request: Request,
        category_id: int,
        db: GetDBDep,
        store: GetStoreDep,
        user: GetCurrentUserDep,  # ✅ ADICIONAR
        audit: GetAuditLoggerDep,  # ✅ ADICIONAR
):
    """
    ✅ Deleta uma categoria com auditoria completa

    ⚠️ ATENÇÃO: Ação irreversível e de ALTO IMPACTO
    - Pode afetar múltiplos produtos
    - Remove grupos de opções e itens
    - Pode quebrar o cardápio
    """

    db_category = crud_category.get_category(db, category_id=category_id, store_id=store.id)
    if not db_category:
        # ✅ LOG DE ERRO
        audit.log_failed_action(
            action=AuditAction.DELETE_CATEGORY,
            entity_type=AuditEntityType.CATEGORY,
            entity_id=category_id,
            error="Categoria não encontrada"
        )
        db.commit()

        raise HTTPException(status_code=404, detail="Category not found")

    # ✅ CAPTURA DADOS ANTES DE DELETAR (para auditoria forense)
    category_data = {
        "category_id": db_category.id,
        "name": db_category.name,
        "category_type": db_category.type,
        "is_pizza": db_category.is_pizza,
        "priority": db_category.priority,
        "is_active": db_category.is_active,
        "option_groups": [
            {
                "id": group.id,
                "name": group.name,
                "min_selection": group.min_selection,
                "max_selection": group.max_selection,
                "items_count": len(group.items) if group.items else 0,
                "items": [
                    {
                        "id": item.id,
                        "name": item.name,
                        "price": float(item.price) / 100 if item.price else 0
                    }
                    for item in (group.items or [])
                ]
            }
            for group in (db_category.option_groups or [])
        ]
    }

    # ✅ VERIFICA SE HÁ PRODUTOS VINCULADOS
    from src.core import models
    linked_products_count = db.query(models.ProductCategoryLink).filter(
        models.ProductCategoryLink.category_id == category_id
    ).count()

    category_data["linked_products_count"] = linked_products_count

    # ✅ DELETA IMAGEM DO S3 SE HOUVER
    if db_category.file_key:
        delete_file(db_category.file_key)
        category_data["deleted_file_key"] = db_category.file_key

    # ✅ LOG DE DELEÇÃO (CRÍTICO - REGISTRA TUDO)
    audit.log(
        action=AuditAction.DELETE_CATEGORY,
        entity_type=AuditEntityType.CATEGORY,
        entity_id=category_id,
        changes={
            "deleted_by": user.name,
            "store_name": store.name,
            "category_data": category_data,
            "impact_warning": f"⚠️ ATENÇÃO: {linked_products_count} produtos estavam vinculados a esta categoria"
        },
        description=f"⚠️ Categoria '{db_category.name}' DELETADA - {linked_products_count} produtos afetados"
    )

    db.delete(db_category)
    db.commit()

    await emit_updates_products(db, store.id)


# ═══════════════════════════════════════════════════════════════════════════════
# 🔥 PONTO VITAL 4: CRIAR GRUPO DE OPÇÕES
# ═══════════════════════════════════════════════════════════════════════════════

@router.post("/{category_id}/option-groups", response_model=OptionGroup, status_code=201)
async def create_option_group_route(
        request: Request,
        category_id: int,
        group_data: OptionGroupCreate,
        db: GetDBDep,
        store: GetStoreDep,
        user: GetCurrentUserDep,  # ✅ ADICIONAR
        audit: GetAuditLoggerDep,  # ✅ ADICIONAR
):
    """
    ✅ Cria um novo grupo de opções (ex: "Tamanhos", "Bordas", "Sabores")
    """

    category = crud_category.get_category(db, category_id=category_id, store_id=store.id)
    if not category:
        # ✅ LOG DE ERRO
        audit.log_failed_action(
            action=AuditAction.CREATE_CATEGORY,
            entity_type=AuditEntityType.CATEGORY,
            error=f"Categoria não encontrada: ID {category_id}"
        )
        db.commit()

        raise HTTPException(status_code=404, detail="Category not found in this store")

    db_group = crud_option.create_option_group(db=db, group_data=group_data, category_id=category_id)

    # ✅ LOG DE CRIAÇÃO BEM-SUCEDIDA
    audit.log(
        action=AuditAction.CREATE_CATEGORY,
        entity_type=AuditEntityType.CATEGORY,
        entity_id=category_id,
        changes={
            "store_name": store.name,
            "category_name": category.name,
            "group_id": db_group.id,
            "group_name": db_group.name,
            "min_selection": db_group.min_selection,
            "max_selection": db_group.max_selection,
            "items_count": len(group_data.items) if group_data.items else 0,
            "items": [
                {
                    "name": item.name,
                    "price": float(item.price) / 100 if item.price else 0
                }
                for item in (group_data.items or [])
            ]
        },
        description=f"Grupo '{db_group.name}' criado na categoria '{category.name}' com {len(group_data.items or [])} itens"
    )

    db.commit()

    await emit_updates_products(db, store.id)
    return db_group