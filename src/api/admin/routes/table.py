import uuid
from datetime import datetime, timezone
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload

from src.core import models
from src.core.database import GetDBDep
from src.core.dependencies import GetStoreDep, GetCurrentUserDep
from src.api.schemas.store import table as table_schemas
from src.core.utils.enums import Roles, TableStatus, CommandStatus, OrderStatus

router = APIRouter(prefix="/tables", tags=["Tables"])


# --- Endpoints para Salões (Saloons) ---

@router.post("/saloons", response_model=table_schemas.SaloonOut, status_code=status.HTTP_201_CREATED)
def create_saloon(
    store: GetStoreDep,
    saloon_data: table_schemas.SaloonCreate,
    db: GetDBDep,
    user: GetCurrentUserDep, # Garante autenticação
):
    """Cria um novo salão (ambiente) para a loja."""
    db_saloon = models.Saloon(**saloon_data.model_dump(), store_id=store.id)
    db.add(db_saloon)
    db.commit()
    db.refresh(db_saloon)
    # TODO: Emitir evento WebSocket para atualizar a UI em tempo real
    return db_saloon

@router.get("/saloons", response_model=List[table_schemas.SaloonOut])
def list_saloons(
    store: GetStoreDep,
    db: GetDBDep,
):
    """Lista todos os salões e suas respectivas mesas para a loja."""
    saloons = db.query(models.Saloon).filter(models.Saloon.store_id == store.id)\
        .options(joinedload(models.Saloon.tables).joinedload(models.Tables.commands))\
        .order_by(models.Saloon.display_order)\
        .all()
    return saloons

@router.put("/saloons/{saloon_id}", response_model=table_schemas.SaloonOut)
def update_saloon(
    saloon_id: int,
    saloon_data: table_schemas.SaloonUpdate,
    store: GetStoreDep,
    db: GetDBDep,
):
    """Atualiza os dados de um salão."""
    db_saloon = db.query(models.Saloon).filter(models.Saloon.id == saloon_id, models.Saloon.store_id == store.id).first()
    if not db_saloon:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Salão não encontrado.")

    update_data = saloon_data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_saloon, key, value)

    db.commit()
    db.refresh(db_saloon)
    # TODO: Emitir evento WebSocket
    return db_saloon

@router.delete("/saloons/{saloon_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_saloon(saloon_id: int, store: GetStoreDep, db: GetDBDep):
    """Deleta um salão e todas as suas mesas associadas (cascade)."""
    db_saloon = db.query(models.Saloon).filter(models.Saloon.id == saloon_id, models.Saloon.store_id == store.id).first()
    if not db_saloon:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Salão não encontrado.")

    db.delete(db_saloon)
    db.commit()
    # TODO: Emitir evento WebSocket
    return None

# --- Endpoints para Mesas (Tables) ---

@router.post("/tables", response_model=table_schemas.TableOut, status_code=status.HTTP_201_CREATED)
def create_table(
    store: GetStoreDep,
    table_data: table_schemas.TableCreate,
    db: GetDBDep,
):
    """Cria uma nova mesa em um salão específico."""
    # Valida se o salão pertence à loja
    saloon = db.query(models.Saloon).filter(models.Saloon.id == table_data.saloon_id, models.Saloon.store_id == store.id).first()
    if not saloon:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Salão inválido.")

    db_table = models.Tables(**table_data.model_dump(), store_id=store.id)
    db.add(db_table)
    db.commit()
    db.refresh(db_table)
    # TODO: Emitir evento WebSocket
    return db_table

@router.put("/tables/{table_id}", response_model=table_schemas.TableOut)
def update_table(
    table_id: int,
    table_data: table_schemas.TableUpdate,
    store: GetStoreDep,
    db: GetDBDep,
):
    """Atualiza os dados de uma mesa."""
    db_table = db.query(models.Tables).filter(models.Tables.id == table_id, models.Tables.store_id == store.id).first()
    if not db_table:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Mesa não encontrada.")

    update_data = table_data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_table, key, value)

    db.commit()
    db.refresh(db_table)
    # TODO: Emitir evento WebSocket
    return db_table

@router.delete("/tables/{table_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_table(table_id: int, store: GetStoreDep, db: GetDBDep):
    """Deleta uma mesa."""
    db_table = db.query(models.Tables).filter(models.Tables.id == table_id, models.Tables.store_id == store.id).first()
    if not db_table:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Mesa não encontrada.")

    # Soft delete ou hard delete? Por enquanto, hard delete.
    db.delete(db_table)
    db.commit()
    # TODO: Emitir evento WebSocket
    return None

# --- Endpoint para Lançar Itens ---

@router.post("/tables/{table_id}/add-item", response_model=table_schemas.TableOut)
def add_item_to_table(
    table_id: int,
    item_data: table_schemas.AddItemToCommandSchema,
    store: GetStoreDep,
    db: GetDBDep,
):
    """
    Adiciona um item a uma mesa. Cria uma comanda se não existir uma ativa.
    Esta é uma versão profissional e robusta da sua `TableService`.
    """
    # 1. Encontrar a mesa e carregar o relacionamento com as comandas
    table = db.query(models.Tables).options(joinedload(models.Tables.commands))\
        .filter(models.Tables.id == table_id, models.Tables.store_id == store.id).first()
    if not table:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Mesa não encontrada")

    # 2. Encontrar ou criar uma comanda ativa para a mesa
    command = next((c for c in table.commands if c.status == CommandStatus.ACTIVE), None)

    if not command:
        command = models.Command(store_id=store.id, table_id=table.id, status=CommandStatus.ACTIVE)
        db.add(command)
        db.flush()

    # 3. Encontrar o produto e validar
    # Usamos a tabela de link para pegar o preço correto para a categoria do produto!
    product_link = db.query(models.ProductCategoryLink)\
        .options(joinedload(models.ProductCategoryLink.product))\
        .filter(models.ProductCategoryLink.product_id == item_data.product_id)\
        .first() # Simplificação: pega o primeiro link encontrado. O ideal seria passar a category_id.

    if not product_link or not product_link.product:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Produto não encontrado ou não está em nenhuma categoria.")

    product = product_link.product
    price = product_link.price # Preço em centavos

    # 4. Criar o pedido (Order) associado à comanda
    # Nota: Este pedido é "virtual" até o fechamento da conta.
    total_price = price * item_data.quantity
    new_order = models.Order(
        store_id=store.id,
        command_id=command.id,
        table_id=table.id,
        order_type="in_store",
        delivery_type="mesa",
        order_status=OrderStatus.PREPARING, # Já entra em preparação
        payment_status="pending",
        total_price=total_price,
        subtotal_price=total_price,
        discounted_total_price=total_price,
        # Preencha campos desnormalizados para evitar joins complexos depois
        street=store.street,
        neighborhood=store.neighborhood,
        city=store.city,
        sequential_id=0, # Gerar depois
        public_id=str(uuid.uuid4()) # Gerar um ID público
    )
    db.add(new_order)
    db.flush()

    # 5. Criar o item do pedido (OrderProduct)
    order_product = models.OrderProduct(
        order_id=new_order.id,
        store_id=store.id,
        product_id=product.id,
        category_id=product_link.category_id,
        name=product.name,
        price=price,
        original_price=price,
        quantity=item_data.quantity,
        note=item_data.notes or ""
    )
    db.add(order_product)

    # 6. Atualizar o status da mesa e comanda
    if table.status == TableStatus.AVAILABLE:
        table.status = TableStatus.OCCUPIED
        table.opened_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(table)

    # TODO: Emitir evento WebSocket para atualizar a mesa na UI de todos os clients
    # Ex: `emit_table_updated(store.id, table_id, table_schema.dump(table))`

    return  #tabletus_code=400, detail=str(e))