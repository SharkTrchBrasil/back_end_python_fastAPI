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
    stars: int
    comment: Optional[str]

    class Config:
        orm_mode = True
