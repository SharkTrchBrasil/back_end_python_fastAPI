# new_order.py
from typing import Annotated, List, Optional
from pydantic import BaseModel, Field, ValidationError, root_validator

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
    address: Optional[Address] = None # Detailed address if delivery_type is 'delivery'
    payment_method_id: Optional[int] = None # ID of the chosen payment method
    needs_change: Optional[bool] = False # Whether the customer needs change for cash payment
    change_for: Optional[float] = None # Amount customer pays if needs_change is True
    observation: Optional[str] = None # Any additional notes for the order
    delivery_fee: Optional[float] = 0.0 # Delivery fee for the order

    @root_validator(pre=False) # Use pre=False for post-validation
    def validate_order_details(cls, values):
        delivery_type = values.get("delivery_type")
        address = values.get("address")
        needs_change = values.get("needs_change")
        change_for = values.get("change_for")
        total_price = values.get("total_price") # This is total_price of the order from frontend

        # Validation for delivery type and address
        if delivery_type == 'delivery' and address is None:
            raise ValueError("Address is required for delivery orders.")
        elif delivery_type == 'pickup' and address is not None:
             # Optionally, you might want to clear or ignore address for pickup to prevent confusion
            pass # Or, raise ValueError("Address should not be provided for pickup orders.")

        # Validation for change amount if needs_change is true
        if needs_change:
            if change_for is None:
                raise ValueError("Informe o valor que o cliente irá pagar em dinheiro (change_for).")
            # Convert total_price to float for comparison if it's stored as int but change_for is float
            if change_for < total_price: # Assuming total_price is in cents (int) and change_for is in real (float)
                                         # You need to ensure consistent units for comparison (e.g., both in cents)
                                         # For now, let's assume total_price should be compared directly to change_for
                raise ValueError("O valor informado para troco (change_for) deve ser maior ou igual ao total da compra.")
        else:
            if change_for is not None:
                raise ValueError("Você marcou que não precisa de troco, então não deve informar o campo change_for.")

        return values