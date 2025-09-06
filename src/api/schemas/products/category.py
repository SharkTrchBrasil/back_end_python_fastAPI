from __future__ import annotations

from datetime import time

from pydantic import BaseModel, Field, computed_field

from src.api.schemas.products.product_category_link import ProductCategoryLinkOut
from src.core.aws import S3_PUBLIC_BASE_URL
from src.core.models import CategoryType, CashbackType
from decimal import Decimal

from src.core.utils.enums import FoodTagEnum, AvailabilityTypeEnum


# --- SCHEMAS DE DISPONIBILIDADE ---
class TimeShiftBase(BaseModel):
    start_time: time
    end_time: time

class TimeShiftCreate(TimeShiftBase):
    pass

class TimeShift(TimeShiftBase):
    id: int
    class Config: from_attributes = True

class CategoryScheduleBase(BaseModel):
    days_of_week: list[int] = Field(..., min_items=1, max_items=7) # Validação básica

class CategoryScheduleCreate(CategoryScheduleBase):
    time_shifts: list[TimeShiftCreate] = []

class CategorySchedule(CategoryScheduleBase):
    id: int
    time_shifts: list[TimeShift] = []
    class Config: from_attributes = True


class CategoryScheduleUpdate(BaseModel):
    id: int | None = None
    days_of_week: list[int]
    time_shifts: list[TimeShiftCreate] # Pode sempre recriar os horários

# --- SCHEMA OptionItem ATUALIZADO ---





class OptionItemBase(BaseModel):
    name: str
    description: str | None = None
    price: float = 0.0
    is_active: bool = True
    # --- CAMPOS ADICIONADOS ---
    external_code: str | None = None
    slices: int | None = None
    max_flavors: int | None = None

class OptionItemCreate(OptionItemBase):
    # ✨ Agora espera uma lista do nosso Enum
    tags: list[FoodTagEnum] | None = None

class OptionItem(OptionItemBase):
    id: int
    priority: int
    # ✨ E retorna uma lista do nosso Enum
    tags: list[FoodTagEnum] = []

    class Config: from_attributes = True


class OptionItemUpdate(BaseModel):
    id: int | None = None # Se o id for nulo, é um novo item. Se tiver id, é um item existente.
    name: str
    description: str | None = None
    price: float = 0.0
    is_active: bool = True
    external_code: str | None = None
    slices: int | None = None
    max_flavors: int | None = None
    tags: list[FoodTagEnum] | None = []





class OptionGroupBase(BaseModel):
    name: str
    min_selection: int = 1
    max_selection: int = 1



class OptionGroupCreate(OptionGroupBase):
    # ✨ ADICIONADO: Permite receber a lista de itens DENTRO do grupo na criação
    items: list[OptionItemCreate] | None = None






class OptionGroup(OptionGroupBase):
    id: int
    priority: int
    items: list[OptionItem] = []

    class Config: from_attributes = True

class OptionGroupUpdate(BaseModel):
    id: int | None = None
    name: str
    min_selection: int = 1
    max_selection: int = 1
    items: list[OptionItemUpdate] = []



class CategoryBase(BaseModel):
    name: str
    is_active: bool = True
    type: CategoryType
   # ✅ ADICIONADOS AQUI AO SCHEMA BASE
    cashback_type: CashbackType = CashbackType.NONE
    cashback_value: Decimal = Decimal('0.00')
    printer_destination: str | None = None # ✅ ADICIONADO AQUI

class CategoryCreate(CategoryBase):

    option_groups: list[OptionGroupCreate] | None = None
    availability_type: AvailabilityTypeEnum = AvailabilityTypeEnum.ALWAYS
    schedules: list[CategoryScheduleCreate] | None = None


class CategoryUpdate(BaseModel):
    name: str | None = None
    is_active: bool | None = None
    priority: int | None = None
    cashback_type: CashbackType | None = None
    cashback_value: Decimal | None = None

    # ✅ CAMPOS ADICIONADOS PARA PERMITIR A ATUALIZAÇÃO COMPLETA
    availability_type: AvailabilityTypeEnum | None = None
    schedules: list[CategoryScheduleUpdate] | None = None
    option_groups: list[OptionGroupUpdate] | None = None
    printer_destination: str | None = None  # ✅ ADICIONADO AQUI



class Category(CategoryBase):  # O schema de resposta
    id: int
    priority: int
    availability_type: AvailabilityTypeEnum
    schedules: list[CategorySchedule] = []

    # ✨ CORREÇÃO 1: Adicionar a URL da imagem para o frontend
    file_key: str | None = Field(None, exclude=True)  # Exclui do JSON final




    cashback_type: CashbackType
    cashback_value: Decimal
    product_links: list[ProductCategoryLinkOut] = []

    option_groups: list[OptionGroup] = []




    @computed_field
    @property
    def image_path(self) -> str | None:
        """Gera a URL completa e pública da imagem."""
        if self.file_key:
            return f"{S3_PUBLIC_BASE_URL}/{self.file_key}"
        return None



    class Config:
        from_attributes = True






# ✅ 1. CRIE O SCHEMA DE SAÍDA PARA A TAG
class FoodTagOut(BaseModel):
    id: int
    name: str
    description: str | None = None
    icon_key: str | None = None

    class Config:
        from_attributes = True
