from pydantic import BaseModel, Field, computed_field
from datetime import date

from .supplier import SupplierResponse  # Importar o novo schema


class CategoryResponse(BaseModel):  # Criar um schema para categoria também
    id: int
    name: str

    class Config:
        from_attributes = True


class PayableUpdate(BaseModel):
    # Campos que podem ser atualizados
    title: str | None = None
    description: str | None = None
    amount: int | None = None
    due_date: date | None = None
    category_id: int | None = None
    supplier_id: int | None = None
    # ... outros campos


class PayableResponse(BaseModel):
    id: int
    title: str
    description: str | None
    amount: int
    discount: int
    addition: int
    final_amount: int  # Propriedade computada
    due_date: date
    payment_date: date | None
    status: str  # Usar o enum aqui

    category: CategoryResponse | None
    supplier: SupplierResponse | None

    # ✅ MELHORIA: Usando o decorador moderno do Pydantic V2
    @computed_field
    @property
    def final_amount(self) -> int:
        """Calcula o valor final da conta (valor - desconto + acréscimo)."""
        return self.amount - self.discount + self.addition

    class Config:
        from_attributes = True


# Schema para a criação de uma recorrência (opcional)
class RecurrenceCreate(BaseModel):
    frequency: str = Field(..., description="Ex: 'monthly', 'weekly', 'yearly'")
    interval: int = Field(1, gt=0, description="Ex: a cada 2 meses (frequency='monthly', interval=2)")
    end_date: date | None = Field(None, description="Data final da recorrência, se houver")


# Schema para CRIAR uma nova conta a pagar
class PayableCreate(BaseModel):
    # Campos obrigatórios
    title: str = Field(..., max_length=255)
    amount: int = Field(..., gt=0, description="Valor em centavos")
    due_date: date

    # Campos opcionais
    description: str | None = None
    category_id: int | None = None
    supplier_id: int | None = None
    barcode: str | None = Field(None, max_length=255)
    notes: str | None = None

    # Campo opcional para criar uma conta recorrente
    recurrence: RecurrenceCreate | None = None