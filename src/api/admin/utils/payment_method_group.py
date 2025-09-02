# Coloque esta função no seu arquivo de socket, antes do handler

from src.api.schemas.financial.payment_method import (
    PaymentMethodGroupOut,
    PaymentMethodCategoryOut,
    PlatformPaymentMethodOut,
    StorePaymentMethodActivationOut,
)
from src.core import models

from collections import defaultdict


def _build_payment_groups_from_activations_simplified(
    activations: list[models.StorePaymentMethodActivation],
) -> list[PaymentMethodGroupOut]:
    """
    Versão simplificada que constrói a hierarquia de pagamentos em uma única passagem.
    """
    # Estrutura para agrupar: {group_model: {category_model: [method_out, ...], ...}, ...}
    grouped_structure = defaultdict(lambda: defaultdict(list))

    for activation in activations:
        method = activation.platform_method
        if not method or not method.category or not method.category.group:
            continue

        method_out = PlatformPaymentMethodOut.model_validate(method)
        method_out.activation = StorePaymentMethodActivationOut.model_validate(activation)

        grouped_structure[method.category.group][method.category].append(method_out)

    final_groups = []
    for group_model, categories in grouped_structure.items():
        category_list = []
        for category_model, methods in categories.items():
            category_list.append(
                PaymentMethodCategoryOut(
                    name=category_model.name,
                    methods=sorted(methods, key=lambda m: m.name),
                )
            )

        final_groups.append(
            PaymentMethodGroupOut(
                name=group_model.name,

                description=group_model.description,
                 title=group_model.title, # Descomente se 'title' for um campo
                categories=sorted(category_list, key=lambda c: c.name),
            )
        )


    return sorted(
        final_groups,
        key=lambda g: next(
            (
                group_model.priority
                for group_model in grouped_structure.keys()
                if group_model.name == g.name
            ),
            0,  # Valor padrão caso o grupo não seja encontrado (segurança)
        ),
    )

