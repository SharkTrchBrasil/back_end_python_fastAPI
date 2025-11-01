"""
Menu Public Service - Cardápio Digital para Clientes
====================================================
Serviço completo para visualização pública do cardápio
"""

from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
from sqlalchemy.orm import Session, selectinload, joinedload
from sqlalchemy import and_, or_, func
from decimal import Decimal
import json

from src.core import models
from src.core.utils.enums import CategoryType, AvailabilityTypeEnum


class MenuPublicService:
    """Serviço para cardápio digital público (cliente)"""
    
    def __init__(self, db: Session):
        self.db = db
    
    # ═══════════════════════════════════════════════════════════
    # CARDÁPIO PÚBLICO
    # ═══════════════════════════════════════════════════════════
    
    def get_public_menu(
        self,
        store_id: int,
        search: Optional[str] = None,
        category_id: Optional[int] = None,
        filters: Optional[Dict[str, Any]] = None,
        sort_by: str = "priority",  # priority, price, name, popularity
        lang: str = "pt"
    ) -> Dict[str, Any]:
        """
        Retorna cardápio completo formatado para cliente
        
        Args:
            store_id: ID da loja
            search: Termo de busca
            category_id: Filtrar por categoria
            filters: Filtros adicionais (vegetariano, sem glúten, etc)
            sort_by: Ordenação
            lang: Idioma (pt, en, es)
            
        Returns:
            Cardápio estruturado com categorias e produtos
        """
        
        # Busca loja com configurações
        store = self.db.query(models.Store).filter(
            models.Store.id == store_id,
            models.Store.is_active == True
        ).first()
        
        if not store:
            raise ValueError("Loja não encontrada ou inativa")
        
        # Busca categorias ativas
        categories_query = self.db.query(models.Category).options(
            selectinload(models.Category.option_groups).selectinload(
                models.OptionGroup.items
            ),
            selectinload(models.Category.schedules).selectinload(
                models.CategorySchedule.time_shifts
            )
        ).filter(
            models.Category.store_id == store_id,
            models.Category.is_active == True
        )
        
        if category_id:
            categories_query = categories_query.filter(
                models.Category.id == category_id
            )
        
        categories = categories_query.order_by(
            models.Category.priority.asc()
        ).all()
        
        # Processa categorias
        menu_categories = []
        for category in categories:
            # Verifica disponibilidade por horário
            if not self._is_category_available(category):
                continue
            
            # Busca produtos da categoria
            products = self._get_category_products(
                category.id,
                search=search,
                filters=filters,
                sort_by=sort_by
            )
            
            # Só inclui categoria se tiver produtos
            if products:
                menu_categories.append({
                    "id": category.id,
                    "name": self._translate(category.name, lang),
                    "type": category.type.value,
                    "image": category.file_key,  # URL da imagem
                    "products_count": len(products),
                    "products": products,
                    "option_groups": self._format_option_groups(
                        category.option_groups, lang
                    ) if category.type == CategoryType.CUSTOMIZABLE else None,
                    "availability": {
                        "type": category.availability_type.value,
                        "schedules": self._format_schedules(category.schedules)
                    }
                })
        
        # Monta resposta
        return {
            "store": {
                "id": store.id,
                "name": store.name,
                "logo": store.logo_url,
                "description": store.description,
                "address": f"{store.street}, {store.city} - {store.state}",
                "phone": store.phone,
                "delivery_time": "30-45 min",  # TODO: Pegar do config
                "minimum_order": 20.00,  # TODO: Pegar do config
                "is_open": self._is_store_open(store)
            },
            "categories": menu_categories,
            "total_products": sum(c["products_count"] for c in menu_categories),
            "filters_available": self._get_available_filters(store_id),
            "last_updated": datetime.now(timezone.utc).isoformat()
        }
    
    def get_product_details(
        self,
        product_id: int,
        lang: str = "pt"
    ) -> Dict[str, Any]:
        """
        Retorna detalhes completos de um produto
        
        Args:
            product_id: ID do produto
            lang: Idioma
            
        Returns:
            Produto com todas as opções e customizações
        """
        
        # Busca produto com relacionamentos
        product = self.db.query(models.Product).options(
            selectinload(models.Product.prices).selectinload(
                models.FlavorPrice.size_option
            ),
            selectinload(models.Product.product_links).selectinload(
                models.ProductCategoryLink.category
            ).selectinload(
                models.Category.option_groups
            ).selectinload(
                models.OptionGroup.items
            ),
            selectinload(models.Product.product_ratings)
        ).filter(
            models.Product.id == product_id,
            models.Product.is_active == True
        ).first()
        
        if not product:
            raise ValueError("Produto não encontrado")
        
        # Calcula rating médio
        ratings = product.product_ratings
        avg_rating = 0
        if ratings:
            avg_rating = sum(r.stars for r in ratings) / len(ratings)
        
        # Formata produto
        return {
            "id": product.id,
            "name": self._translate(product.name, lang),
            "description": self._translate(product.description, lang),
            "images": [product.file_key] if product.file_key else [],
            "price": float(product.price / 100),  # Converte para reais
            "original_price": float(product.original_price / 100) if product.original_price else None,
            "discount_percentage": self._calculate_discount(
                product.original_price, product.price
            ),
            "category": {
                "id": product.product_links[0].category.id,
                "name": product.product_links[0].category.name,
                "type": product.product_links[0].category.type.value
            } if product.product_links else None,
            "nutritional_info": json.loads(product.nutritional_info) if product.nutritional_info else None,
            "allergens": self._get_allergens(product),
            "preparation_time": product.preparation_time or "15-20 min",
            "rating": {
                "average": round(avg_rating, 1),
                "count": len(ratings)
            },
            "in_stock": product.is_available and (
                product.stock_quantity > 0 if product.stock_quantity is not None else True
            ),
            "stock_quantity": product.stock_quantity,
            "tags": self._get_product_tags(product, lang),
            "customizations": self._get_product_customizations(product, lang),
            "size_prices": self._get_size_prices(product) if product.prices else None,
            "min_quantity": 1,
            "max_quantity": product.stock_quantity or 99
        }
    
    def search_products(
        self,
        store_id: int,
        query: str,
        limit: int = 20,
        offset: int = 0,
        lang: str = "pt"
    ) -> List[Dict[str, Any]]:
        """
        Busca produtos por nome ou descrição
        
        Args:
            store_id: ID da loja
            query: Termo de busca
            limit: Limite de resultados
            offset: Offset para paginação
            lang: Idioma
            
        Returns:
            Lista de produtos encontrados
        """
        
        # Busca produtos
        products = self.db.query(models.Product).join(
            models.ProductCategoryLink
        ).join(
            models.Category
        ).filter(
            models.Category.store_id == store_id,
            models.Product.is_active == True,
            models.Category.is_active == True,
            or_(
                func.lower(models.Product.name).contains(query.lower()),
                func.lower(models.Product.description).contains(query.lower())
            )
        ).offset(offset).limit(limit).all()
        
        # Formata resultados
        results = []
        for product in products:
            results.append({
                "id": product.id,
                "name": self._translate(product.name, lang),
                "description": self._translate(product.description, lang)[:100] + "...",
                "price": float(product.price / 100),
                "image": product.file_key,
                "category_name": product.product_links[0].category.name if product.product_links else None,
                "in_stock": product.is_available
            })
        
        return results
    
    # ═══════════════════════════════════════════════════════════
    # CARRINHO DE COMPRAS
    # ═══════════════════════════════════════════════════════════
    
    def validate_cart_item(
        self,
        product_id: int,
        quantity: int,
        customizations: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Valida item antes de adicionar ao carrinho
        
        Args:
            product_id: ID do produto
            quantity: Quantidade
            customizations: Opções selecionadas
            
        Returns:
            Item validado com preço calculado
        """
        
        # Busca produto
        product = self.db.query(models.Product).filter(
            models.Product.id == product_id,
            models.Product.is_active == True
        ).first()
        
        if not product:
            raise ValueError("Produto não encontrado")
        
        if not product.is_available:
            raise ValueError("Produto fora de estoque")
        
        # Verifica quantidade em estoque
        if product.stock_quantity is not None:
            if quantity > product.stock_quantity:
                raise ValueError(f"Apenas {product.stock_quantity} unidades disponíveis")
        
        # Calcula preço base
        unit_price = product.price
        
        # Adiciona customizações
        customization_price = 0
        selected_options = []
        
        if customizations:
            # Valida e calcula preço das customizações
            for group_id, option_ids in customizations.items():
                group = self.db.query(models.OptionGroup).filter(
                    models.OptionGroup.id == int(group_id)
                ).first()
                
                if not group:
                    continue
                
                # Verifica limites de seleção
                if isinstance(option_ids, list):
                    if len(option_ids) < group.min_selection:
                        raise ValueError(
                            f"Selecione pelo menos {group.min_selection} opções em {group.name}"
                        )
                    if len(option_ids) > group.max_selection:
                        raise ValueError(
                            f"Selecione no máximo {group.max_selection} opções em {group.name}"
                        )
                    
                    # Calcula preço das opções
                    for option_id in option_ids:
                        option = self.db.query(models.OptionItem).filter(
                            models.OptionItem.id == option_id,
                            models.OptionItem.option_group_id == group_id,
                            models.OptionItem.is_active == True
                        ).first()
                        
                        if option:
                            customization_price += int(option.price * 100)  # Converte para centavos
                            selected_options.append({
                                "group": group.name,
                                "option": option.name,
                                "price": float(option.price)
                            })
        
        # Preço total
        total_price = (unit_price + customization_price) * quantity
        
        return {
            "valid": True,
            "product_id": product.id,
            "product_name": product.name,
            "quantity": quantity,
            "unit_price": float(unit_price / 100),
            "customization_price": float(customization_price / 100),
            "total_price": float(total_price / 100),
            "selected_options": selected_options
        }
    
    # ═══════════════════════════════════════════════════════════
    # MÉTODOS AUXILIARES
    # ═══════════════════════════════════════════════════════════
    
    def _get_category_products(
        self,
        category_id: int,
        search: Optional[str] = None,
        filters: Optional[Dict[str, Any]] = None,
        sort_by: str = "priority"
    ) -> List[Dict[str, Any]]:
        """Busca produtos de uma categoria com filtros"""
        
        # Query base
        query = self.db.query(models.Product).join(
            models.ProductCategoryLink
        ).filter(
            models.ProductCategoryLink.category_id == category_id,
            models.Product.is_active == True
        )
        
        # Aplica busca
        if search:
            query = query.filter(
                or_(
                    func.lower(models.Product.name).contains(search.lower()),
                    func.lower(models.Product.description).contains(search.lower())
                )
            )
        
        # Aplica filtros
        if filters:
            # TODO: Implementar filtros por tags, preço, etc
            pass
        
        # Ordenação
        if sort_by == "price":
            query = query.order_by(models.Product.price.asc())
        elif sort_by == "name":
            query = query.order_by(models.Product.name.asc())
        elif sort_by == "popularity":
            # TODO: Implementar ordenação por popularidade
            query = query.order_by(models.Product.priority.asc())
        else:  # priority
            query = query.order_by(models.Product.priority.asc())
        
        products = query.all()
        
        # Formata produtos
        formatted_products = []
        for product in products:
            formatted_products.append({
                "id": product.id,
                "name": product.name,
                "description": product.description,
                "price": float(product.price / 100),
                "original_price": float(product.original_price / 100) if product.original_price else None,
                "image": product.file_key,
                "in_stock": product.is_available,
                "preparation_time": product.preparation_time,
                "tags": self._get_product_tags(product, "pt")
            })
        
        return formatted_products
    
    def _is_category_available(self, category: models.Category) -> bool:
        """Verifica se categoria está disponível no horário atual"""
        
        if category.availability_type == AvailabilityTypeEnum.ALWAYS:
            return True
        
        if category.availability_type == AvailabilityTypeEnum.NEVER:
            return False
        
        # Verifica schedules
        if category.availability_type == AvailabilityTypeEnum.SCHEDULED:
            now = datetime.now()
            day_of_week = now.weekday()
            current_time = now.time()
            
            for schedule in category.schedules:
                if day_of_week in schedule.days_of_week:
                    for shift in schedule.time_shifts:
                        if shift.start_time <= current_time <= shift.end_time:
                            return True
        
        return False
    
    def _is_store_open(self, store: models.Store) -> bool:
        """Verifica se loja está aberta"""
        
        if not store.is_active:
            return False
        
        # TODO: Verificar StoreHours
        return True
    
    def _format_option_groups(
        self, 
        option_groups: List[models.OptionGroup],
        lang: str
    ) -> List[Dict[str, Any]]:
        """Formata grupos de opções para frontend"""
        
        formatted = []
        for group in option_groups:
            if not group.items:
                continue
            
            formatted.append({
                "id": group.id,
                "name": self._translate(group.name, lang),
                "min_selection": group.min_selection,
                "max_selection": group.max_selection,
                "required": group.min_selection > 0,
                "type": group.group_type.value if group.group_type else "GENERIC",
                "options": [
                    {
                        "id": item.id,
                        "name": self._translate(item.name, lang),
                        "description": self._translate(item.description, lang) if item.description else None,
                        "price": float(item.price),
                        "is_available": item.is_active,
                        "tags": item.tags if hasattr(item, 'tags') else []
                    }
                    for item in group.items
                    if item.is_active
                ]
            })
        
        return formatted
    
    def _format_schedules(
        self,
        schedules: List[models.CategorySchedule]
    ) -> List[Dict[str, Any]]:
        """Formata horários de disponibilidade"""
        
        formatted = []
        days_map = {
            0: "Segunda",
            1: "Terça",
            2: "Quarta",
            3: "Quinta", 
            4: "Sexta",
            5: "Sábado",
            6: "Domingo"
        }
        
        for schedule in schedules:
            for shift in schedule.time_shifts:
                formatted.append({
                    "days": [days_map.get(d, str(d)) for d in schedule.days_of_week],
                    "start": shift.start_time.strftime("%H:%M"),
                    "end": shift.end_time.strftime("%H:%M")
                })
        
        return formatted
    
    def _get_product_tags(self, product: models.Product, lang: str) -> List[str]:
        """Retorna tags do produto traduzidas"""
        
        tags = []
        
        # TODO: Implementar tags do produto
        # Por enquanto, retorna tags básicas
        if hasattr(product, 'is_vegetarian') and product.is_vegetarian:
            tags.append(self._translate("Vegetariano", lang))
        
        if hasattr(product, 'is_vegan') and product.is_vegan:
            tags.append(self._translate("Vegano", lang))
        
        if hasattr(product, 'is_gluten_free') and product.is_gluten_free:
            tags.append(self._translate("Sem Glúten", lang))
        
        return tags
    
    def _get_allergens(self, product: models.Product) -> List[str]:
        """Retorna alergênicos do produto"""
        
        # TODO: Implementar campo de alergênicos no produto
        allergens = []
        
        if hasattr(product, 'allergens') and product.allergens:
            return json.loads(product.allergens)
        
        return allergens
    
    def _get_product_customizations(
        self,
        product: models.Product,
        lang: str
    ) -> List[Dict[str, Any]]:
        """Retorna opções de customização do produto"""
        
        customizations = []
        
        # Pega categoria do produto
        if product.product_links:
            category = product.product_links[0].category
            if category.type == CategoryType.CUSTOMIZABLE and category.option_groups:
                customizations = self._format_option_groups(
                    category.option_groups,
                    lang
                )
        
        return customizations
    
    def _get_size_prices(self, product: models.Product) -> List[Dict[str, Any]]:
        """Retorna preços por tamanho se houver"""
        
        size_prices = []
        
        for price in product.prices:
            if price.size_option:
                size_prices.append({
                    "size_id": price.size_option_id,
                    "size_name": price.size_option.name,
                    "price": float(price.price / 100),
                    "is_available": price.is_available if hasattr(price, 'is_available') else True
                })
        
        return size_prices
    
    def _calculate_discount(
        self,
        original_price: Optional[int],
        current_price: int
    ) -> Optional[float]:
        """Calcula percentual de desconto"""
        
        if not original_price or original_price <= current_price:
            return None
        
        discount = ((original_price - current_price) / original_price) * 100
        return round(discount, 0)
    
    def _get_available_filters(self, store_id: int) -> Dict[str, List[str]]:
        """Retorna filtros disponíveis para o cardápio"""
        
        return {
            "dietary": [
                {"id": "vegetarian", "label": "Vegetariano", "icon": "🥗"},
                {"id": "vegan", "label": "Vegano", "icon": "🌱"},
                {"id": "gluten_free", "label": "Sem Glúten", "icon": "🌾"},
                {"id": "lactose_free", "label": "Sem Lactose", "icon": "🥛"},
                {"id": "sugar_free", "label": "Sem Açúcar", "icon": "🍯"}
            ],
            "spice_level": [
                {"id": "mild", "label": "Suave", "icon": "🌶️"},
                {"id": "medium", "label": "Médio", "icon": "🌶️🌶️"},
                {"id": "hot", "label": "Picante", "icon": "🌶️🌶️🌶️"}
            ],
            "price_range": [
                {"id": "0-20", "label": "Até R$ 20", "min": 0, "max": 20},
                {"id": "20-40", "label": "R$ 20 - 40", "min": 20, "max": 40},
                {"id": "40-60", "label": "R$ 40 - 60", "min": 40, "max": 60},
                {"id": "60+", "label": "Acima de R$ 60", "min": 60, "max": None}
            ]
        }
    
    def _translate(self, text: str, lang: str) -> str:
        """Traduz texto para o idioma solicitado"""
        
        # TODO: Implementar sistema de tradução real
        # Por enquanto retorna o texto original
        return text
