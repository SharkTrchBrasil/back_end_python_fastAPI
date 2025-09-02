from pydantic import BaseModel, Field
from datetime import date

from src.api.schemas.customer.customer import StoreCustomerOut


# --- Schemas para Categoria de Recebíveis ---

class ReceivableCategoryBase(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)


class ReceivableCategoryCreate(ReceivableCategoryBase):
    pass


class ReceivableCategoryUpdate(ReceivableCategoryBase):
    pass


class ReceivableCategoryResponse(ReceivableCategoryBase):
    id: int

    class Config:
        from_attributes = True


# --- Schemas para Contas a Receber ---

class ReceivableBase(BaseModel):
    title: str = Field(..., max_length=255)
    description: str | None = None
    amount: int = Field(..., gt=0, description="Valor em centavos")
    due_date: date
    category_id: int | None = None
    customer_id: int | None = None


class ReceivableCreate(ReceivableBase):
    pass


class ReceivableUpdate(BaseModel):
    # Na atualização, todos os campos são opcionais
    title: str | None = Field(None, max_length=255)
    description: str | None = None
    amount: int | None = Field(None, gt=0)
    due_date: date | None = None
    category_id: int | None = None
    customer_id: int | None = None


class ReceivableResponse(ReceivableBase):
    id: int
    received_date: date | None
    status: str  # Ou use um Enum, se preferir

    # Aninha os objetos completos para uma resposta mais rica para o frontend
    category: ReceivableCategoryResponse | None = None
    customer: StoreCustomerOut | None = None

    class Config:
        from_attributes = True