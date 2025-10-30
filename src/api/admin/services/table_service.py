# src/api/services/table_service.py
from datetime import datetime, timezone
from sqlalchemy.orm import Session, selectinload
from sqlalchemy.exc import IntegrityError

from src.api.schemas.tables.table import CreateSaloonRequest, OpenTableRequest, CreateTableRequest, \
    AddItemToTableRequest, UpdateTableRequest, UpdateSaloonRequest
from src.core import models
from src.core.utils.enums import TableStatus, CommandStatus, OrderStatus, PaymentStatus, SalesChannel


class TableService:
    """Service para gerenciar mesas, comandas e pedidos de salão"""

    def __init__(self, db: Session):
        self.db = db

    # ========== GERENCIAMENTO DE SALÕES ==========

    def create_saloon(self, store_id: int, request: CreateSaloonRequest) -> models.Saloon:
        """Cria um novo salão/ambiente"""
        saloon = models.Saloon(
            store_id=store_id,
            name=request.name,
            display_order=request.display_order,
            is_active=True,
        )
        self.db.add(saloon)

        try:
            self.db.commit()
            self.db.refresh(saloon)
            return saloon
        except IntegrityError:
            self.db.rollback()
            raise ValueError(f"Já existe um salão com o nome '{request.name}' nesta loja.")

    def update_saloon(self, saloon_id: int, store_id: int, request: UpdateSaloonRequest) -> models.Saloon:
        """Atualiza um salão existente"""
        saloon = self.db.query(models.Saloon).filter(
            models.Saloon.id == saloon_id,
            models.Saloon.store_id == store_id
        ).first()

        if not saloon:
            raise ValueError("Salão não encontrado")

        if request.name is not None:
            saloon.name = request.name
        if request.display_order is not None:
            saloon.display_order = request.display_order
        if request.is_active is not None:
            saloon.is_active = request.is_active

        self.db.commit()
        self.db.refresh(saloon)
        return saloon

    def delete_saloon(self, saloon_id: int, store_id: int) -> bool:
        """Deleta um salão (soft delete)"""
        saloon = self.db.query(models.Saloon).filter(
            models.Saloon.id == saloon_id,
            models.Saloon.store_id == store_id
        ).first()

        if not saloon:
            raise ValueError("Salão não encontrado")

        # Verifica se há mesas ativas
        active_tables = self.db.query(models.Tables).filter(
            models.Tables.saloon_id == saloon_id,
            models.Tables.status != TableStatus.AVAILABLE
        ).count()

        if active_tables > 0:
            raise ValueError("Não é possível deletar um salão com mesas ocupadas ou reservadas")

        saloon.is_active = False
        self.db.commit()
        return True

    # ========== GERENCIAMENTO DE MESAS ==========

    def create_table(self, store_id: int, request: CreateTableRequest) -> models.Tables:
        """Cria uma nova mesa"""
        # Valida se o salão existe e pertence à loja
        saloon = self.db.query(models.Saloon).filter(
            models.Saloon.id == request.saloon_id,
            models.Saloon.store_id == store_id
        ).first()

        if not saloon:
            raise ValueError("Salão não encontrado")

        table = models.Tables(
            store_id=store_id,
            saloon_id=request.saloon_id,
            name=request.name,
            max_capacity=request.max_capacity,
            location_description=request.location_description,
            status=TableStatus.AVAILABLE,
            current_capacity=0,
            opened_at=datetime.now(timezone.utc),
        )

        self.db.add(table)

        try:
            self.db.commit()
            self.db.refresh(table)
            return table
        except IntegrityError:
            self.db.rollback()
            raise ValueError(f"Já existe uma mesa com o nome '{request.name}' neste salão.")

    def update_table(self, table_id: int, store_id: int, request: UpdateTableRequest) -> models.Tables:
        """Atualiza informações de uma mesa"""
        table = self.db.query(models.Tables).filter(
            models.Tables.id == table_id,
            models.Tables.store_id == store_id
        ).first()

        if not table:
            raise ValueError("Mesa não encontrada")

        if request.name is not None:
            table.name = request.name
        if request.max_capacity is not None:
            table.max_capacity = request.max_capacity
        if request.location_description is not None:
            table.location_description = request.location_description
        if request.status is not None:
            table.status = TableStatus(request.status)

        self.db.commit()
        self.db.refresh(table)
        return table

    def delete_table(self, table_id: int, store_id: int) -> bool:
        """Deleta uma mesa (soft delete)"""
        table = self.db.query(models.Tables).filter(
            models.Tables.id == table_id,
            models.Tables.store_id == store_id
        ).first()

        if not table:
            raise ValueError("Mesa não encontrada")

        if table.status != TableStatus.AVAILABLE:
            raise ValueError("Não é possível deletar uma mesa ocupada ou reservada")

        table.is_deleted = True
        table.deleted_at = datetime.now(timezone.utc)
        self.db.commit()
        return True

    # ========== ABERTURA E FECHAMENTO DE MESAS ==========


    def open_table(self, store_id: int, request: OpenTableRequest) -> models.Command:
        """Abre uma mesa criando uma comanda ativa"""

        # ✅ VALIDAÇÃO ATUALIZADA: table_id é opcional
        table = None
        if request.table_id is not None:
            table = self.db.query(models.Tables).filter(
                models.Tables.id == request.table_id,
                models.Tables.store_id == store_id
            ).first()

            if not table:
                raise ValueError("Mesa não encontrada")

            if table.status != TableStatus.AVAILABLE:
                raise ValueError("Esta mesa já está ocupada ou reservada")

        # Cria a comanda (com ou sem mesa)
        command = models.Command(
            store_id=store_id,
            table_id=request.table_id,  # ✅ Pode ser None agora
            customer_name=request.customer_name,
            customer_contact=request.customer_contact,
            attendant_id=request.attendant_id,
            notes=request.notes,
            status=CommandStatus.ACTIVE,
        )
        self.db.add(command)

        # Atualiza o status da mesa (se houver)
        if table is not None:
            table.status = TableStatus.OCCUPIED
            table.opened_at = datetime.now(timezone.utc)

        self.db.commit()
        self.db.refresh(command)

        # Carrega os relacionamentos necessários para o socket
        if table is not None:
            self.db.refresh(table)
            table = self.db.query(models.Tables).options(
                selectinload(models.Tables.commands)
            ).filter(models.Tables.id == table.id).first()

        return command

    def close_table(self, store_id: int, table_id: int, command_id: int) -> models.Tables:
        """Fecha uma mesa e sua comanda"""
        table = self.db.query(models.Tables).filter(
            models.Tables.id == table_id,
            models.Tables.store_id == store_id
        ).first()

        if not table:
            raise ValueError("Mesa não encontrada")

        command = self.db.query(models.Command).filter(
            models.Command.id == command_id,
            models.Command.table_id == table_id,
            models.Command.store_id == store_id
        ).first()

        if not command:
            raise ValueError("Comanda não encontrada")

        # ✅ INÍCIO DO BLOCO CORRIGIDO (agora indentado)
        # Fecha a comanda
        command.status = CommandStatus.CLOSED

        # Normaliza pedidos da comanda para contarem no dashboard/performance
        orders = self.db.query(models.Order).filter(
            models.Order.command_id == command_id,
            models.Order.store_id == store_id
        ).all()

        # Fallback de método de pagamento padrão (ex.: Dinheiro) se ausente
        default_pm = None
        try:
            default_pm = (
                self.db.query(models.StorePaymentMethodActivation)
                .join(models.PlatformPaymentMethod)
                .filter(
                    models.StorePaymentMethodActivation.store_id == store_id,
                    models.PlatformPaymentMethod.name.in_(["Dinheiro", "Cash"])
                )
                .first()
            )
        except Exception:
            default_pm = None

        for order in orders:
            # Considera pedido concluído e pago ao fechar mesa
            order.order_status = OrderStatus.DELIVERED
            order.payment_status = PaymentStatus.PAID
            if getattr(order, 'payment_method', None) is None and default_pm is not None:
                try:
                    order.payment_method = default_pm
                except Exception:
                    pass
            # delivered_at opcional
            if hasattr(order, 'delivered_at') and getattr(order, 'delivered_at') is None:
                setattr(order, 'delivered_at', datetime.now(timezone.utc))
            # Garantir campos numéricos não nulos
            order.total_price = order.total_price or 0
            order.subtotal_price = order.subtotal_price or order.total_price
            order.discounted_total_price = order.discounted_total_price or order.total_price
            # Tipos padronizados para relatórios
            order.order_type = SalesChannel.TABLE
            setattr(order, 'delivery_type', 'in_store')
            setattr(order, 'consumption_type', 'dine_in')

        # Libera a mesa
        table.status = TableStatus.AVAILABLE
        table.current_capacity = 0
        table.closed_at = datetime.now(timezone.utc)
        # ✅ FIM DO BLOCO CORRIGIDO

        self.db.commit()
        self.db.refresh(table)
        return table

    def transfer_items_between_commands(self, store_id: int, from_command_id: int, to_command_id: int, order_product_ids: list[int]) -> bool:
        """Transfere itens selecionados entre comandas (mesma loja)"""
        from_cmd = self.db.query(models.Command).filter(models.Command.id == from_command_id, models.Command.store_id == store_id).first()
        to_cmd = self.db.query(models.Command).filter(models.Command.id == to_command_id, models.Command.store_id == store_id).first()
        if not from_cmd or not to_cmd:
            raise ValueError("Comanda de origem ou destino não encontrada")
        if from_cmd.status != CommandStatus.ACTIVE or to_cmd.status != CommandStatus.ACTIVE:
            raise ValueError("Apenas comandas ativas podem transferir/receber itens")

        items = self.db.query(models.OrderProduct).join(models.Order, models.OrderProduct.order_id == models.Order.id).filter(
            models.OrderProduct.id.in_(order_product_ids),
            models.Order.store_id == store_id,
            models.Order.command_id == from_command_id
        ).all()

        if not items:
            raise ValueError("Nenhum item válido para transferir")

        # Reatribui os pedidos base dos itens para a comanda destino
        order_ids_touched = set()
        for op in items:
            order = self.db.query(models.Order).filter(models.Order.id == op.order_id).first()
            if order:
                order.command_id = to_command_id
                order.table_id = to_cmd.table_id
                order_ids_touched.add(order.id)

        self.db.commit()
        return True

    def split_items_to_new_command(self, store_id: int, source_command_id: int, order_product_ids: list[int], target_table_id: int | None = None) -> models.Command:
        """Divide itens selecionados criando uma nova comanda (opcionalmente vinculada a uma mesa)"""
        source = self.db.query(models.Command).filter(models.Command.id == source_command_id, models.Command.store_id == store_id).first()
        if not source or source.status != CommandStatus.ACTIVE:
            raise ValueError("Comanda origem inválida ou inativa")

        new_cmd = models.Command(
            store_id=store_id,
            table_id=target_table_id if target_table_id is not None else source.table_id,
            customer_name=source.customer_name,
            customer_contact=source.customer_contact,
            attendant_id=source.attendant_id,
            notes=source.notes,
            status=CommandStatus.ACTIVE,
        )
        self.db.add(new_cmd)
        self.db.flush()

        # Move itens selecionados (reassign orders)
        items = self.db.query(models.OrderProduct).join(models.Order, models.OrderProduct.order_id == models.Order.id).filter(
            models.OrderProduct.id.in_(order_product_ids),
            models.Order.store_id == store_id,
            models.Order.command_id == source_command_id
        ).all()
        if not items:
            raise ValueError("Nenhum item válido para dividir")

        for op in items:
            order = self.db.query(models.Order).filter(models.Order.id == op.order_id).first()
            if order:
                order.command_id = new_cmd.id
                order.table_id = new_cmd.table_id

        self.db.commit()
        self.db.refresh(new_cmd)
        return new_cmd

    def merge_commands(self, store_id: int, source_command_id: int, target_command_id: int) -> bool:
        """Agrupa (merge) todos os pedidos da comanda origem na comanda destino"""
        source = self.db.query(models.Command).filter(models.Command.id == source_command_id, models.Command.store_id == store_id).first()
        target = self.db.query(models.Command).filter(models.Command.id == target_command_id, models.Command.store_id == store_id).first()
        if not source or not target:
            raise ValueError("Comandas não encontradas")
        if source.status != CommandStatus.ACTIVE or target.status != CommandStatus.ACTIVE:
            raise ValueError("Apenas comandas ativas podem ser unificadas")

        orders = self.db.query(models.Order).filter(models.Order.command_id == source_command_id, models.Order.store_id == store_id).all()
        for order in orders:
            order.command_id = target_command_id
            order.table_id = target.table_id

        # Fecha a comanda origem
        source.status = CommandStatus.CLOSED
        self.db.commit()
        return True

    def move_table_to_saloon(self, store_id: int, table_id: int, new_saloon_id: int) -> models.Tables:
        """Move a mesa para outro salão (mantém status/comandas)"""
        table = self.db.query(models.Tables).filter(models.Tables.id == table_id, models.Tables.store_id == store_id).first()
        if not table:
            raise ValueError("Mesa não encontrada")
        saloon = self.db.query(models.Saloon).filter(models.Saloon.id == new_saloon_id, models.Saloon.store_id == store_id).first()
        if not saloon:
            raise ValueError("Salão destino não encontrado")
        table.saloon_id = new_saloon_id
        self.db.commit()
        self.db.refresh(table)
        return table

    def apply_command_adjustments(self, store_id: int, command_id: int, discount_value: float | None = None, notes: str | None = None) -> models.Command:
        """Aplica desconto e/ou notas na comanda (não altera itens)"""
        cmd = self.db.query(models.Command).filter(models.Command.id == command_id, models.Command.store_id == store_id).first()
        if not cmd:
            raise ValueError("Comanda não encontrada")
        if notes is not None:
            cmd.notes = notes
        # Para desconto, opcional: registrar em tabela de ajustes/financeiro (fora do escopo aqui)
        self.db.commit()
        self.db.refresh(cmd)
        return cmd

    # ========== ADICIONAR/REMOVER ITENS ==========

    def add_item_to_table(self, store_id: int, request: AddItemToTableRequest) -> models.Order:
        """Adiciona um item ao pedido de uma mesa"""

        # 1. Valida a mesa
        table = self.db.query(models.Tables).filter(
            models.Tables.id == request.table_id,
            models.Tables.store_id == store_id
        ).first()

        if not table:
            raise ValueError("Mesa não encontrada")

        # 2. Valida a comanda
        command = self.db.query(models.Command).filter(
            models.Command.id == request.command_id,
            models.Command.table_id == request.table_id,
            models.Command.status == CommandStatus.ACTIVE
        ).first()

        if not command:
            raise ValueError("Comanda não encontrada ou inativa")

        # 3. Busca o produto
        product = self.db.query(models.Product).filter(
            models.Product.id == request.product_id,
            models.Product.store_id == store_id
        ).first()

        if not product:
            raise ValueError("Produto não encontrado")

        # 4. Busca o link de preço do produto na categoria
        product_link = self.db.query(models.ProductCategoryLink).filter(
            models.ProductCategoryLink.product_id == request.product_id,
            models.ProductCategoryLink.category_id == request.category_id
        ).first()

        if not product_link:
            raise ValueError("Produto não encontrado nesta categoria")

        # 5. Calcula o preço base
        base_price = product_link.promotional_price if product_link.is_on_promotion else product_link.price

        # 6. Cria o pedido (Order)
        order = models.Order(
            store_id=store_id,
            table_id=request.table_id,
            command_id=request.command_id,
            sequential_id=self._get_next_sequential_id(store_id),
            public_id=self._generate_public_id(store_id),
            order_type=SalesChannel.TABLE,
            delivery_type="in_store",
            order_status=OrderStatus.PENDING,  # ✅ Usa o Enum
            payment_status=PaymentStatus.PENDING,
            consumption_type="dine_in",
            total_price=0,
            subtotal_price=0,
            discounted_total_price=0,
            delivery_fee=0,
            street="",
            neighborhood="",
            city="",
            customer_name=None,
            customer_phone=None,
        )

        self.db.add(order)
        self.db.flush()

        # 7. Cria o item do pedido (OrderProduct)
        order_product = models.OrderProduct(
            order_id=order.id,
            store_id=store_id,
            product_id=request.product_id,
            category_id=request.category_id,
            name=product.name,
            price=base_price,
            original_price=base_price,
            quantity=request.quantity,
            note=request.note or "",
        )
        self.db.add(order_product)
        self.db.flush()

        # 8. Processa as variantes
        total_variants_price = 0
        for variant_data in request.variants:
            order_variant = models.OrderVariant(
                order_product_id=order_product.id,
                variant_id=variant_data.variant_id,
                store_id=store_id,
                name="",  # Será preenchido depois
            )
            self.db.add(order_variant)
            self.db.flush()

            for option_data in variant_data.options:
                variant_option = self.db.query(models.VariantOption).filter(
                    models.VariantOption.id == option_data.variant_option_id
                ).first()

                if variant_option:
                    order_variant_option = models.OrderVariantOption(
                        order_variant_id=order_variant.id,
                        variant_option_id=option_data.variant_option_id,
                        store_id=store_id,
                        name=variant_option.resolved_name,
                        price=variant_option.resolved_price,
                        quantity=option_data.quantity,
                    )
                    self.db.add(order_variant_option)
                    total_variants_price += variant_option.resolved_price * option_data.quantity

        # 9. Calcula o total do pedido
        item_total = (base_price * request.quantity) + total_variants_price
        order.total_price = item_total
        order.subtotal_price = item_total
        order.discounted_total_price = item_total

        self.db.commit()
        self.db.refresh(order)
        return order

    def remove_item_from_table(self, store_id: int, order_product_id: int, command_id: int) -> bool:
        """Remove um item do pedido de uma mesa"""
        order_product = self.db.query(models.OrderProduct).filter(
            models.OrderProduct.id == order_product_id,
            models.OrderProduct.store_id == store_id
        ).first()

        if not order_product:
            raise ValueError("Item não encontrado")

        # Valida se o item pertence a um pedido da comanda
        order = self.db.query(models.Order).filter(
            models.Order.id == order_product.order_id,
            models.Order.command_id == command_id
        ).first()

        if not order:
            raise ValueError("Item não pertence a esta comanda")

        # Remove o item
        self.db.delete(order_product)

        # Recalcula o total do pedido
        remaining_items = self.db.query(models.OrderProduct).filter(
            models.OrderProduct.order_id == order.id
        ).all()

        if not remaining_items:
            # Se não há mais itens, cancela o pedido
            order.order_status = OrderStatus.CANCELLED
        else:
            # Recalcula o total
            new_total = sum(item.price * item.quantity for item in remaining_items)
            order.total_price = new_total
            order.subtotal_price = new_total
            order.discounted_total_price = new_total

        self.db.commit()
        return True

    # ========== MÉTODOS AUXILIARES ==========

    def _get_next_sequential_id(self, store_id: int) -> int:
        """Gera o próximo ID sequencial para pedidos da loja"""
        last_order = self.db.query(models.Order).filter(
            models.Order.store_id == store_id
        ).order_by(models.Order.sequential_id.desc()).first()

        return (last_order.sequential_id + 1) if last_order else 1

    def _generate_public_id(self, store_id: int) -> str:
        """Gera um ID público único para o pedido"""
        from datetime import datetime
        import random
        timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
        random_suffix = random.randint(1000, 9999)
        return f"{store_id}{timestamp}{random_suffix}"

    def get_table_with_details(self, table_id: int, store_id: int) -> models.Tables:
        """Busca uma mesa com todos os relacionamentos carregados"""
        return self.db.query(models.Tables).options(
            selectinload(models.Tables.commands),
            selectinload(models.Tables.orders)
        ).filter(
            models.Tables.id == table_id,
            models.Tables.store_id == store_id
        ).first()