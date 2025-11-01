"""
Customer Order Service - Pedidos do Cliente
===========================================
Sistema completo de pedidos para clientes do cardápio digital
"""

import uuid
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from sqlalchemy.orm import Session, selectinload
from sqlalchemy import and_, or_

from src.core import models
from src.core.utils.enums import (
    OrderStatus, 
    PaymentStatus, 
    CommandStatus,
    SalesChannel
)
from src.api.admin.socketio.socketio_manager import event_emitter


class CustomerOrderService:
    """Serviço para pedidos de clientes via cardápio digital"""
    
    def __init__(self, db: Session):
        self.db = db
    
    # ═══════════════════════════════════════════════════════════
    # CRIAÇÃO DE PEDIDO
    # ═══════════════════════════════════════════════════════════
    
    def create_customer_order(
        self,
        store_id: int,
        table_token: Optional[str],
        cart_items: List[Dict[str, Any]],
        customer_info: Dict[str, Any],
        notes: Optional[str] = None,
        schedule_time: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        Cria pedido a partir do carrinho do cliente
        
        Args:
            store_id: ID da loja
            table_token: Token da mesa (opcional para delivery)
            cart_items: Itens do carrinho com customizações
            customer_info: Informações do cliente
            notes: Observações do pedido
            schedule_time: Horário agendado (opcional)
            
        Returns:
            Pedido criado com número e detalhes
        """
        
        # Valida loja
        store = self.db.query(models.Store).filter(
            models.Store.id == store_id,
            models.Store.is_active == True
        ).first()
        
        if not store:
            raise ValueError("Loja não encontrada ou inativa")
        
        # Busca mesa se houver token
        table = None
        command = None
        
        if table_token:
            table = self.db.query(models.Tables).filter(
                models.Tables.table_token == table_token,
                models.Tables.store_id == store_id
            ).first()
            
            if table:
                # Verifica se há comanda ativa
                command = self.db.query(models.Command).filter(
                    models.Command.table_id == table.id,
                    models.Command.status == CommandStatus.ACTIVE
                ).first()
                
                # Se não houver comanda, cria uma
                if not command:
                    command = models.Command(
                        store_id=store_id,
                        table_id=table.id,
                        customer_name=customer_info.get('name'),
                        customer_contact=customer_info.get('phone'),
                        status=CommandStatus.ACTIVE
                    )
                    self.db.add(command)
                    self.db.flush()
        
        # Calcula totais
        subtotal = 0
        preparation_time = 0
        order_items_data = []
        
        for item in cart_items:
            # Valida produto
            product = self.db.query(models.Product).filter(
                models.Product.id == item['product_id'],
                models.Product.is_active == True
            ).first()
            
            if not product:
                raise ValueError(f"Produto {item['product_id']} não encontrado")
            
            if not product.is_available:
                raise ValueError(f"Produto {product.name} fora de estoque")
            
            # Calcula preço do item
            unit_price = product.price
            customization_price = 0
            customization_text = []
            
            # Processa customizações
            if item.get('customizations'):
                for group_id, option_ids in item['customizations'].items():
                    if isinstance(option_ids, list):
                        for option_id in option_ids:
                            option = self.db.query(models.OptionItem).filter(
                                models.OptionItem.id == option_id
                            ).first()
                            if option:
                                customization_price += int(option.price * 100)
                                customization_text.append(option.name)
                    else:
                        option = self.db.query(models.OptionItem).filter(
                            models.OptionItem.id == option_ids
                        ).first()
                        if option:
                            customization_price += int(option.price * 100)
                            customization_text.append(option.name)
            
            # Total do item
            quantity = item['quantity']
            item_total = (unit_price + customization_price) * quantity
            subtotal += item_total
            
            # Tempo de preparo
            if product.preparation_time:
                try:
                    prep_minutes = int(product.preparation_time.split('-')[0])
                    preparation_time = max(preparation_time, prep_minutes)
                except:
                    preparation_time = max(preparation_time, 20)
            
            # Adiciona dados do item
            order_items_data.append({
                'product': product,
                'quantity': quantity,
                'unit_price': unit_price,
                'customization_price': customization_price,
                'total_price': item_total,
                'notes': item.get('notes', ''),
                'customizations': ', '.join(customization_text) if customization_text else None
            })
        
        # Aplica taxas e descontos
        service_fee = int(subtotal * 0.1)  # 10% de taxa de serviço
        delivery_fee = 0  # TODO: Calcular baseado no endereço
        discount = 0  # TODO: Aplicar cupons
        
        total = subtotal + service_fee + delivery_fee - discount
        
        # Gera número único do pedido
        order_number = self._generate_order_number()
        
        # Cria pedido
        order = models.Order(
            store_id=store_id,
            command_id=command.id if command else None,
            order_number=order_number,
            customer_name=customer_info.get('name'),
            customer_phone=customer_info.get('phone'),
            customer_email=customer_info.get('email'),
            order_status=OrderStatus.PENDING,
            payment_status=PaymentStatus.PENDING,
            order_type=SalesChannel.TABLE if table else SalesChannel.ONLINE,
            subtotal_price=subtotal,
            delivery_fee=delivery_fee,
            service_fee=service_fee,
            discount_amount=discount,
            total_price=total,
            discounted_total_price=total,
            notes=notes,
            preparation_time=preparation_time,
            schedule_time=schedule_time,
            created_at=datetime.now(timezone.utc)
        )
        
        self.db.add(order)
        self.db.flush()
        
        # Cria itens do pedido
        for item_data in order_items_data:
            order_item = models.OrderProduct(
                order_id=order.id,
                product_id=item_data['product'].id,
                product_name=item_data['product'].name,
                quantity=item_data['quantity'],
                unit_price=item_data['unit_price'],
                customization_price=item_data['customization_price'],
                total_price=item_data['total_price'],
                notes=item_data['notes'],
                customizations=item_data['customizations']
            )
            self.db.add(order_item)
        
        # Atualiza estoque se necessário
        for item in cart_items:
            product = self.db.query(models.Product).filter(
                models.Product.id == item['product_id']
            ).first()
            
            if product and product.stock_quantity is not None:
                product.stock_quantity -= item['quantity']
                if product.stock_quantity <= 0:
                    product.is_available = False
        
        # Confirma transação
        self.db.commit()
        self.db.refresh(order)
        
        # Emite eventos em tempo real
        self._emit_new_order_event(order)
        
        # Envia notificação sonora para cozinha
        self._notify_kitchen(order)
        
        return {
            "success": True,
            "order_id": order.id,
            "order_number": order_number,
            "status": order.order_status.value,
            "total": float(total / 100),
            "preparation_time": preparation_time,
            "estimated_time": (datetime.now(timezone.utc) + timedelta(minutes=preparation_time)).isoformat(),
            "table": {
                "id": table.id,
                "name": table.name
            } if table else None,
            "payment_pending": True,
            "message": "Pedido criado com sucesso! Aguardando confirmação do pagamento."
        }
    
    # ═══════════════════════════════════════════════════════════
    # ACOMPANHAMENTO DO PEDIDO
    # ═══════════════════════════════════════════════════════════
    
    def get_order_status(
        self,
        order_number: str,
        customer_phone: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Retorna status atualizado do pedido
        
        Args:
            order_number: Número do pedido
            customer_phone: Telefone para validação (opcional)
            
        Returns:
            Status e detalhes do pedido
        """
        
        # Busca pedido
        query = self.db.query(models.Order).filter(
            models.Order.order_number == order_number
        )
        
        if customer_phone:
            query = query.filter(
                models.Order.customer_phone == customer_phone
            )
        
        order = query.first()
        
        if not order:
            raise ValueError("Pedido não encontrado")
        
        # Busca itens
        items = self.db.query(models.OrderProduct).filter(
            models.OrderProduct.order_id == order.id
        ).all()
        
        # Calcula progresso
        progress = self._calculate_order_progress(order)
        
        return {
            "order_number": order.order_number,
            "status": order.order_status.value,
            "status_display": self._get_status_display(order.order_status),
            "progress": progress,
            "created_at": order.created_at.isoformat(),
            "estimated_time": (
                order.created_at + timedelta(minutes=order.preparation_time)
            ).isoformat() if order.preparation_time else None,
            "items": [
                {
                    "name": item.product_name,
                    "quantity": item.quantity,
                    "customizations": item.customizations,
                    "notes": item.notes
                }
                for item in items
            ],
            "total": float(order.total_price / 100),
            "payment_status": order.payment_status.value,
            "can_cancel": order.order_status in [
                OrderStatus.PENDING,
                OrderStatus.CONFIRMED
            ],
            "timeline": self._get_order_timeline(order)
        }
    
    def cancel_order(
        self,
        order_id: int,
        reason: str,
        customer_phone: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Cancela pedido se ainda não saiu da cozinha
        
        Args:
            order_id: ID do pedido
            reason: Motivo do cancelamento
            customer_phone: Telefone para validação
            
        Returns:
            Confirmação do cancelamento
        """
        
        # Busca pedido
        query = self.db.query(models.Order).filter(
            models.Order.id == order_id
        )
        
        if customer_phone:
            query = query.filter(
                models.Order.customer_phone == customer_phone
            )
        
        order = query.first()
        
        if not order:
            raise ValueError("Pedido não encontrado")
        
        # Verifica se pode cancelar
        if order.order_status not in [OrderStatus.PENDING, OrderStatus.CONFIRMED]:
            raise ValueError("Pedido não pode mais ser cancelado")
        
        # Cancela pedido
        order.order_status = OrderStatus.CANCELLED
        order.cancelled_at = datetime.now(timezone.utc)
        order.cancellation_reason = reason
        
        # Restaura estoque
        items = self.db.query(models.OrderProduct).filter(
            models.OrderProduct.order_id == order.id
        ).all()
        
        for item in items:
            product = self.db.query(models.Product).filter(
                models.Product.id == item.product_id
            ).first()
            
            if product and product.stock_quantity is not None:
                product.stock_quantity += item.quantity
                product.is_available = True
        
        # Se pagamento foi feito, marcar para reembolso
        if order.payment_status == PaymentStatus.PAID:
            order.payment_status = PaymentStatus.REFUND_PENDING
        
        self.db.commit()
        
        # Emite evento de cancelamento
        self._emit_order_cancelled_event(order)
        
        return {
            "success": True,
            "message": "Pedido cancelado com sucesso",
            "refund_pending": order.payment_status == PaymentStatus.REFUND_PENDING
        }
    
    def rate_order(
        self,
        order_id: int,
        rating: int,
        comment: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Avalia pedido após conclusão
        
        Args:
            order_id: ID do pedido
            rating: Nota de 1 a 5
            comment: Comentário opcional
            
        Returns:
            Confirmação da avaliação
        """
        
        # Busca pedido
        order = self.db.query(models.Order).filter(
            models.Order.id == order_id,
            models.Order.order_status == OrderStatus.DELIVERED
        ).first()
        
        if not order:
            raise ValueError("Pedido não encontrado ou não finalizado")
        
        # Cria avaliação
        # TODO: Criar modelo OrderRating
        # rating = models.OrderRating(
        #     order_id=order_id,
        #     rating=rating,
        #     comment=comment,
        #     created_at=datetime.now(timezone.utc)
        # )
        # self.db.add(rating)
        
        # Atualiza rating dos produtos
        items = self.db.query(models.OrderProduct).filter(
            models.OrderProduct.order_id == order_id
        ).all()
        
        for item in items:
            product_rating = models.ProductRating(
                product_id=item.product_id,
                order_id=order_id,
                stars=rating,
                comment=comment
            )
            self.db.add(product_rating)
        
        self.db.commit()
        
        return {
            "success": True,
            "message": "Obrigado pela sua avaliação!"
        }
    
    # ═══════════════════════════════════════════════════════════
    # MÉTODOS AUXILIARES
    # ═══════════════════════════════════════════════════════════
    
    def _generate_order_number(self) -> str:
        """Gera número único do pedido"""
        
        # Formato: YYYYMMDD-XXXX
        today = datetime.now().strftime('%Y%m%d')
        
        # Busca último pedido do dia
        last_order = self.db.query(models.Order).filter(
            models.Order.order_number.like(f"{today}-%")
        ).order_by(
            models.Order.order_number.desc()
        ).first()
        
        if last_order:
            # Incrementa sequencial
            last_seq = int(last_order.order_number.split('-')[1])
            new_seq = last_seq + 1
        else:
            new_seq = 1
        
        return f"{today}-{new_seq:04d}"
    
    def _calculate_order_progress(self, order: models.Order) -> int:
        """Calcula progresso do pedido (0-100)"""
        
        progress_map = {
            OrderStatus.PENDING: 10,
            OrderStatus.CONFIRMED: 20,
            OrderStatus.PREPARING: 40,
            OrderStatus.READY: 80,
            OrderStatus.OUT_FOR_DELIVERY: 90,
            OrderStatus.DELIVERED: 100,
            OrderStatus.CANCELLED: 0
        }
        
        return progress_map.get(order.order_status, 0)
    
    def _get_status_display(self, status: OrderStatus) -> str:
        """Retorna texto amigável do status"""
        
        display_map = {
            OrderStatus.PENDING: "Aguardando confirmação",
            OrderStatus.CONFIRMED: "Pedido confirmado", 
            OrderStatus.PREPARING: "Preparando seu pedido",
            OrderStatus.READY: "Pedido pronto!",
            OrderStatus.OUT_FOR_DELIVERY: "Saiu para entrega",
            OrderStatus.DELIVERED: "Entregue",
            OrderStatus.CANCELLED: "Cancelado"
        }
        
        return display_map.get(status, status.value)
    
    def _get_order_timeline(self, order: models.Order) -> List[Dict[str, Any]]:
        """Retorna timeline do pedido"""
        
        timeline = []
        
        # Pedido criado
        timeline.append({
            "status": "created",
            "label": "Pedido recebido",
            "timestamp": order.created_at.isoformat(),
            "completed": True
        })
        
        # Confirmado
        if order.order_status.value >= OrderStatus.CONFIRMED.value:
            timeline.append({
                "status": "confirmed",
                "label": "Pedido confirmado",
                "timestamp": (order.created_at + timedelta(minutes=1)).isoformat(),
                "completed": True
            })
        
        # Preparando
        if order.order_status.value >= OrderStatus.PREPARING.value:
            timeline.append({
                "status": "preparing",
                "label": "Preparando",
                "timestamp": (order.created_at + timedelta(minutes=5)).isoformat(),
                "completed": True
            })
        
        # Pronto
        if order.order_status.value >= OrderStatus.READY.value:
            timeline.append({
                "status": "ready",
                "label": "Pronto para retirada",
                "timestamp": (order.created_at + timedelta(minutes=order.preparation_time or 20)).isoformat(),
                "completed": True
            })
        
        # Entregue
        if order.order_status == OrderStatus.DELIVERED:
            timeline.append({
                "status": "delivered",
                "label": "Entregue",
                "timestamp": order.delivered_at.isoformat() if order.delivered_at else datetime.now(timezone.utc).isoformat(),
                "completed": True
            })
        
        return timeline
    
    async def _emit_new_order_event(self, order: models.Order):
        """Emite evento de novo pedido via WebSocket"""
        
        try:
            await event_emitter.emit_order_update(
                store_id=order.store_id,
                order_data={
                    "id": order.id,
                    "number": order.order_number,
                    "status": order.order_status.value,
                    "table": order.command.table.name if order.command and order.command.table else None,
                    "total": float(order.total_price / 100),
                    "created_at": order.created_at.isoformat()
                }
            )
        except Exception as e:
            print(f"Erro ao emitir evento: {e}")
    
    async def _emit_order_cancelled_event(self, order: models.Order):
        """Emite evento de pedido cancelado"""
        
        try:
            await event_emitter.emit_notification(
                store_id=order.store_id,
                title="Pedido Cancelado",
                message=f"Pedido #{order.order_number} foi cancelado",
                level="warning",
                data={"order_id": order.id}
            )
        except Exception as e:
            print(f"Erro ao emitir evento: {e}")
    
    def _notify_kitchen(self, order: models.Order):
        """Envia notificação para cozinha"""
        
        # TODO: Implementar notificação sonora
        # - Tocar som na tela da cozinha
        # - Enviar push notification
        # - Imprimir automaticamente se configurado
        
        pass
