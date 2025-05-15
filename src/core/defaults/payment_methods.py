# src/core/defaults/payment_methods.py

default_payment_methods = [
    {
        "payment_type": "Cash",
        "custom_name": "Dinheiro",
        "custom_icon": "cash.png",
        "change_back": True,
        "pix_key_active": False,
    },
    {
        "payment_type": "Pix",
        "custom_name": "Pix",
        "custom_icon": "pix.png",
        "pix_key_active": False,
    },
    {
        "payment_type": "Card",
        "custom_name": "Cartão de Débito",
        "custom_icon": "debit.png",
        "pix_key_active": False,
    },
    {
        "payment_type": "Card",
        "custom_name": "Cartão de Crédito",
        "custom_icon": "credit.png",
        "pix_key_active": False,
    },
]
