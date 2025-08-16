from datetime import datetime, timezone

from sqlalchemy.orm import Session
from src.core import models

class CouponValidator:
    def __init__(self, db, coupon: models.Coupon, cart: models.Cart, customer: models.Customer):
        self.db = db
        self.coupon = coupon
        self.cart = cart
        self.customer = customer
        self.error_message = None

    def validate(self) -> bool:
        """Executa todas as validações. Retorna True se o cupom for válido."""
        # Validações básicas do cupom
        if not self.coupon.is_active or self.coupon.start_date > datetime.now(timezone.utc) or self.coupon.end_date < datetime.now(timezone.utc):
            self.error_message = "Cupom inválido ou expirado."
            return False

        # Itera e valida cada regra associada ao cupom
        for rule in self.coupon.rules:
            is_valid = self._check_rule(rule)
            if not is_valid:
                return False # A primeira regra que falhar, para o processo

        return True

    def _check_rule(self, rule: models.CouponRule) -> bool:
        """Direciona a validação para o método correto baseado no tipo de regra."""
        handler = getattr(self, f"_validate_{rule.rule_type.lower()}", None)
        if not handler:
            print(f"AVISO: Nenhuma função de validação para a regra '{rule.rule_type}'")
            return True # Ou False, se regras desconhecidas devem invalidar
        return handler(rule)

    # --- MÉTODOS DE VALIDAÇÃO PARA CADA TIPO DE REGRA ---

    def _validate_min_subtotal(self, rule: models.CouponRule) -> bool:
        min_value = rule.value.get('value')
        if self.cart.subtotal < min_value:
            self.error_message = f"O pedido mínimo para este cupom é de R$ {min_value/100:.2f}."
            return False
        return True

    def _validate_first_order(self, rule: models.CouponRule) -> bool:
        order_count = self.db.query(models.Order).filter(models.Order.customer_id == self.customer.id).count()
        if order_count > 0:
            self.error_message = "Este cupom é válido apenas para a primeira compra."
            return False
        return True

    def _validate_max_uses_per_customer(self, rule: models.CouponRule) -> bool:
        limit = rule.value.get('limit', 1)
        usage_count = self.db.query(models.CouponUsage).filter_by(coupon_id=self.coupon.id, customer_id=self.customer.id).count()
        if usage_count >= limit:
            self.error_message = "Você já utilizou o limite de usos para este cupom."
            return False
        return True

    def _validate_target_product(self, rule: models.CouponRule) -> bool:
        product_id = rule.value.get('product_id')
        if not any(item.product_id == product_id for item in self.cart.items):
            self.error_message = "Este cupom requer um produto específico que não está na sua sacola."
            return False
        return True

    # ✅ NOVO: Validação para Categoria Específica
    def _validate_target_category(self, rule: models.CouponRule) -> bool:
        """Verifica se o carrinho contém algum item da categoria alvo."""
        target_category_id = rule.value.get('category_id')
        if not target_category_id:
            print(f"AVISO: Regra de categoria para cupom {self.coupon.id} mal configurada.")
            return False  # A regra está mal formada, então falha.

        # Cria um conjunto com todos os IDs de categoria presentes no carrinho para uma busca rápida
        cart_category_ids = {item.product.category_id for item in self.cart.items if
                             item.product and item.product.category_id}

        if target_category_id not in cart_category_ids:
            self.error_message = "Este cupom é válido apenas para uma categoria de produtos específica."
            return False
        return True

    # ✅ NOVO: Validação para Limite de Usos Totais
    def _validate_max_uses_total(self, rule: models.CouponRule) -> bool:
        """Verifica se o cupom já atingiu o seu limite de uso geral."""
        limit = rule.value.get('limit')
        if limit is None:
            print(f"AVISO: Regra de uso total para cupom {self.coupon.id} mal configurada.")
            return False

        # Conta de forma eficiente no banco de dados sem carregar todos os objetos
        usage_count = self.db.query(models.CouponUsage).filter_by(coupon_id=self.coupon.id).count()

        if usage_count >= limit:
            self.error_message = "Este cupom já atingiu o limite máximo de utilizações."
            return False
        return True