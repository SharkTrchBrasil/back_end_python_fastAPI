# seu_projeto/src/api/crud/crud_category.py
from sqlalchemy.orm import Session, selectinload
from src.api.schemas.products.category import CategoryCreate, CategoryUpdate  # Importe o CategoryUpdate
from src.core import models
import logging

# É uma boa prática usar logging em vez de print
logger = logging.getLogger(__name__)


# --- FUNÇÃO DE CRIAÇÃO REFINADA ---
def create_category(db, category_data: CategoryCreate, store_id: int):
    # Separa os dados aninhados dos dados principais
    option_groups_data = category_data.option_groups or []
    schedules_data = category_data.schedules or []
    category_dict = category_data.model_dump(exclude={'option_groups', 'schedules'})

    # Define a prioridade de forma mais segura
    max_priority = db.query(models.func.max(models.Category.priority)).filter(
        models.Category.store_id == store_id).scalar()

    db_category = models.Category(
        **category_dict,
        store_id=store_id,
        priority=(max_priority or 0) + 1
    )
    db.add(db_category)
    db.flush()  # Obtém o ID da categoria

    # --- Cria os OptionGroups e seus Itens (sua lógica está boa) ---
    for group_data in option_groups_data:
        items_data = group_data.items or []
        group_dict = group_data.model_dump(exclude={'items'})
        db_group = models.OptionGroup(**group_dict, category_id=db_category.id)
        db.add(db_group)
        db.flush()
        for item_data in items_data:
            db_item = models.OptionItem(**item_data.model_dump(), option_group_id=db_group.id)
            db.add(db_item)

    # --- ✨ LÓGICA ADICIONADA: Cria os Schedules e seus TimeShifts ---
    for schedule_data in schedules_data:
        shifts_data = schedule_data.time_shifts or []
        schedule_dict = schedule_data.model_dump(exclude={'time_shifts'})
        db_schedule = models.CategorySchedule(**schedule_dict, category_id=db_category.id)
        db.add(db_schedule)
        db.flush()
        for shift_data in shifts_data:
            db_shift = models.TimeShift(**shift_data.model_dump(), schedule_id=db_schedule.id)
            db.add(db_shift)

    db.commit()
    db.refresh(db_category)
    return db_category


# --- FUNÇÃO DE ATUALIZAÇÃO PODEROSA (A GRANDE MUDANÇA) ---
def update_category(db, db_category: models.Category, update_data: CategoryUpdate):
    update_dict = update_data.model_dump(exclude_unset=True)

    # 1. Atualiza os campos simples da categoria
    for key, value in update_dict.items():
        if key not in ["option_groups", "schedules"]:  # Ignora as listas por enquanto
            setattr(db_category, key, value)

    # 2. Sincroniza os OptionGroups
    if "option_groups" in update_dict:
        sync_option_groups(db, db_category, update_dict["option_groups"])

    # 3. Sincroniza os Schedules
    if "schedules" in update_dict:
        sync_schedules(db, db_category, update_dict["schedules"])

    db.commit()
    db.refresh(db_category)
    return db_category


# --- Funções Auxiliares para Sincronização ---

def sync_option_groups(db, category: models.Category, groups_data: list[dict]):
    # Mapeia grupos existentes e novos por ID
    existing_groups = {group.id: group for group in category.option_groups}
    incoming_groups = {group['id']: group for group in groups_data if group.get('id')}

    # Deleta grupos que não vieram na requisição
    for group_id in existing_groups:
        if group_id not in incoming_groups:
            db.delete(existing_groups[group_id])

    # Atualiza grupos existentes e cria novos
    for group_data in groups_data:
        group_id = group_data.get('id')
        if group_id and group_id in existing_groups:
            # Atualiza o grupo
            db_group = existing_groups[group_id]
            for key, value in group_data.items():
                if key != 'items': setattr(db_group, key, value)
            # Sincroniza os itens DENTRO do grupo
            sync_option_items(db, db_group, group_data.get('items', []))
        else:
            # Cria um novo grupo
            items_data = group_data.pop('items', [])
            db_group = models.OptionGroup(**group_data, category_id=category.id)
            db.add(db_group)
            db.flush()
            # Cria os itens para o novo grupo
            for item_data in items_data:
                db.add(models.OptionItem(**item_data, option_group_id=db_group.id))


def sync_option_items(db, group: models.OptionGroup, items_data: list[dict]):
    # Lógica de sincronização para os itens (mesmo padrão: deletar, atualizar, criar)
    existing_items = {item.id: item for item in group.items}
    incoming_items = {item['id']: item for item in items_data if item.get('id')}

    for item_id in existing_items:
        if item_id not in incoming_items:
            db.delete(existing_items[item_id])

    for item_data in items_data:
        item_id = item_data.get('id')
        if item_id and item_id in existing_items:
            db_item = existing_items[item_id]
            for key, value in item_data.items(): setattr(db_item, key, value)
        else:
            db.add(models.OptionItem(**item_data, option_group_id=group.id))


# (A função sync_schedules seria muito similar, sincronizando schedules e time_shifts)

# --- FUNÇÕES DE LEITURA REFINADAS ---
def get_category(db, category_id: int, store_id: int):
    return db.query(models.Category).options(
        selectinload(models.Category.option_groups).selectinload(models.OptionGroup.items),
        selectinload(models.Category.schedules).selectinload(models.CategorySchedule.time_shifts)  # ✨ Adicionado
    ).filter(
        models.Category.id == category_id,
        models.Category.store_id == store_id
    ).first()


def get_all_categories(db, store_id: int):
    return db.query(models.Category).options(
        selectinload(models.Category.option_groups).selectinload(models.OptionGroup.items),
        selectinload(models.Category.schedules).selectinload(models.CategorySchedule.time_shifts)  # ✨ Adicionado
    ).filter(models.Category.store_id == store_id).all()


def update_category_status(db, db_category: models.Category, is_active: bool):
    db_category.is_active = is_active
    if not is_active:
        for link in db_category.product_links:
            link.product.available = False
            logger.info(f"Desativando produto '{link.product.name}' via cascata.")  # Melhor usar logging
    db.commit()
    db.refresh(db_category)
    return db_category


# Adicione estas duas funções ao seu arquivo crud_category.py

def sync_schedules(db: Session, category: models.Category, schedules_data: list[dict]):
    """Sincroniza a lista de regras de agendamento de uma categoria."""

    # 1. Mapeia os agendamentos existentes e os que vieram na requisição
    existing_schedules = {schedule.id: schedule for schedule in category.schedules}
    incoming_schedules = {schedule['id']: schedule for schedule in schedules_data if schedule.get('id')}

    # 2. Deleta agendamentos que não vieram na requisição
    for schedule_id in existing_schedules:
        if schedule_id not in incoming_schedules:
            db.delete(existing_schedules[schedule_id])

    # 3. Atualiza os existentes e cria os novos
    for schedule_data in schedules_data:
        schedule_id = schedule_data.get('id')

        if schedule_id and schedule_id in existing_schedules:
            # ATUALIZA um agendamento existente
            db_schedule = existing_schedules[schedule_id]
            # Atualiza os campos simples (neste caso, os dias da semana)
            db_schedule.days_of_week = schedule_data.get('days_of_week', [])

            # Sincroniza a lista aninhada de turnos de horário
            sync_time_shifts(db, db_schedule, schedule_data.get('time_shifts', []))
        else:
            # CRIA um novo agendamento
            shifts_data = schedule_data.pop('time_shifts', [])
            db_schedule = models.CategorySchedule(**schedule_data, category_id=category.id)
            db.add(db_schedule)
            db.flush()  # Flush para obter o ID do novo schedule

            # Cria os turnos para o novo agendamento
            for shift_data in shifts_data:
                db.add(models.TimeShift(**shift_data, schedule_id=db_schedule.id))


def sync_time_shifts(db: Session, schedule: models.CategorySchedule, shifts_data: list[dict]):
    """
    Sincroniza a lista de turnos de horário para uma regra de agendamento.
    Para esta sub-lista simples, a abordagem mais fácil é deletar e recriar.
    """

    # 1. Deleta todos os turnos de horário antigos associados a esta regra
    for shift in schedule.time_shifts:
        db.delete(shift)

    # 2. Cria os novos turnos de horário que vieram na requisição
    for shift_data in shifts_data:
        db.add(models.TimeShift(**shift_data, schedule_id=schedule.id))