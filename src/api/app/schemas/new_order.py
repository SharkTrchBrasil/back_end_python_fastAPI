# new_order.py
from typing import Annotated, List, Optional
from pydantic import BaseModel, Field, ValidationError, root_validator, model_validator

from src.api.app.schemas.customer import AddressOut



class NewOrderVariantOption(BaseModel):
    variant_option_id: int
    quantity: Annotated[int, Field(gt=0)]
    price: int


class NewOrderVariant(BaseModel):
    variant_id: int
    options: List[NewOrderVariantOption]


class NewOrderProduct(BaseModel):
    product_id: int
    price: int
    quantity: Annotated[int, Field(gt=0)]
    variants: List[NewOrderVariant]
    note: str = ''
    coupon_code: str | None = None  # ✅ Isso aqui precisa existir


class NewOrder(BaseModel):

    customer_id: int # New: Unique ID for the customer

    customer_name: str | None = None
    customer_phone: str | None = None


    total_price: int
    coupon_code: Optional[str] = None  # 👈 Aqui você recebe
    products: List[NewOrderProduct]
    payment_method_name: str | None = None


    delivery_type: Optional[str] = None
    address: AddressOut | None = None
    payment_method_id: Optional[int] = None
    needs_change: Optional[bool] = False
    change_for: Optional[float] = None
    observation: Optional[str] = None
    delivery_fee: Optional[float] = 0.0

    # ✅ Campos copiados do endereço
    street: str | None = None
    number: str | None = None
    complement: str | None = None
    neighborhood: str | None = None

    city: str | None = None

    @model_validator(mode='after')
    def validate_order_details(self):
        if self.delivery_type == 'delivery':
            # Valida campos soltos ao invés do objeto 'address'
            if not (self.street and self.neighborhood and self.city):
                raise ValueError(
                    "Campos de endereço (street, neighborhood, city) são obrigatórios para pedidos de delivery.")
        # validação do troco continua igual
        if self.needs_change:
            if self.change_for is None:
                raise ValueError("Informe o valor que o cliente irá pagar em dinheiro (change_for).")
            if self.change_for < self.total_price / 100:
                raise ValueError("O valor informado para troco deve ser maior ou igual ao total da compra.")
        else:
            if self.change_for is not None:
                raise ValueError("Você marcou que não precisa de troco, então não deve informar o campo change_for.")

        return self
