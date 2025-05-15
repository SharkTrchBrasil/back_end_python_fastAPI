# src/core/defaults/delivery_methods.py

default_delivery_methods = [
    {
        "delivery_type": "delivery",
        "custom_name": "Entrega",
        "custom_icon": "delivery.png",
        "is_active": True,
        "min_delivery_time": 30,
        "max_delivery_time": 60,
    },
    {
        "delivery_type": "pickup",
        "custom_name": "Retirada no Balcão",
        "custom_icon": "pickup.png",
        "is_active": True,
        "min_delivery_time": 5,
        "max_delivery_time": 15,
    },
    {
        "delivery_type": "table",
        "custom_name": "Atendimento em Mesa",
        "custom_icon": "table.png",
        "is_active": False,
        "min_delivery_time": 0,
        "max_delivery_time": 0,
    },
]
