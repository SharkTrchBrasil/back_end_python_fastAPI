# Coloque esta função no seu arquivo de socket, antes do handler

from collections import defaultdict
from src.api.schemas.payment_method import (
    PaymentMethodGroupOut,
    PaymentMethodCategoryOut,
    PlatformPaymentMethodOut,
    StorePaymentMethodActivationOut,
)
from src.core import models



def _build_payment_groups_from_activations(
        activations: list[models.StorePaymentMethodActivation],
) -> list[PaymentMethodGroupOut]:
    """
    Transforma uma lista de ativações de pagamento na estrutura hierárquica
    de grupos e categorias esperada pelo schema.
    """
    if not activations:
        return []

    groups = {}
    categories = defaultdict(list)

    for activation in activations:
        method = activation.platform_method
        if not method or not method.category:
            continue

        method_out = PlatformPaymentMethodOut(
            id=method.id,
            name=method.name,
            icon_key=method.icon_key,
            activation=StorePaymentMethodActivationOut.model_validate(activation),
        )
        categories[method.category.id].append(method_out)

    all_categories_processed = set()
    for activation in activations:
        method = activation.platform_method
        if not method or not method.category or not method.category.group:
            continue

        category_model = method.category
        group_model = category_model.group

        if category_model.id in all_categories_processed:
            continue

        category_out = PaymentMethodCategoryOut(
            name=category_model.name,
            methods=sorted(categories.get(category_model.id, []), key=lambda m: m.name),
        )

        if group_model.id not in groups:
            groups[group_model.id] = {
                "model": group_model,
                "categories": [],
            }
        groups[group_model.id]["categories"].append(category_out)
        all_categories_processed.add(category_model.id)

    final_groups = []
    for group_id, group_data in groups.items():
        group_model = group_data["model"]
        final_groups.append(
            PaymentMethodGroupOut(
                name=group_model.name,
                categories=sorted(group_data["categories"], key=lambda c: c.name),
            )
        )

    # ✅ CORREÇÃO AQUI: Acessando p["model"].priority em vez de p.priority
    return sorted(
        final_groups,
        key=lambda g: next(
            (
                p["model"].priority
                for p in groups.values()
                if p["model"].name == g.name
            ),
            0,
        ),
    )