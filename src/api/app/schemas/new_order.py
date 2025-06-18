from typing import Annotated

from pydantic import BaseModel, Field
from pydantic.v1 import root_validator


class NewOrderProductVariantOption(BaseModel):
    variant_option_id: int
    quantity: Annotated[int, Field(gt=0)]
    price: int


class NewOrderProductVariant(BaseModel):
    variant_id: int
    options: list[NewOrderProductVariantOption]


class NewOrderProduct(BaseModel):
    product_id: int
    price: int
    quantity: Annotated[int, Field(gt=0)]
    variants: list[NewOrderProductVariant]
    note: str = ''  # ➕ Adicionado aqui


class NewOrder(BaseModel):
    phone: str
    cpf: str
    name: str
    total_price: int
    products: list[NewOrderProduct]

    @root_validator
    def validate_change_amount(self, values):
        needs_change = values.get("needs_change")
        change_amount = values.get("change_amount")
        total_price = values.get("total_price")

        if needs_change:
            if change_amount is None:
                raise ValueError("Informe o valor que o cliente irá pagar em dinheiro (change_amount).")
            if change_amount < total_price:
                raise ValueError("O valor informado para troco (change_amount) deve ser maior ou igual ao total da compra.")
        else:
            if change_amount is not None:
                raise ValueError("Você marcou que não precisa de troco, então não deve informar o campo change_amount.")

        return values