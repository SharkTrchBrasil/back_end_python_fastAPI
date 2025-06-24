# new_order.py
from typing import Annotated, List, Optional
from pydantic import BaseModel, Field, ValidationError, root_validator, model_validator

from src.api.app.schemas.customer import AddressOut
from src.core.models import Address


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


class NewOrder(BaseModel):
    # --- Removed customer contact details ---
    # phone: str
    # cpf: str
    # name: str

    # --- Added customer_id ---
    customer_id: int # New: Unique ID for the customer

    # --- Existing fields ---
    total_price: int
    products: List[NewOrderProduct]

    # --- New fields for delivery and payment ---
    delivery_type: Optional[str] = None # e.g., 'delivery', 'pickup'
    address: AddressOut | None = None
    payment_method_id: Optional[int] = None # ID of the chosen payment method
    needs_change: Optional[bool] = False # Whether the customer needs change for cash payment
    change_for: Optional[float] = None # Amount customer pays if needs_change is True
    observation: Optional[str] = None # Any additional notes for the order
    delivery_fee: Optional[float] = 0.0 # Delivery fee for the order

    @model_validator(mode='after')
    def validate_order_details(self):
        if self.delivery_type == 'delivery' and self.address is None:
            raise ValueError("Address is required for delivery orders.")
        elif self.delivery_type == 'pickup' and self.address is not None:
            pass  # ou raise se quiser bloquear

        if self.needs_change:
            if self.change_for is None:
                raise ValueError("Informe o valor que o cliente irá pagar em dinheiro (change_for).")
            if self.change_for < self.total_price:
                raise ValueError("O valor informado para troco deve ser maior ou igual ao total da compra.")
        else:
            if self.change_for is not None:
                raise ValueError("Você marcou que não precisa de troco, então não deve informar o campo change_for.")

        return self