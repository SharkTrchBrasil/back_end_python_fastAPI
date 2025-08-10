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

    # Dicionários para agrupar os dados
    groups = {}
    categories = defaultdict(list)

    # 1. Itera sobre as ativações para organizar os métodos por categoria
    for activation in activations:
        method = activation.platform_method
        if not method or not method.category:
            continue

        # Cria o DTO do método, já aninhando os dados da ativação
        method_out = PlatformPaymentMethodOut(
            id=method.id,
            name=method.name,
            icon_key=method.icon_key,
            # Aninha os detalhes da ativação (is_active, fee, etc.)
            activation=StorePaymentMethodActivationOut.model_validate(activation),
        )

        # Adiciona o método à sua respectiva categoria
        categories[method.category.id].append(method_out)

    # 2. Itera sobre as categorias para organizar por grupo
    all_categories_processed = set()
    for activation in activations:
        method = activation.platform_method
        if not method or not method.category or not method.category.group:
            continue

        category_model = method.category
        group_model = category_model.group

        if category_model.id in all_categories_processed:
            continue

        # Cria a categoria Pydantic com a lista de métodos que já montamos
        category_out = PaymentMethodCategoryOut(
            name=category_model.name,
            methods=sorted(categories.get(category_model.id, []), key=lambda m: m.name),  # Ordena métodos
        )

        # Adiciona a categoria ao seu grupo, criando o grupo se for a primeira vez
        if group_model.id not in groups:
            groups[group_model.id] = {
                "model": group_model,
                "categories": [],
            }
        groups[group_model.id]["categories"].append(category_out)
        all_categories_processed.add(category_model.id)

    # 3. Monta a lista final de grupos
    final_groups = []
    for group_id, group_data in groups.items():
        group_model = group_data["model"]
        final_groups.append(
            PaymentMethodGroupOut(
                name=group_model.name,
                # Ordena as categorias dentro do grupo
                categories=sorted(group_data["categories"], key=lambda c: c.name),
            )
        )

    # Ordena os grupos pela prioridade definida no banco
    return sorted(final_groups,
                  key=lambda g: next((p.priority for p in groups.values() if p["model"].name == g.name), 0))