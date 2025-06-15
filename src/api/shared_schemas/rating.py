from pydantic import BaseModel, Field, model_validator
from typing import Optional

class RatingCreate(BaseModel):
    stars: int = Field(..., ge=1, le=5)
    comment: Optional[str] = None
    store_id: Optional[int] = None
    product_id: Optional[int] = None
    order_id: int

    @classmethod
    @model_validator(mode='before')  # valida antes da criação do objeto
    def check_only_one_entity(cls, values):
        store_id = values.get("store_id")
        product_id = values.get("product_id")

        if store_id is None and product_id is None:
            raise ValueError("Você deve informar store_id ou product_id.")
        if store_id is not None and product_id is not None:
            raise ValueError("Avalie apenas a loja ou o produto, nunca os dois.")
        return values


class RatingOut(BaseModel):
    id: int
    customer_name: Optional[str] = None # Certifique-se que seu get_ratings_summary popula isso
    stars: int
    comment: Optional[str]
    created_at: Optional[str] = None # Para garantir que o timestamp seja serializado

    class Config:
        from_attributes = True # Pydantic v2+

class RatingsSummaryOut(BaseModel):
    average_rating: float = Field(..., alias="average_rating")
    total_ratings: int = Field(..., alias="total_ratings")
    distribution: dict[int, int]
    ratings: list[RatingOut]

    class Config:
        from_attributes = True # Pydantic v2+
        populate_by_name = True # Permite mapear 'average_rating' do JSON para 'average_rating' no campo