# Em: src/api/schemas/payable_category.py
from pydantic import BaseModel, Field

# Schema base com os campos da categoria
class PayableCategoryBase(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)

# Schema para criar uma nova categoria
class PayableCategoryCreate(PayableCategoryBase):
    pass

# Schema para atualizar uma categoria existente
class PayableCategoryUpdate(PayableCategoryBase):
    pass

# Schema para a resposta da API (incluindo o ID)
class PayableCategoryResponse(PayableCategoryBase):
    id: int

    class Config:
        from_attributes = True