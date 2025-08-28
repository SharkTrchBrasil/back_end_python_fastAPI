from decimal import Decimal

from sqlalchemy import select, Boolean, JSON, Integer
import enum
from datetime import datetime, date, timezone
from typing import Optional, List

from sqlalchemy import DateTime, func, Index, LargeBinary, UniqueConstraint, Numeric, String, CheckConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


from src.core.utils.enums import CashbackType, TableStatus, CommandStatus, StoreVerificationStatus, PaymentMethodType, \
    CartStatus, ProductType, OrderStatus, PayableStatus, ThemeMode
from src.api.schemas.base_schema import VariantType, UIDisplayMode

from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy import ForeignKey, Enum, Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
import uuid

class Base(DeclarativeBase):
    pass


class TimestampMixin:
    # ✅ Otimizado com index=True
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        index=True  # <--- A ÚNICA MUDANÇA NECESSÁRIA
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now()
    )




class Store(Base, TimestampMixin):
    __tablename__ = "stores"

    id: Mapped[int] = mapped_column(primary_key=True)
    store_uuid: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        server_default=func.uuid_generate_v4(),
        unique=True,
        index=True,
        nullable=False
    )


    # --- Identificação Básica ---
    name: Mapped[str] = mapped_column()
    url_slug: Mapped[str] = mapped_column(unique=True, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    phone: Mapped[str | None] = mapped_column(nullable=True)
    cnpj: Mapped[str | None] = mapped_column(unique=True, index=True, nullable=True)
    segment_id: Mapped[int | None] = mapped_column(ForeignKey("segments.id"), nullable=True)

    # --- Endereço e Logística ---
    zip_code: Mapped[str | None] = mapped_column(nullable=True)
    street: Mapped[str | None] = mapped_column(nullable=True)
    number: Mapped[str | None] = mapped_column(nullable=True)
    complement: Mapped[str | None] = mapped_column(nullable=True)
    neighborhood: Mapped[str | None] = mapped_column(nullable=True)
    city: Mapped[str | None] = mapped_column(nullable=True)
    state: Mapped[str | None] = mapped_column(nullable=True)
    latitude: Mapped[float | None] = mapped_column(nullable=True)
    longitude: Mapped[float | None] = mapped_column(nullable=True)
    delivery_radius_km: Mapped[float | None] = mapped_column(nullable=True)

    # --- Operacional ---
    average_preparation_time: Mapped[int | None] = mapped_column(nullable=True)  # Em minutos
    order_number_prefix: Mapped[str | None] = mapped_column(nullable=True)
    manual_close_until: Mapped[datetime | None] = mapped_column(nullable=True)

    # --- Responsável Operacional ---
    responsible_name: Mapped[str | None] = mapped_column(nullable=True)
    responsible_phone: Mapped[str | None] = mapped_column(nullable=True)

    # --- Marketing e SEO ---
    tags: Mapped[list[str] | None] = mapped_column(ARRAY(String), nullable=True)
    meta_title: Mapped[str | None] = mapped_column(nullable=True)
    meta_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    rating_average: Mapped[float | None] = mapped_column(default=0.0)
    rating_count: Mapped[int | None] = mapped_column(default=0)
    file_key: Mapped[str | None] = mapped_column(nullable=True)
    banner_file_key: Mapped[str | None] = mapped_column(nullable=True)
    signature_file_key: Mapped[str | None] = mapped_column(nullable=True,
                                                           doc="Chave do arquivo da assinatura no serviço de armazenamento (S3, etc.)")
    # --- Gerenciamento da Plataforma ---
    is_active: Mapped[bool] = mapped_column(default=True)
    is_setup_complete: Mapped[bool] = mapped_column(default=False)
    is_featured: Mapped[bool] = mapped_column(default=False)
    verification_status: Mapped[StoreVerificationStatus] = mapped_column(
        Enum(StoreVerificationStatus), default=StoreVerificationStatus.UNVERIFIED
    )
    internal_notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # --- Relacionamentos (Seus relacionamentos existentes) ---
    segment: Mapped["Segment"] = relationship()


    coupons: Mapped[List["Coupon"]] = relationship(back_populates="store")
    # no Store
    store_customers = relationship("StoreCustomer", back_populates="store")

    theme: Mapped["StoreTheme"] = relationship(back_populates="store", uselist=False, cascade="all, delete-orphan")
    banners: Mapped[List["Banner"]] = relationship(back_populates="store", cascade="all, delete-orphan")

    orders: Mapped[List["Order"]] = relationship("Order", back_populates="store", cascade="all, delete-orphan")

    products = relationship(
        "Product",
        back_populates="store",
        order_by="asc(Product.priority)"  # Ou "Product.name" para ordem alfabética
    )

    categories = relationship(
        "Category",
        back_populates="store",
        order_by="asc(Category.priority)",
        cascade="all, delete-orphan"
    )

    cashier_sessions: Mapped[List["CashierSession"]] = relationship(
        "CashierSession", back_populates="store", cascade="all, delete-orphan"
    )

    # ✅ ATUALIZE ESTE RELACIONAMENTO
    store_operation_config: Mapped["StoreOperationConfig"] = relationship(
        back_populates="store", uselist=False, cascade="all, delete-orphan"
    )

    # Horários de funcionamento (relacionamento 1:N)
    hours: Mapped[List["StoreHours"]] = relationship(
        back_populates="store", cascade="all, delete-orphan"
    )

    scheduled_pauses: Mapped[list["ScheduledPause"]] = relationship(
        back_populates="store", cascade="all, delete-orphan"
    )

    # Cidades de entrega (relacionamento 1:N)
    cities: Mapped[List["StoreCity"]] = relationship(
        back_populates="store", cascade="all, delete-orphan"
    )

    store_ratings: Mapped[List["StoreRating"]] = relationship(back_populates="store")



    commands: Mapped[list["Command"]] = relationship(back_populates="store")

    subscriptions: Mapped[list["StoreSubscription"]] = relationship(
        "StoreSubscription",  # <-- Use a string aqui
        back_populates="store",
        lazy="select"
    )

    # active_sessions: Mapped[List["ActiveSession"]] = relationship(
    #     back_populates="store",
    #     cascade="all, delete-orphan"
    # )

    # dentro da classe Store
    accesses: Mapped[List["StoreAccess"]] = relationship(
        back_populates="store", cascade="all, delete-orphan"
    )

    variants: Mapped[List["Variant"]] = relationship(
        back_populates="store", cascade="all, delete-orphan"
    )

    payment_activations: Mapped[List["StorePaymentMethodActivation"]] = relationship(
        back_populates="store",
        cascade="all, delete-orphan"
    )

    # ✅ ADIÇÃO: Relacionamento com Contas a Pagar
    payables: Mapped[list["StorePayable"]] = relationship(
        back_populates="store",
        cascade="all, delete-orphan"
    )

    # ✅ ADIÇÃO: Relacionamento com Fornecedores
    suppliers: Mapped[list["Supplier"]] = relationship(
        back_populates="store",
        cascade="all, delete-orphan"
    )

    # ✅ ADIÇÃO: Relacionamento com Categorias de Contas a Pagar
    payable_categories: Mapped[list["PayableCategory"]] = relationship(
        back_populates="store",
        cascade="all, delete-orphan"
    )

    receivables: Mapped[list["StoreReceivable"]] = relationship(back_populates="store", cascade="all, delete-orphan")
    receivable_categories: Mapped[list["ReceivableCategory"]] = relationship(back_populates="store",
                                                                             cascade="all, delete-orphan")

    @hybrid_property
    def active_subscription(self) -> Optional["StoreSubscription"]:  # <- Use a string aqui também
        """
        Retorna a primeira assinatura ativa ou em cobrança encontrada para esta loja.
        """
        active_statuses = {'active', 'new_charge', 'trialing'}
        for sub in self.subscriptions:
            if sub.status in active_statuses:
                return sub
        return None

    @active_subscription.expression
    def active_subscription(cls):

        return select(StoreSubscription).where(
            StoreSubscription.store_id == cls.id,
            StoreSubscription.status.in_(['active', 'new_charge', 'trialing'])
        ).correlate_except(StoreSubscription).as_scalar()




class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(unique=True, index=True)
    name: Mapped[str] = mapped_column()
    phone: Mapped[Optional[str]] = mapped_column(nullable=True) # ALTERADO
    hashed_password: Mapped[str] = mapped_column()
    is_active: Mapped[bool] = mapped_column(default=True)
    is_email_verified: Mapped[bool] = mapped_column(default=False)
    verification_code: Mapped[Optional[str]] = mapped_column(nullable=True) # ALTERADO
    cpf: Mapped[Optional[str]] = mapped_column(unique=True, index=True, nullable=True) # ALTERADO
    birth_date: Mapped[Optional[date]] = mapped_column(nullable=True) # ALTERADO

    # --- CAMPOS PARA O SISTEMA DE INDICAÇÃO ---
    referral_code: Mapped[str] = mapped_column(unique=True, index=True)
    referred_by_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True) # ALTERADO

    # --- Relacionamentos SQLAlchemy ---
    referrer: Mapped[Optional["User"]] = relationship(remote_side=[id]) # ALTERADO
class Role(Base, TimestampMixin):
    __tablename__ = "roles"

    id: Mapped[int] = mapped_column(primary_key=True)
    machine_name: Mapped[str] = mapped_column(unique=True)

class StoreAccess(Base, TimestampMixin):
    __tablename__ = "store_accesses"

    store_id: Mapped[int] = mapped_column(ForeignKey("stores.id"), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), primary_key=True)
    role_id: Mapped[int] = mapped_column(ForeignKey("roles.id"))
    store: Mapped["Store"] = relationship("Store", back_populates="accesses")

    user: Mapped[User] = relationship()
    role: Mapped[Role] = relationship()

    __table_args__ = (Index("ix_store_user", "store_id", "user_id"),)



class Category(Base, TimestampMixin):
    __tablename__ = "categories"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column()
    priority: Mapped[int] = mapped_column()
    store_id: Mapped[int] = mapped_column(ForeignKey("stores.id"))
    file_key: Mapped[str] = mapped_column()
    is_active: Mapped[bool] = mapped_column(default=True)
    store: Mapped[Store] = relationship()


    product_links: Mapped[List["ProductCategoryLink"]] = relationship(back_populates="category",
                                                                      cascade="all, delete-orphan")

    # --- NOVOS CAMPOS PARA CASHBACK NA CATEGORIA ---
    cashback_type: Mapped[CashbackType] = mapped_column(Enum(CashbackType, name="cashback_type_enum"),
                                                        default=CashbackType.NONE)
    cashback_value: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal('0.00'))
    printer_destination: Mapped[str | None] = mapped_column(String(50), nullable=True)


class Product(Base, TimestampMixin):
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(80))
    description: Mapped[str] = mapped_column(String(1000))
    base_price: Mapped[int] = mapped_column()
    cost_price: Mapped[int] = mapped_column(default=0)
    available: Mapped[bool] = mapped_column()
    priority: Mapped[int] = mapped_column()
    promotion_price: Mapped[int] = mapped_column(default=0)

    featured: Mapped[bool] = mapped_column()
    activate_promotion: Mapped[bool] = mapped_column()

    store_id: Mapped[int] = mapped_column(ForeignKey("stores.id"))
    # ✅ ADICIONE ESTA LINHA PARA O RELACIONAMENTO REVERSO
    store: Mapped["Store"] = relationship(back_populates="products")

    # ✅ ADICIONE ESTA LINHA PARA O RELACIONAMENTO MUITOS-PARA-MUITOS:
    category_links: Mapped[List["ProductCategoryLink"]] = relationship(back_populates="product", cascade="all, delete-orphan")

    file_key: Mapped[str] = mapped_column()




    ean: Mapped[str] = mapped_column(default="")

    stock_quantity: Mapped[int] = mapped_column(default=0)
    control_stock: Mapped[bool] = mapped_column(default=False)
    min_stock: Mapped[int] = mapped_column(default=0)
    max_stock: Mapped[int] = mapped_column(default=0)
    unit: Mapped[str] = mapped_column(default="Unidade")
    tag: Mapped[str] = mapped_column(default="")

    product_ratings: Mapped[List["ProductRating"]] = relationship(back_populates="product")
    sold_count: Mapped[int] = mapped_column(nullable=False, default=0)


    cashback_type: Mapped[CashbackType] = mapped_column(Enum(CashbackType, name="cashback_type_enum"),
                                                        default=CashbackType.NONE)
    cashback_value: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal('0.00'))

    product_type: Mapped[ProductType] = mapped_column(default=ProductType.INDIVIDUAL)

    order_items: Mapped[list["OrderProduct"]] = relationship(back_populates="product")

    default_options: Mapped[list["ProductDefaultOption"]] = relationship(
        back_populates="product",
        cascade="all, delete-orphan"
    )

    variant_links: Mapped[List["ProductVariantLink"]] = relationship(
        back_populates="product",
        cascade="all, delete-orphan"
    )

    components: Mapped[list["KitComponent"]] = relationship(
        foreign_keys="[KitComponent.kit_product_id]",
        back_populates="kit",
        cascade="all, delete-orphan"
    )

    # ✅ SUGESTÃO: Adicione este campo para vincular ao catálogo
    master_product_id: Mapped[int | None] = mapped_column(ForeignKey("master_products.id"), nullable=True)
    master_product: Mapped[Optional["MasterProduct"]] = relationship()



    @hybrid_property
    def image_path(self):
        from src.core.aws import get_presigned_url
        return get_presigned_url(self.file_key) if self.file_key else None



class KitComponent(Base, TimestampMixin):
    __tablename__ = "kit_components"

    kit_product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), primary_key=True)
    component_product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), primary_key=True)

    quantity: Mapped[int] = mapped_column(default=1)  # Qtd do componente dentro do kit

    # Relacionamentos
    kit: Mapped["Product"] = relationship(foreign_keys=[kit_product_id], back_populates="components")
    component: Mapped["Product"] = relationship(foreign_keys=[component_product_id])


class Variant(Base, TimestampMixin):
    __tablename__ = "variants"

    id: Mapped[int] = mapped_column(primary_key=True)

    name: Mapped[str] = mapped_column(unique=True, doc="Nome único do template. Ex: 'Adicionais', 'Bebidas', 'Molhos'")

    type: Mapped[VariantType] = mapped_column(
        Enum(
            VariantType,
            native_enum=False,
            # ✅ A LINHA MÁGICA É ESTA:
            values_callable=lambda obj: [e.value for e in obj]
        ),
        doc="Define a finalidade do grupo..."
    )


    store_id: Mapped[int] = mapped_column(ForeignKey("stores.id"))

    # Relacionamentos
    options: Mapped[list["VariantOption"]] = relationship(back_populates="variant", cascade="all, delete-orphan")
    product_links: Mapped[list["ProductVariantLink"]] = relationship(back_populates="variant", cascade="all, delete-orphan")
    store: Mapped["Store"] = relationship(back_populates="variants")


class VariantOption(Base, TimestampMixin):
    __tablename__ = "variant_options"

    id: Mapped[int] = mapped_column(primary_key=True)

    variant_id: Mapped[int] = mapped_column(ForeignKey("variants.id", ondelete="CASCADE"))
    variant: Mapped["Variant"] = relationship(back_populates="options")

    linked_product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), nullable=True,
                                                   doc="Se não nulo, esta opção representa outro produto (Cross-Sell)")
    linked_product: Mapped["Product"] = relationship()

    name_override: Mapped[str] = mapped_column(nullable=True,
                                               doc="Nome customizado. Se nulo, usa o nome do produto linkado (se houver).")
    price_override: Mapped[int] = mapped_column(nullable=True,
                                                doc="Preço em centavos. Se nulo, usa o preço do produto linkado. Se for um ingrediente, este é o preço base.")

    # ✅ 1. CAMPO DE DESCRIÇÃO ADICIONADO
    description: Mapped[str] = mapped_column(Text, nullable=True,
                                             doc="Descrição detalhada da opção, exibida na UI para dar mais contexto ao cliente.")

    file_key: Mapped[str] = mapped_column(nullable=True,
                                          doc="Chave da imagem da opção (se não usar a do produto linkado).")
    pos_code: Mapped[str] = mapped_column(nullable=True, doc="Código de integração para o sistema PDV.")

    available: Mapped[bool] = mapped_column(default=True,
                                            doc="Disponibilidade manual. Pode ser usado para desativar um item temporariamente, independentemente do estoque.")
    store_id: Mapped[int] = mapped_column(ForeignKey("stores.id"))

    # ✅ 2. CAMPOS DE CONTROLE DE ESTOQUE ADICIONADOS
    track_inventory: Mapped[bool] = mapped_column(default=False,
                                                  doc="Se True, o estoque será controlado. Se False, o item é considerado de estoque infinito.")
    stock_quantity: Mapped[int] = mapped_column(default=0, server_default='0',
                                                doc="Quantidade disponível em estoque. Só é relevante se track_inventory for True.")

    # Adiciona uma restrição a nível de banco de dados para garantir que o estoque nunca seja negativo
    __table_args__ = (
        CheckConstraint('stock_quantity >= 0', name='check_stock_quantity_non_negative'),
    )

    def get_price(self) -> int:
        """
        Retorna o preço correto da opção em centavos, seguindo a regra de negócio:
        1. Usa o preço de sobreposição (override) se ele existir.
        2. Se não, usa o preço do produto linkado.
        3. Se nenhum dos dois, o preço é zero.
        """
        if self.price_override is not None:
            return self.price_override
        if self.linked_product:
            return self.linked_product.promotion_price if self.linked_product.activate_promotion else self.linked_product.base_price
        return 0

    @hybrid_property
    def resolvedName(self):
        if self.name_override:
            return self.name_override
        if self.linked_product:
            return self.linked_product.name
        return "Opção sem nome"

    # ✅ 3. PROPRIEDADE INTELIGENTE PARA DISPONIBILIDADE REAL
    @hybrid_property
    def is_actually_available(self) -> bool:
        """
        Verifica a disponibilidade real do item, considerando o controle de estoque.
        Esta é a propriedade que o front-end deve usar para habilitar/desabilitar a opção.
        """
        # 1. Se foi desabilitado manualmente, está indisponível. Ponto final.
        if not self.available:
            return False

        # 2. Se o estoque não é rastreado, está sempre disponível.
        if not self.track_inventory:
            return True

        # 3. Se o estoque é rastreado, só está disponível se a quantidade for maior que zero.
        return self.stock_quantity > 0


class ProductVariantLink(Base, TimestampMixin):
    __tablename__ = "product_variant_links"
    __table_args__ = (UniqueConstraint('product_id', 'variant_id', name='uix_product_variant_link'),)

    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), primary_key=True)
    variant_id: Mapped[int] = mapped_column(ForeignKey("variants.id"), primary_key=True)

    # --- REGRAS DE COMPORTAMENTO E INTERFACE ---

    ui_display_mode: Mapped[UIDisplayMode] = mapped_column(
        Enum(UIDisplayMode, native_enum=False),  # <--- A MUDANÇA É AQUI
        doc="Define a finalidade do grupo..."
    )


    min_selected_options: Mapped[int] = mapped_column(default=0,
                                                      doc="Qtd. mínima de opções. 0=Opcional, >0=Obrigatório.")
    max_selected_options: Mapped[int] = mapped_column(default=1,
                                                      doc="Qtd. máxima de OPÇÕES DISTINTAS a serem escolhidas.")
    max_total_quantity: Mapped[int] = mapped_column(nullable=True,
                                                    doc="Soma máxima das quantidades (para modo QUANTITY).")

    display_order: Mapped[int] = mapped_column(default=0, doc="Ordem de exibição do grupo no produto.")
    available: Mapped[bool] = mapped_column(default=True, doc="Se este grupo está ativo neste produto.")

    # Relacionamentos
    product: Mapped["Product"] = relationship()  # Assumindo que Product tem o back_populates
    variant: Mapped["Variant"] = relationship(back_populates="product_links")

class ProductDefaultOption(Base, TimestampMixin):
    __tablename__ = "product_default_options"
    __table_args__ = (UniqueConstraint('product_id', 'variant_option_id', name='uix_product_default_option'),)

    product_id: Mapped[int] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"), primary_key=True)
    variant_option_id: Mapped[int] = mapped_column(ForeignKey("variant_options.id", ondelete="CASCADE"), primary_key=True)

    # Relacionamentos para facilitar as consultas
    product: Mapped["Product"] = relationship(back_populates="default_options")
    option: Mapped["VariantOption"] = relationship()



class Coupon(Base, TimestampMixin):
    __tablename__ = "coupons"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    description: Mapped[str] = mapped_column(String(255))

    # A AÇÃO do cupom
    discount_type: Mapped[str] = mapped_column(String(20))  # 'PERCENTAGE', 'FIXED_AMOUNT', 'FREE_DELIVERY'
    discount_value: Mapped[float] = mapped_column() # Em % ou centavos

    max_discount_amount: Mapped[int] = mapped_column(nullable=True) # Teto do desconto em centavos

    # Validade e Status
    start_date: Mapped[datetime] = mapped_column()
    end_date: Mapped[datetime] = mapped_column()
    is_active: Mapped[bool] = mapped_column(default=True)

    # Relacionamentos
    store_id: Mapped[int] = mapped_column(ForeignKey("stores.id"))

    # --- RELACIONAMENTOS CORRETOS ---
    store: Mapped["Store"] = relationship(back_populates="coupons")

    # ✅ Um cupom pode ter várias regras
    rules = relationship("CouponRule", back_populates="coupon", cascade="all, delete-orphan")

    # ✅ Um cupom pode ser usado várias vezes (vários registros de uso)
    usages = relationship("CouponUsage", back_populates="coupon", cascade="all, delete-orphan")


class CouponRule(Base):
    __tablename__ = "coupon_rules"

    id: Mapped[int] = mapped_column(primary_key=True)
    coupon_id: Mapped[int] = mapped_column(ForeignKey("coupons.id"))

    # O TIPO de regra
    rule_type: Mapped[str] = mapped_column(String(50))
    # Ex: 'MIN_SUBTOTAL', 'FIRST_ORDER', 'TARGET_PRODUCT', 'TARGET_CATEGORY', 'MAX_USES_TOTAL', 'MAX_USES_PER_CUSTOMER'

    # O VALOR da regra (usar JSONB é super flexível)
    # Ex: {'value': 5000} para subtotal, {'product_id': 123}, {'limit': 1} para uso por cliente
    value: Mapped[dict] = mapped_column(JSONB)

    coupon = relationship("Coupon", back_populates="rules")


class CouponUsage(Base):
    __tablename__ = "coupon_usages"

    id: Mapped[int] = mapped_column(primary_key=True)
    coupon_id: Mapped[int] = mapped_column(ForeignKey("coupons.id"))
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"))
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"), unique=True) # Garante um uso por pedido
    used_at: Mapped[datetime] = mapped_column(default=func.now())

    # --- RELACIONAMENTOS CORRETOS ---

    # ✅ Um registro de uso pertence a um cupom
    coupon = relationship("Coupon", back_populates="usages")

    # ✅ Um registro de uso pertence a um pedido (um-para-um)
    order: Mapped["Order"] = relationship(back_populates="coupon_usage")

    customer = relationship("Customer")



    
class TotemAuthorization(Base, TimestampMixin):
    __tablename__ = "totem_authorizations"

    id: Mapped[int] = mapped_column(primary_key=True)

    totem_token: Mapped[str] = mapped_column(unique=True)
    totem_name: Mapped[str] = mapped_column()
    public_key: Mapped[str] = mapped_column(unique=True)

    store_id: Mapped[int | None] = mapped_column(ForeignKey("stores.id"))
    granted: Mapped[bool] = mapped_column(default=False)
    granted_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))

    store: Mapped[Store] = relationship()

    sid: Mapped[str | None] = mapped_column(unique=True)

    store_url: Mapped[str] = mapped_column(unique=True, nullable=False)


class StoreSession(Base, TimestampMixin):
    __tablename__ = "store_sessions"

    id: Mapped[int] = mapped_column(primary_key=True)

    # ✨ CORREÇÃO: Tornamos o user_id opcional (pode ser nulo) no banco
    user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)


    store_id: Mapped[Optional[int]] = mapped_column(ForeignKey("stores.id"), nullable=True)

    client_type: Mapped[str] = mapped_column()  # 'admin' ou 'totem'
    sid: Mapped[str] = mapped_column(unique=True)

    # Opcional: Adicionar um relationship para facilitar o acesso ao usuário
    # user: Mapped["User"] = relationship()


class CustomerSession(Base, TimestampMixin):
    __tablename__ = "customer_sessions"

    # O SID do Socket.IO é a chave primária. É único para cada conexão.
    sid: Mapped[str] = mapped_column(String(255), primary_key=True)

    # Opcional no início (sessão anônima), preenchido após o login.
    customer_id: Mapped[int | None] = mapped_column(ForeignKey("customers.id"), nullable=True, index=True)

    store_id: Mapped[int] = mapped_column(ForeignKey("stores.id"))

    # Relacionamentos para facilitar o acesso
    customer: Mapped[Optional["Customer"]] = relationship()
    store: Mapped["Store"] = relationship()


class AdminConsolidatedStoreSelection(Base, TimestampMixin):  # Adicionei TimestampMixin aqui também para padronizar
    __tablename__ = 'admin_consolidated_store_selection'

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    # ✅ CORREÇÃO: A ForeignKey agora aponta para 'users.id'
    admin_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    store_id: Mapped[int] = mapped_column(ForeignKey("stores.id"), nullable=False)

    __table_args__ = (UniqueConstraint('admin_id', 'store_id', name='uq_admin_store_selection'),)

    # ✅ CORREÇÃO: O relacionamento agora é com o modelo de usuário (ex: User)
    admin_user: Mapped["User"] = relationship() # O nome do modelo pode variar (User, AdminUser, etc)
    store: Mapped["Store"] = relationship()




class StoreTheme(Base, TimestampMixin):
    __tablename__ = "store_themes"

    id: Mapped[int] = mapped_column(primary_key=True)
    store_id: Mapped[int] = mapped_column(ForeignKey("stores.id"), unique=True)

    # --- As ÚNICAS coisas que o lojista escolhe e salvamos no banco ---

    primary_color: Mapped[str] = mapped_column(
        doc="Cor primária da marca em formato HEX (ex: 'FF6B2C')"
    )

    mode: Mapped[ThemeMode] = mapped_column(
        Enum(ThemeMode, native_enum=False, values_callable=lambda obj: [e.value for e in obj]),
        default=ThemeMode.LIGHT,
        doc="O modo do tema: claro (light) ou escuro (dark)"
    )

    font_family: Mapped[str] = mapped_column(
        default='roboto',
        doc="A família de fontes escolhida (ex: 'roboto', 'montserrat')"
    )

    # ✅ NOVO CAMPO ADICIONADO
    theme_name: Mapped[str] = mapped_column(
        default='custom',
        doc="Nome do tema pré-definido (ex: 'default', 'speed') ou 'custom' se for personalizado."
    )

    # Relacionamento
    store: Mapped["Store"] = relationship(back_populates="theme")


class StorePixConfig(Base, TimestampMixin):
    __tablename__ = "store_pix_configs"

    id: Mapped[int] = mapped_column(primary_key=True)

    store_id: Mapped[int] = mapped_column(ForeignKey("stores.id"), unique=True)

    client_id: Mapped[str] = mapped_column()
    client_secret: Mapped[str] = mapped_column()
    pix_key: Mapped[str] = mapped_column()
    certificate: Mapped[bytes] = mapped_column(LargeBinary)

    hmac_key: Mapped[str] = mapped_column(unique=True)


class Charge(Base, TimestampMixin):
    __tablename__ = "charges"

    id: Mapped[int] = mapped_column(primary_key=True)

    store_id: Mapped[int] = mapped_column(ForeignKey("stores.id"), nullable=False)
    tx_id: Mapped[str] = mapped_column()
    status: Mapped[str] = mapped_column()
    amount: Mapped[int] = mapped_column()
    copy_key: Mapped[str] = mapped_column()
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    e2e_id: Mapped[str | None] = mapped_column()


class PixDevolution(Base, TimestampMixin):
    __tablename__ = "pix_devolutions"

    id: Mapped[int] = mapped_column(primary_key=True)
    store_id: Mapped[int] = mapped_column(ForeignKey("stores.id"), nullable=False)
    rtr_id: Mapped[str] = mapped_column()
    status: Mapped[str] = mapped_column()
    amount: Mapped[int] = mapped_column()
    e2e_id: Mapped[str] = mapped_column()
    reason: Mapped[str | None] = mapped_column()


class StoreChatbotConfig(Base, TimestampMixin):
    __tablename__ = "store_chatbot_configs"

    id: Mapped[int] = mapped_column(primary_key=True)

    store_id: Mapped[int] = mapped_column(ForeignKey("stores.id"))

    whatsapp_number: Mapped[str] = mapped_column(nullable=True)
    whatsapp_name: Mapped[str] = mapped_column(nullable=True)
    connection_status: Mapped[str] = mapped_column()  # exemplo: 'connected', 'disconnected', 'awaiting_qr'
    last_qr_code: Mapped[str] = mapped_column(nullable=True)  # pode salvar o base64/texto do QR
    last_connected_at: Mapped[datetime] = mapped_column(nullable=True)
    session_path: Mapped[str] = mapped_column(nullable=True)  # caminho local ou info da sessão


class PaymentMethodGroup(Base):
    __tablename__ = "payment_method_groups"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(50), unique=True)
    title: Mapped[str] = mapped_column(String(255), nullable=True)
    description: Mapped[str] = mapped_column(String(255), nullable=True)

    priority: Mapped[int] = mapped_column(default=0)
    categories = relationship("PaymentMethodCategory", back_populates="group")


class PaymentMethodCategory(Base):
    __tablename__ = "payment_method_categories"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(50))
    priority: Mapped[int] = mapped_column(default=0)
    group_id: Mapped[int] = mapped_column(ForeignKey("payment_method_groups.id"), nullable=False)
    group = relationship("PaymentMethodGroup", back_populates="categories")
    methods = relationship("PlatformPaymentMethod", back_populates="category")



class PlatformPaymentMethod(Base, TimestampMixin):
    __tablename__ = "platform_payment_methods"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(50), unique=True)
    description: Mapped[str] = mapped_column(String(255), nullable=True)
    method_type: Mapped[PaymentMethodType] = mapped_column(Enum(PaymentMethodType), nullable=False)
    icon_key: Mapped[str] = mapped_column(String(100), nullable=True)
    is_globally_enabled: Mapped[bool] = mapped_column(default=True)
    requires_details: Mapped[bool] = mapped_column(default=False)

    # ✅ CORREÇÃO: Adicionada a chave estrangeira que faltava
    category_id: Mapped[int] = mapped_column(ForeignKey("payment_method_categories.id"), nullable=False)

    # Relacionamentos
    category = relationship("PaymentMethodCategory", back_populates="methods")
    activations = relationship("StorePaymentMethodActivation", back_populates="platform_method")


class StorePaymentMethodActivation(Base, TimestampMixin):
    __tablename__ = "store_payment_method_activations"

    id: Mapped[int] = mapped_column(primary_key=True)
    store_id: Mapped[int] = mapped_column(ForeignKey("stores.id"), nullable=False)
    platform_payment_method_id: Mapped[int] = mapped_column(ForeignKey("platform_payment_methods.id"), nullable=False)
    is_active: Mapped[bool] = mapped_column(default=False)
    fee_percentage: Mapped[float] = mapped_column(default=0)
    details: Mapped[dict] = mapped_column(JSONB, nullable=True)
    is_for_delivery: Mapped[bool] = mapped_column(default=True)
    is_for_pickup: Mapped[bool] = mapped_column(default=True)
    is_for_in_store: Mapped[bool] = mapped_column(default=True)

    # Relacionamentos
    store = relationship("Store", back_populates="payment_activations")
    platform_method = relationship("PlatformPaymentMethod", back_populates="activations")
    orders = relationship("Order", back_populates="payment_method")


# --- ATUALIZAÇÕES NECESSÁRIAS EM MODELOS EXISTENTES ---












# ✅ NOVO MODELO UNIFICADO
class StoreOperationConfig(Base, TimestampMixin):
    __tablename__ = "store_operation_config" # Novo nome de tabela

    id: Mapped[int] = mapped_column(primary_key=True)
    store_id: Mapped[int] = mapped_column(ForeignKey("stores.id"), unique=True, index=True)

    # --- Campos que eram de 'Settings' ---
    is_store_open: Mapped[bool] = mapped_column(default=True)
    auto_accept_orders: Mapped[bool] = mapped_column(default=False)
    auto_print_orders: Mapped[bool] = mapped_column(default=False)
    main_printer_destination: Mapped[str] = mapped_column(nullable=True)
    kitchen_printer_destination: Mapped[str] = mapped_column(nullable=True)
    bar_printer_destination: Mapped[str] = mapped_column(nullable=True)

    # --- Campos que eram de 'Delivery' (agora unificados) ---
    delivery_enabled: Mapped[bool] = mapped_column(default=False)
    delivery_estimated_min: Mapped[int] = mapped_column(nullable=True)
    delivery_estimated_max: Mapped[int] = mapped_column(nullable=True)
    delivery_fee: Mapped[float] = mapped_column(nullable=True)
    delivery_min_order: Mapped[float] = mapped_column(nullable=True)
    delivery_scope: Mapped[str] = mapped_column(nullable=True, default='neighborhood')

    pickup_enabled: Mapped[bool] = mapped_column(default=False)
    pickup_estimated_min: Mapped[int] = mapped_column(nullable=True)
    pickup_estimated_max: Mapped[int] = mapped_column(nullable=True)
    pickup_instructions: Mapped[str] = mapped_column(nullable=True)

    table_enabled: Mapped[bool] = mapped_column(default=False)
    table_estimated_min: Mapped[int] = mapped_column(nullable=True)
    table_estimated_max: Mapped[int] = mapped_column(nullable=True)
    table_instructions: Mapped[str] = mapped_column(nullable=True)

    # ✅ Relacionamento atualizado no modelo 'Store'
    store: Mapped["Store"] = relationship(back_populates="store_operation_config")
    free_delivery_threshold: Mapped[float] = mapped_column(nullable=True) # Valor a partir do qual o frete é grátis

class StoreHours(Base, TimestampMixin):
    __tablename__ = "store_hours"

    id: Mapped[int] = mapped_column(primary_key=True)
    store_id: Mapped[int] = mapped_column(ForeignKey("stores.id", ondelete="CASCADE"))

    day_of_week: Mapped[int] = mapped_column()  # 0 - domingo, 6 - sábado
    open_time: Mapped[str] = mapped_column()  # exemplo: '08:00'
    close_time: Mapped[str] = mapped_column()  # exemplo: '18:00'
    shift_number: Mapped[int] = mapped_column()
    is_active: Mapped[bool] = mapped_column(default=True)

    store: Mapped["Store"] = relationship(back_populates="hours")


class StoreCity(Base, TimestampMixin):
    __tablename__ = "store_cities"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column()
    delivery_fee: Mapped[int] = mapped_column(default=0)
    store_id: Mapped[int] = mapped_column(ForeignKey("stores.id", ondelete="CASCADE"))
    neighborhoods: Mapped[List["StoreNeighborhood"]] = relationship("StoreNeighborhood", back_populates="city",
                                                                    cascade="all, delete")
    is_active: Mapped[bool] = mapped_column(default=True)
    store: Mapped["Store"] = relationship(back_populates="cities")


class StoreNeighborhood(Base, TimestampMixin):
    __tablename__ = "store_neighborhoods"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column()

    city_id: Mapped[int] = mapped_column(ForeignKey("store_cities.id", ondelete="CASCADE"))

    delivery_fee: Mapped[int] = mapped_column(default=0)
    free_delivery: Mapped[bool] = mapped_column(default=False)
    is_active: Mapped[bool] = mapped_column(default=True)

    city: Mapped["StoreCity"] = relationship("StoreCity", back_populates="neighborhoods")




# Crie estes novos modelos também
class PayableCategory(Base):
    __tablename__ = "payable_categories"
    id: Mapped[int] = mapped_column(primary_key=True)
    store_id: Mapped[int] = mapped_column(ForeignKey("stores.id", ondelete="CASCADE"))
    # ✅ ADIÇÃO: O relacionamento de volta para a loja
    store: Mapped["Store"] = relationship(back_populates="payable_categories")

    name: Mapped[str] = mapped_column()
    # Relacionamento inverso
    payables: Mapped[list["StorePayable"]] = relationship(back_populates="category")





class Supplier(Base):
    __tablename__ = "suppliers"

    id: Mapped[int] = mapped_column(primary_key=True)
    store_id: Mapped[int] = mapped_column(ForeignKey("stores.id", ondelete="CASCADE"))
    store: Mapped["Store"] = relationship(back_populates="suppliers")
    name: Mapped[str] = mapped_column(String(255))
    trade_name: Mapped[str | None] = mapped_column(String(255))  # Nome Fantasia
    document: Mapped[str | None] = mapped_column(String(20), unique=True, index=True)  # CPF ou CNPJ

    # Contato
    email: Mapped[str | None] = mapped_column(String(255))
    phone: Mapped[str | None] = mapped_column(String(20))

    # Endereço e Informações Bancárias (usando JSON para flexibilidade)
    address: Mapped[dict | None] = mapped_column(JSON)
    bank_info: Mapped[dict | None] = mapped_column(JSON)

    notes: Mapped[str | None] = mapped_column(Text)

    # Relacionamento inverso
    payables: Mapped[list["StorePayable"]] = relationship(back_populates="supplier")



class PayableRecurrence(Base):
    __tablename__ = "payable_recurrences"
    id: Mapped[int] = mapped_column(primary_key=True)

    # Vínculo com a conta a pagar original que gerou a recorrência
    original_payable_id: Mapped[int] = mapped_column(ForeignKey("store_payables.id"))

    frequency: Mapped[str] = mapped_column(String(50))  # Ex: 'daily', 'weekly', 'monthly', 'yearly'
    interval: Mapped[int] = mapped_column(default=1)  # Ex: a cada 2 meses (frequency='monthly', interval=2)
    start_date: Mapped[date] = mapped_column()
    end_date: Mapped[date | None] = mapped_column()  # A recorrência pode ser infinita


    # ✅ CORREÇÃO: Especifica qual chave estrangeira usar para este relacionamento
    original_payable: Mapped["StorePayable"] = relationship(
        back_populates="recurrence",
        foreign_keys=[original_payable_id]
    )

    # ✅ ADIÇÃO (Opcional, mas bom): Relacionamento para ver todas as contas geradas
    generated_payables: Mapped[list["StorePayable"]] = relationship(
        back_populates="parent_recurrence",
        foreign_keys="[StorePayable.parent_recurrence_id]"
    )
class StorePayable(Base, TimestampMixin):
    __tablename__ = "store_payables"

    id: Mapped[int] = mapped_column(primary_key=True)
    store_id: Mapped[int] = mapped_column(ForeignKey("stores.id", ondelete="CASCADE"))

    category_id: Mapped[int | None] = mapped_column(ForeignKey("payable_categories.id"))
    supplier_id: Mapped[int | None] = mapped_column(ForeignKey("suppliers.id"))

    title: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text)

    amount: Mapped[int] = mapped_column(Integer)  # Valor em centavos
    discount: Mapped[int] = mapped_column(Integer, default=0)
    addition: Mapped[int] = mapped_column(Integer, default=0)

    due_date: Mapped[date] = mapped_column(index=True)
    payment_date: Mapped[date | None] = mapped_column()
    barcode: Mapped[str | None] = mapped_column(String(255))
    status: Mapped[PayableStatus] = mapped_column(default=PayableStatus.pending, index=True)

    attachment_key: Mapped[str | None] = mapped_column()  # Chave para o arquivo (ex: em um S3)
    notes: Mapped[str | None] = mapped_column(Text)

    # Relacionamentos
    store: Mapped["Store"] = relationship(back_populates="payables")
    category: Mapped["PayableCategory"] = relationship(back_populates="payables", lazy="joined")
    supplier: Mapped["Supplier"] = relationship(back_populates="payables", lazy="joined")

    parent_recurrence_id: Mapped[int | None] = mapped_column(
        ForeignKey(
            "payable_recurrences.id",
            use_alter=True,
            name="fk_payable_parent_recurrence"
        )
    )


    recurrence: Mapped["PayableRecurrence"] = relationship(
        back_populates="original_payable",
        foreign_keys="[PayableRecurrence.original_payable_id]",
        cascade="all, delete-orphan"
    )


    parent_recurrence: Mapped["PayableRecurrence"] = relationship(
        back_populates="generated_payables",
        foreign_keys=[parent_recurrence_id]
    )


class ReceivableCategory(Base):
    """
    Categorias para as contas a receber.
    Exemplos: 'Venda a Prazo', 'Serviço Prestado', 'Mensalidade'.
    """
    __tablename__ = "receivable_categories"
    id: Mapped[int] = mapped_column(primary_key=True)
    store_id: Mapped[int] = mapped_column(ForeignKey("stores.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(100))

    # Relacionamento de volta para a loja
    store: Mapped["Store"] = relationship(back_populates="receivable_categories")

    # Lista de recebíveis nesta categoria
    receivables: Mapped[list["StoreReceivable"]] = relationship(back_populates="category")


class StoreReceivable(Base):  # Adicione , TimestampMixin se usar
    """
    Representa uma conta a receber de uma loja.
    """
    __tablename__ = "store_receivables"
    id: Mapped[int] = mapped_column(primary_key=True)
    store_id: Mapped[int] = mapped_column(ForeignKey("stores.id", ondelete="CASCADE"))
    category_id: Mapped[int | None] = mapped_column(ForeignKey("receivable_categories.id"))

    # Chave da mudança: link para um cliente (customer) em vez de um fornecedor
    # Supondo que você tenha uma tabela 'customers'
    customer_id: Mapped[int | None] = mapped_column(ForeignKey("customers.id"))

    title: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text)
    amount: Mapped[int] = mapped_column(Integer)  # Valor em centavos

    due_date: Mapped[date] = mapped_column(index=True)  # Data de Vencimento
    received_date: Mapped[date | None] = mapped_column()  # Data de Recebimento

    # Status possíveis: 'pending', 'received', 'overdue'
    status: Mapped[str] = mapped_column(String(50), default='pending', index=True)

    # --- Relacionamentos ---
    store: Mapped["Store"] = relationship(back_populates="receivables")
    category: Mapped["ReceivableCategory"] = relationship(back_populates="receivables", lazy="joined")

    # ✅ 2. SINTAXE CORRIGIDA E ADIÇÃO DO back_populates
    # Supondo que seu modelo Customer tenha um relacionamento 'receivables'
    customer: Mapped[Optional["Customer"]] = relationship(
        back_populates="receivables",
        lazy="joined"
    )

# --- ATUALIZAÇÕES NECESSÁRIAS EM OUTROS MODELOS ---


class CashierSession(Base, TimestampMixin):
    __tablename__ = "cashier_sessions"

    id: Mapped[int] = mapped_column(primary_key=True)
    store_id: Mapped[int] = mapped_column(ForeignKey("stores.id"))
    user_opened_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    user_closed_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    opened_at: Mapped[datetime] = mapped_column(default=datetime.now(timezone.utc), )
    closed_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    opening_amount: Mapped[float] = mapped_column()
    cash_added: Mapped[float] = mapped_column(default=0.0)
    cash_removed: Mapped[float] = mapped_column(default=0.0)

    cash_difference: Mapped[float] = mapped_column(default=0.0)
    expected_amount: Mapped[float] = mapped_column(default=0.0)
    informed_amount: Mapped[float] = mapped_column(default=0.0)

    status: Mapped[str] = mapped_column(default="open")

    store: Mapped["Store"] = relationship("Store", back_populates="cashier_sessions")

    transactions: Mapped[List["CashierTransaction"]] = relationship(
        "CashierTransaction", back_populates="cashier_session", cascade="all, delete-orphan"
    )

    def add_cash(self, amount: float):
        if amount <= 0:
            raise ValueError("O valor a adicionar deve ser positivo.")
        self.cash_added += amount

    def remove_cash(self, amount: float):
        if amount <= 0:
            raise ValueError("O valor a remover deve ser positivo.")
        self.cash_removed += amount


class CashierTransaction(Base, TimestampMixin):
    __tablename__ = "cashier_transactions"

    id: Mapped[int] = mapped_column(primary_key=True)
    cashier_session_id: Mapped[int] = mapped_column(ForeignKey("cashier_sessions.id"))
    type: Mapped[str] = mapped_column()  # inflow ou outflow
    amount: Mapped[float] = mapped_column()
   # payment_method_id: Mapped[int] = mapped_column(ForeignKey("store_payment_methods.id"))
    description: Mapped[Optional[str]] = mapped_column()
    order_id: Mapped[Optional[int]] = mapped_column(ForeignKey("orders.id"), nullable=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))  # Novo campo recomendado
    order: Mapped[Optional["Order"]] = relationship("Order", back_populates="transactions")

    cashier_session: Mapped["CashierSession"] = relationship("CashierSession", back_populates="transactions")
    user: Mapped["User"] = relationship("User")
   # payment_method: Mapped["StorePaymentMethods"] = relationship("StorePaymentMethods")


class Customer(Base):
    __tablename__ = "customers"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    email: Mapped[str] = mapped_column(String(150), unique=True, nullable=False)
    phone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    photo: Mapped[str | None] = mapped_column(nullable=True)

    customer_addresses: Mapped[list["Address"]] = relationship("Address", back_populates="customer",
                                                               cascade="all, delete-orphan")

    store_ratings: Mapped[List["StoreRating"]] = relationship(back_populates="customer")
    product_ratings: Mapped[List["ProductRating"]] = relationship(back_populates="customer")

    # no Customer
    store_customers = relationship("StoreCustomer", back_populates="customer")
    cashback_balance: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal('0.00'))

    orders: Mapped[list["Order"]] = relationship(back_populates="customer")

    receivables: Mapped[list["StoreReceivable"]] = relationship()

class StoreCustomer(Base, TimestampMixin):
    __tablename__ = "store_customers"

    store_id: Mapped[int] = mapped_column(ForeignKey("stores.id"), primary_key=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"), primary_key=True)

    total_orders: Mapped[int] = mapped_column(default=1)
    total_spent: Mapped[int] = mapped_column(default=0)
    last_order_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    store = relationship("Store", back_populates="store_customers")
    customer = relationship("Customer", back_populates="store_customers")



class Address(Base):
    __tablename__ = "customer_addresses"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id", ondelete="CASCADE"))

    # --- Metadados do Endereço (Para organização do cliente) ---
    label: Mapped[str] = mapped_column(String(50))  # Ex: "Casa", "Trabalho"
    is_favorite: Mapped[bool] = mapped_column(default=False)

    # --- Campos de Texto (Para exibição e geolocalização) ---

    street: Mapped[str] = mapped_column(String(200))
    number: Mapped[str] = mapped_column(String(50))
    complement: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    neighborhood: Mapped[str] = mapped_column(String(100))
    city: Mapped[str] = mapped_column(String(100))

    reference: Mapped[Optional[str]] = mapped_column(String(150), nullable=True)


    city_id: Mapped[Optional[int]] = mapped_column(ForeignKey("store_cities.id"), nullable=True)
    neighborhood_id: Mapped[Optional[int]] = mapped_column(ForeignKey("store_neighborhoods.id"), nullable=True)

    # --- Relacionamento ---
    customer: Mapped["Customer"] = relationship("Customer", back_populates="customer_addresses")

class Banner(Base, TimestampMixin):
    __tablename__ = "banners"

    id: Mapped[int] = mapped_column(primary_key=True)
    store_id: Mapped[int] = mapped_column(ForeignKey("stores.id"), nullable=False)

    link_url: Mapped[str] = mapped_column(nullable=True)
    file_key: Mapped[str] = mapped_column(nullable=False)

    product_id: Mapped[int | None] = mapped_column(ForeignKey("products.id"), nullable=True)
    category_id: Mapped[int | None] = mapped_column(ForeignKey("categories.id"), nullable=True)

    start_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    end_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)

    is_active: Mapped[bool] = mapped_column(default=True)
    position: Mapped[int | None] = mapped_column(nullable=True)

    # Relacionamentos
    product: Mapped[Product | None] = relationship()
    category: Mapped[Category | None] = relationship()

    store: Mapped["Store"] = relationship(back_populates="banners")




class Order(Base, TimestampMixin):
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(primary_key=True)
    sequential_id: Mapped[int] = mapped_column()
    public_id: Mapped[str] = mapped_column(unique=True, index=True)


    store_id: Mapped[int] = mapped_column(ForeignKey("stores.id"), index=True)


    customer_id: Mapped[int | None] = mapped_column(ForeignKey("customers.id"), nullable=True, index=True)

    customer: Mapped[Optional["Customer"]] = relationship(back_populates="orders")

    # Campos desnormalizados
    customer_name: Mapped[str | None] = mapped_column(nullable=True)
    customer_phone: Mapped[str | None] = mapped_column(nullable=True)
    payment_method_name: Mapped[str | None] = mapped_column(nullable=True)

    # Endereço
    street: Mapped[str] = mapped_column()
    number: Mapped[str | None] = mapped_column(nullable=True)
    complement: Mapped[str | None] = mapped_column(nullable=True)
    neighborhood: Mapped[str] = mapped_column()
    city: Mapped[str] = mapped_column()

    # Informações do pedido
    attendant_name: Mapped[str | None] = mapped_column(nullable=True)
    order_type: Mapped[str] = mapped_column()
    delivery_type: Mapped[str] = mapped_column()
    observation: Mapped[str | None] = mapped_column(nullable=True)

    # Valores monetários
    total_price: Mapped[int] = mapped_column()
    subtotal_price: Mapped[int] = mapped_column(
        server_default='0',  # Valor padrão no banco
        default=0  # Valor padrão no Python
    )




    discounted_total_price: Mapped[int] = mapped_column()
    delivery_fee: Mapped[int] = mapped_column(default=0)
    change_amount: Mapped[float | None] = mapped_column(nullable=True)

    # Descontos
    discount_amount: Mapped[int] = mapped_column(default=0)
    discount_percentage: Mapped[float | None] = mapped_column(nullable=True)
    discount_type: Mapped[str | None] = mapped_column(nullable=True)
    discount_reason: Mapped[str | None] = mapped_column(nullable=True)

    # Status e pagamento
    payment_status: Mapped[str] = mapped_column()


    order_status: Mapped[OrderStatus] = mapped_column(Enum(OrderStatus, native_enum=False), default=OrderStatus.PENDING,
                                                      index=True)

    needs_change: Mapped[bool] = mapped_column(default=False)

    # Cashback - VERSÃO CORRIGIDA
    cashback_amount_generated: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False, default=Decimal('0.00'))
    cashback_used: Mapped[int] = mapped_column(default=0)


    products: Mapped[list["OrderProduct"]] = relationship(backref="order")
    store = relationship("Store", back_populates="orders")
    transactions: Mapped[list["CashierTransaction"]] = relationship(back_populates="order")

    # Agendamento e consumo
    is_scheduled: Mapped[bool] = mapped_column(default=False)
    scheduled_for: Mapped[datetime | None] = mapped_column(nullable=True)
    consumption_type: Mapped[str] = mapped_column(default="dine_in")

    # Mesas/comandas
    table_id: Mapped[int | None] = mapped_column(ForeignKey("tables.id", ondelete="SET NULL"), nullable=True)
    table: Mapped[Optional["Table"]] = relationship(back_populates="orders")
    command_id: Mapped[int | None] = mapped_column(ForeignKey("commands.id", ondelete="SET NULL"), nullable=True)
    command: Mapped[Optional["Command"]] = relationship(back_populates="orders")


    # NOVO RELACIONAMENTO
    print_logs: Mapped[list["OrderPrintLog"]] = relationship(back_populates="order")


    payment_method_id: Mapped[int | None] = mapped_column(
        ForeignKey("store_payment_method_activations.id", ondelete="SET NULL"),  # Aponta para a nova tabela
        nullable=True
    )
    payment_method = relationship(
        "StorePaymentMethodActivation",  # Aponta para a nova classe de modelo
        back_populates="orders"
    )

    partial_payments: Mapped[list["OrderPartialPayment"]] = relationship(
        back_populates="order",
        cascade="all, delete-orphan"  # Garante que ao apagar um pedido, os pagamentos parciais também sejam apagados.
    )

    # ✅ Um pedido pode ter um (e apenas um) registro de uso de cupom
    coupon_usage: Mapped["CouponUsage"] = relationship(back_populates="order")

    # Você ainda pode manter a propriedade para uma checagem rápida
    @hybrid_property
    def is_printed(self) -> bool:
        return len(self.print_logs) > 0


    __table_args__ = (
        # Este índice é um "super-índice" para a combinação mais comum de filtros
        Index('ix_orders_store_id_created_at', 'store_id', 'created_at'),
    )

class OrderProduct(Base, TimestampMixin):
    __tablename__ = "order_products"

    id: Mapped[int] = mapped_column(primary_key=True)

    order_id: Mapped[int] = mapped_column(
        ForeignKey("orders.id", ondelete="CASCADE")
    )
    store_id: Mapped[int] = mapped_column(
        ForeignKey("stores.id", ondelete="CASCADE")
    )
    product_id: Mapped[int] = mapped_column(
        ForeignKey("products.id", ondelete="SET NULL"),
        nullable=True
    )
    product: Mapped[Optional["Product"]] = relationship(back_populates="order_items")

    name: Mapped[str] = mapped_column()
    price: Mapped[int] = mapped_column()
    quantity: Mapped[int] = mapped_column()
    note: Mapped[str] = mapped_column(default='', nullable=False)
    image_url: Mapped[str | None] = mapped_column(nullable=True)  # URL da imagem do produto no momento do pedido
   # file_key: Mapped[str] = mapped_column(String(255))


    original_price: Mapped[int] = mapped_column()  # Preço antes de descontos
    discount_amount: Mapped[int] = mapped_column(default=0)  # Valor do desconto neste item
    discount_percentage: Mapped[float | None] = mapped_column(nullable=True)
    variants: Mapped[List["OrderVariant"]] = relationship(back_populates="order_product")

class OrderVariant(Base, TimestampMixin):
    __tablename__ = "order_variants"

    id: Mapped[int] = mapped_column(primary_key=True)

    order_product_id: Mapped[int] = mapped_column(
        ForeignKey("order_products.id", ondelete="CASCADE")
    )
    variant_id: Mapped[int] = mapped_column(
        ForeignKey("variants.id", ondelete="SET NULL"),
        nullable=True
    )

    store_id: Mapped[int] = mapped_column(ForeignKey("stores.id"))

    name: Mapped[str] = mapped_column()

    options: Mapped[List["OrderVariantOption"]] = relationship(back_populates="order_variant")

    order_product: Mapped["OrderProduct"] = relationship(back_populates="variants")

class OrderVariantOption(Base, TimestampMixin):
    __tablename__ = "order_variant_options"

    id: Mapped[int] = mapped_column(primary_key=True)

    order_variant_id: Mapped[int] = mapped_column(
        ForeignKey("order_variants.id", ondelete="CASCADE")
    )
    variant_option_id: Mapped[int | None] = mapped_column(
        ForeignKey("variant_options.id", ondelete="SET NULL"),  # se quiser
        nullable=True
    )

    store_id: Mapped[int] = mapped_column(ForeignKey("stores.id"))

    name: Mapped[str] = mapped_column()
    price: Mapped[int] = mapped_column()
    quantity: Mapped[int] = mapped_column()


    order_variant: Mapped["OrderVariant"] = relationship(back_populates="options")




class OrderPrintLog(Base, TimestampMixin):
    __tablename__ = "order_print_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"))
    printer_destination: Mapped[str] = mapped_column()  # Ex: "cozinha", "balcao"
    status: Mapped[str] = mapped_column(default='pending', nullable=False)
    printed_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    printer_name: Mapped[str | None] = mapped_column()  # Ex: "cozinha", "balcao"
    is_reprint: Mapped[bool] = mapped_column(default=False)
    order: Mapped["Order"] = relationship(back_populates="print_logs")




class Table(Base, TimestampMixin):
    __tablename__ = "tables"
    __table_args__ = (
        CheckConstraint("max_capacity > 0", name="check_max_capacity_positive"),
        Index("idx_table_store", "store_id", "status"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    store_id: Mapped[int] = mapped_column(ForeignKey("stores.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(50))
    status: Mapped[TableStatus] = mapped_column(
        Enum(TableStatus, native_enum=False),
        default=TableStatus.AVAILABLE,
    )

    max_capacity: Mapped[int] = mapped_column(default=4)
    current_capacity: Mapped[int] = mapped_column(default=0)
    opened_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    closed_at: Mapped[datetime | None] = mapped_column(nullable=True)
    is_deleted: Mapped[bool] = mapped_column(default=False)
    deleted_at: Mapped[datetime | None] = mapped_column(nullable=True)
    location_description: Mapped[str | None] = mapped_column(String(100), nullable=True)  # Ex: "Perto da janela"

    orders: Mapped[list["Order"]] = relationship(back_populates="table")
    commands: Mapped[list["Command"]] = relationship(back_populates="table")
    history: Mapped[list["TableHistory"]] = relationship(back_populates="table")



class Command(Base, TimestampMixin):
    __tablename__ = "commands"
    __table_args__ = (
        Index("idx_command_store", "store_id", "status"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    store_id: Mapped[int] = mapped_column(ForeignKey("stores.id", ondelete="CASCADE"))
    table_id: Mapped[int | None] = mapped_column(ForeignKey("tables.id", ondelete="SET NULL"), nullable=True)
    customer_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    customer_contact: Mapped[str | None] = mapped_column(String(50), nullable=True)  # Telefone/email
    status: Mapped[CommandStatus] = mapped_column(
        Enum(CommandStatus, native_enum=False),
        default=CommandStatus.ACTIVE,
    )
    attendant_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    notes: Mapped[str | None] = mapped_column(String(500), nullable=True)  # Observações especiais

    store: Mapped["Store"] = relationship(back_populates="commands")
    table: Mapped["Table | None"] = relationship(back_populates="commands")
    orders: Mapped[list["Order"]] = relationship(back_populates="command")
    attendant: Mapped["User | None"] = relationship()


class OrderPartialPayment(Base, TimestampMixin):
    __tablename__ = "order_partial_payments"

    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id", ondelete="CASCADE"), index=True)
    amount: Mapped[int] = mapped_column()  # Valor em centavos

    # --- CAMPOS ÚTEIS DO SEU MODELO (Mantidos) ---
    received_by: Mapped[str | None] = mapped_column(String(100), nullable=True)  # Ex: "Caixa 1", "Entregador João"
    transaction_id: Mapped[str | None] = mapped_column(String(100),
                                                       nullable=True)  # ID da transação na maquininha, etc.
    notes: Mapped[str | None] = mapped_column(String(500), nullable=True)
    is_confirmed: Mapped[bool] = mapped_column(default=True)

    # --- CONEXÃO CORRIGIDA COM A FORMA DE PAGAMENTO ---
    # ✅ Aponta para a tabela de ativações, que é a fonte da verdade para a loja.
    store_payment_method_activation_id: Mapped[int | None] = mapped_column(
        ForeignKey("store_payment_method_activations.id", ondelete="SET NULL"),
        nullable=True
    )

    # --- RELACIONAMENTOS ATUALIZADOS ---
    order: Mapped["Order"] = relationship(back_populates="partial_payments")

    # ✅ Relacionamento correto para buscar os detalhes da forma de pagamento usada.
    payment_method_activation: Mapped["StorePaymentMethodActivation | None"] = relationship()


class TableHistory(Base):
    __tablename__ = "table_histories"

    id: Mapped[int] = mapped_column(primary_key=True)
    table_id: Mapped[int] = mapped_column(ForeignKey("tables.id"))
    status: Mapped[str] = mapped_column(String(20))
    changed_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    changed_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    notes: Mapped[str | None] = mapped_column(String(500), nullable=True)

    table: Mapped["Table"] = relationship(back_populates="history")
    user: Mapped["User | None"] = relationship()






# class OrderProductTicket(Base, TimestampMixin):
#     __tablename__ = "order_product_tickets"
#
#     id: Mapped[int] = mapped_column(primary_key=True)
#
#     order_product_id: Mapped[int] = mapped_column(ForeignKey("order_products.id"))
#     order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"))
#     store_id: Mapped[int] = mapped_column(ForeignKey("stores.id"))
#
#     ticket_code: Mapped[str] = mapped_column(unique=True)
#     status: Mapped[int] = mapped_column()
#
#     order_product: Mapped[OrderProduct] = relationship(backref="tickets")
#
#
#
#


class StoreRating(Base, TimestampMixin):
    __tablename__ = "store_rating"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    stars: Mapped[int] = mapped_column(nullable=False)
    comment: Mapped[str | None] = mapped_column(String(500), nullable=True)

    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"), nullable=False)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"), nullable=False)
    store_id: Mapped[int] = mapped_column(ForeignKey("stores.id"), nullable=False)

    is_active: Mapped[bool] = mapped_column(default=True)
    owner_reply: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # Relacionamentos
    customer: Mapped["Customer"] = relationship(back_populates="store_ratings")
    order: Mapped["Order"] = relationship()
    store: Mapped["Store"] = relationship(back_populates="store_ratings")

    __table_args__ = (
        UniqueConstraint("customer_id", "order_id", "store_id", name="uq_customer_order_store_rating"),
    )


class ProductRating(Base, TimestampMixin):
    __tablename__ = "product_rating"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    stars: Mapped[int] = mapped_column(nullable=False)
    comment: Mapped[str | None] = mapped_column(String(500), nullable=True)

    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"), nullable=False)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"), nullable=False)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), nullable=False)

    is_active: Mapped[bool] = mapped_column(default=True)
    owner_reply: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # Relacionamentos
    customer: Mapped["Customer"] = relationship(back_populates="product_ratings")
    order: Mapped["Order"] = relationship()
    product: Mapped["Product"] = relationship(back_populates="product_ratings")

    __table_args__ = (
        UniqueConstraint("customer_id", "order_id", "product_id", name="uq_customer_order_product_rating"),
    )





class Feature(Base, TimestampMixin):
    __tablename__ = "features"

    id: Mapped[int] = mapped_column(primary_key=True)

    # A chave única para uso interno no código (ex: "chatbot", "custom_reports")
    feature_key: Mapped[str] = mapped_column(unique=True, index=True)

    # O nome amigável para exibir na interface (ex: "Chatbot com IA")
    name: Mapped[str] = mapped_column()

    # Descrição detalhada do que a funcionalidade faz.
    description: Mapped[str | None] = mapped_column()

    # Define se esta feature pode ser comprada como um add-on.
    is_addon: Mapped[bool] = mapped_column(default=False)

    # Preço do add-on em CENTAVOS para evitar problemas com ponto flutuante.
    # Ex: R$ 29,90 seria armazenado como 2990.
    addon_price: Mapped[int | None] = mapped_column()

    # Relacionamentos para saber em quais planos esta feature está inclusa
    # e quais assinaturas a contrataram como add-on.
    plan_associations: Mapped[list["PlansFeature"]] = relationship(back_populates="feature")
    addon_subscriptions: Mapped[list["PlansAddon"]] = relationship(back_populates="feature")


class PlansFeature(Base, TimestampMixin):
    __tablename__ = "plans_features"

    id: Mapped[int] = mapped_column(primary_key=True)

    # Chaves estrangeiras que criam a ligação
    subscription_plan_id: Mapped[int] = mapped_column(ForeignKey("plans.id"))
    feature_id: Mapped[int] = mapped_column(ForeignKey("features.id"))

    # Relacionamentos para navegar facilmente para o plano e para a feature
    plan: Mapped["Plans"] = relationship(back_populates="included_features")
    feature: Mapped["Feature"] = relationship(back_populates="plan_associations")


class StoreSubscription(Base, TimestampMixin):
    __tablename__ = "store_subscriptions"

    id: Mapped[int] = mapped_column(primary_key=True)
    store_id: Mapped[int] = mapped_column(ForeignKey("stores.id"))
    subscription_plan_id: Mapped[int] = mapped_column(ForeignKey("plans.id"))
    store: Mapped["Store"] = relationship(back_populates="subscriptions")
    status: Mapped[str] = mapped_column()  # ex: "active", "past_due", "canceled"
    current_period_start: Mapped[datetime] = mapped_column()
    current_period_end: Mapped[datetime] = mapped_column()
    gateway_subscription_id: Mapped[str | None] = mapped_column(nullable=True) # Preço do plano em CENTAVOS
    # Relacionamento com o plano principal assinado
    plan: Mapped["Plans"] = relationship(back_populates="subscriptions")

    # NOVO: Relacionamento para ver todos os add-ons contratados nesta assinatura
    subscribed_addons: Mapped[list["PlansAddon"]] = relationship(
        back_populates="store_subscription",
        cascade="all, delete-orphan"
    )


class Plans(Base, TimestampMixin):
    __tablename__ = "plans"

    id: Mapped[int] = mapped_column(primary_key=True)
    plan_name: Mapped[str] = mapped_column()
    price: Mapped[int] = mapped_column()  # Preço do plano em CENTAVOS
    interval: Mapped[int] = mapped_column()  # Intervalo em meses
    available: Mapped[bool] = mapped_column(default=True)
    repeats: Mapped[int | None] = mapped_column(nullable=True)

    product_limit: Mapped[int | None] = mapped_column(nullable=True)
    # Limite de produtos que a loja pode cadastrar no cardápio.

    category_limit: Mapped[int | None] = mapped_column(nullable=True)
    # Limite de categorias de produtos.

    user_limit: Mapped[int | None] = mapped_column(nullable=True)
    # Limite de usuários (funcionários) que podem ser cadastrados para gerenciar a loja.

    monthly_order_limit: Mapped[int | None] = mapped_column(nullable=True)
    # Limite de pedidos que a loja pode receber por mês. Essencial para planos gratuitos.

    location_limit: Mapped[int | None] = mapped_column(nullable=True, default=1)
    # Limite de lojas/endereços que podem ser gerenciados na mesma conta.

    banner_limit: Mapped[int | None] = mapped_column(nullable=True)
    # Limite de banners promocionais que podem ser exibidos no cardápio digital.

    max_active_devices: Mapped[int | None] = mapped_column(nullable=True)
    # Limite de sessões/dispositivos ativos simultaneamente.

    support_type: Mapped[str | None] = mapped_column(nullable=True)

    # --- RELACIONAMENTOS (sem alteração) ---

    included_features: Mapped[List["PlansFeature"]] = relationship(
        back_populates="plan",
        cascade="all, delete-orphan"
    )

    subscriptions: Mapped[List["StoreSubscription"]] = relationship(
        back_populates="plan"
    )

class PlansAddon(Base, TimestampMixin):
    __tablename__ = "plans_addons"

    id: Mapped[int] = mapped_column(primary_key=True)

    # A qual assinatura este add-on pertence
    store_subscription_id: Mapped[int] = mapped_column(ForeignKey("store_subscriptions.id"))

    # Qual feature foi contratada como add-on
    feature_id: Mapped[int] = mapped_column(ForeignKey("features.id"))

    # Preço em CENTAVOS no momento da contratação do add-on.
    # Importante para não afetar o cliente se o preço do add-on mudar no futuro.
    price_at_subscription: Mapped[int] = mapped_column()

    subscribed_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)

    # Relacionamentos para navegar para a assinatura e para a feature
    store_subscription: Mapped["StoreSubscription"] = relationship(back_populates="subscribed_addons")
    feature: Mapped["Feature"] = relationship(back_populates="addon_subscriptions")




class Segment(Base, TimestampMixin):
    __tablename__ = "segments"

    # --- Colunas Principais ---
    id: Mapped[int] = mapped_column(primary_key=True)

    # O nome da especialidade (ex: "Pizzaria", "Hamburgueria").
    # `unique=True` garante que não haverá nomes duplicados.
    # `index=True` torna as buscas por nome mais rápidas.
    name: Mapped[str] = mapped_column(unique=True, index=True)

    # Um campo opcional para descrever a especialidade.
    # Útil para mostrar dicas na UI ou para seu painel de admin.
    description: Mapped[str | None] = mapped_column(nullable=True)

    # Um campo booleano para "desativar" uma especialidade sem precisar deletá-la.
    # Muito útil para manter a integridade dos dados de lojas antigas.
    is_active: Mapped[bool] = mapped_column(default=True)

    # --- Relacionamento (Opcional, mas recomendado) ---
    # Se você tiver uma tabela `stores` e quiser navegar
    # dos segmentos para as lojas que pertencem a ele.
    # stores: Mapped[List["Store"]] = relationship(back_populates="segment")

    def __repr__(self) -> str:
        return f"<Segment(id={self.id}, name='{self.name}')>"


class CashbackTransaction(Base):
    __tablename__ = "cashback_transactions"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"), nullable=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    type: Mapped[str] = mapped_column(String(50))  # "generated", "used", "expired"
    description: Mapped[str] = mapped_column(String(255))
    expires_at: Mapped[datetime] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=func.now())

    user: Mapped["User"] = relationship()
    order: Mapped["Order"] = relationship()


class LoyaltyConfig(Base, TimestampMixin):
    __tablename__ = "loyalty_configs"

    id: Mapped[int] = mapped_column(primary_key=True)
    store_id: Mapped[int] = mapped_column(ForeignKey("stores.id"), unique=True, index=True)

    is_active: Mapped[bool] = mapped_column(default=False, comment="Liga/Desliga o programa de pontos para a loja.")

    # REGRA DE GANHO: Quantos pontos o cliente ganha a cada Real (R$ 1,00) gasto.
    # Exemplo: 1.0 = 1 ponto por real / 0.5 = 1 ponto a cada R$ 2,00.
    points_per_real: Mapped[Decimal] = mapped_column(Numeric(10, 4), default=Decimal("0.0"))

class LoyaltyReward(Base, TimestampMixin):
    __tablename__ = "loyalty_rewards"

    id: Mapped[int] = mapped_column(primary_key=True)
    store_id: Mapped[int] = mapped_column(ForeignKey("stores.id"), index=True)

    is_active: Mapped[bool] = mapped_column(default=True, comment="Permite desativar um prêmio sem apagá-lo.")
    name: Mapped[str] = mapped_column(String(100), comment="Nome do prêmio. Ex: 'Refrigerante Grátis'")
    description: Mapped[str | None] = mapped_column(String(500), comment="Descrição que aparecerá para o cliente.")

    # PONTOS NECESSÁRIOS: Nível de pontos acumulados para desbloquear este prêmio.
    points_threshold: Mapped[int] = mapped_column()

    # O PRÊMIO: Link para o produto que será dado como recompensa.
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"))
    product: Mapped["Product"] = relationship()


class CustomerStoreLoyalty(Base, TimestampMixin):
    __tablename__ = "customer_store_loyalty"

    id: Mapped[int] = mapped_column(primary_key=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"), index=True)
    store_id: Mapped[int] = mapped_column(ForeignKey("stores.id"), index=True)

    # SALDO ATUAL: Pontos que o cliente tem para gastar (pode ser usado para outras mecânicas no futuro).
    points_balance: Mapped[Decimal] = mapped_column(Numeric(10, 4), default=Decimal("0.0"))

    # TOTAL ACUMULADO: Pontos totais que o cliente já ganhou na loja (só aumenta). É este que define o progresso na trilha.
    total_points_earned: Mapped[Decimal] = mapped_column(Numeric(10, 4), default=Decimal("0.0"))

    __table_args__ = (UniqueConstraint('customer_id', 'store_id', name='_customer_store_uc'),)


class CustomerClaimedReward(Base, TimestampMixin):
    __tablename__ = "customer_claimed_rewards"

    id: Mapped[int] = mapped_column(primary_key=True)
    customer_store_loyalty_id: Mapped[int] = mapped_column(ForeignKey("customer_store_loyalty.id"))
    loyalty_reward_id: Mapped[int] = mapped_column(ForeignKey("loyalty_rewards.id"))

    # Link para o pedido onde o prêmio foi efetivamente entregue (fecha o ciclo da auditoria).
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"))
    claimed_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)

    # Garante que um cliente não pode resgatar o mesmo prêmio de marco mais de uma vez.
    __table_args__ = (UniqueConstraint('customer_store_loyalty_id', 'loyalty_reward_id', name='_customer_reward_uc'),)


class LoyaltyTransaction(Base, TimestampMixin):
    __tablename__ = "loyalty_transactions"

    id: Mapped[int] = mapped_column(primary_key=True)
    customer_store_loyalty_id: Mapped[int] = mapped_column(ForeignKey("customer_store_loyalty.id"))
    points_amount: Mapped[Decimal] = mapped_column(Numeric(10, 4))
    transaction_type: Mapped[str] = mapped_column(String(20))  # 'earn', 'spend', 'adjust', etc.
    description: Mapped[str | None] = mapped_column(String(255))
    order_id: Mapped[int | None] = mapped_column(ForeignKey("orders.id"), nullable=True)


class Cart(Base, TimestampMixin):
    __tablename__ = "carts"

    id: Mapped[int] = mapped_column(primary_key=True)

    # Chaves estrangeiras essenciais
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"), index=True)
    store_id: Mapped[int] = mapped_column(ForeignKey("stores.id"), index=True)

    # Status do ciclo de vida do carrinho
    status: Mapped[CartStatus] = mapped_column(Enum(CartStatus, native_enum=False), default=CartStatus.ACTIVE)

    # Campos que podem ser definidos antes do checkout
    coupon_id: Mapped[int | None] = mapped_column(ForeignKey("coupons.id"), nullable=True)
    coupon_code: Mapped[str | None] = mapped_column(nullable=True)
    observation: Mapped[str | None] = mapped_column(nullable=True)

    # Relacionamentos
    customer: Mapped["Customer"] = relationship()
    store: Mapped["Store"] = relationship()
    coupon: Mapped["Coupon"] = relationship()

    items: Mapped[list["CartItem"]] = relationship(
        back_populates="cart",
        cascade="all, delete-orphan"
    )


class CartItem(Base, TimestampMixin):
    __tablename__ = "cart_items"

    id: Mapped[int] = mapped_column(primary_key=True)

    # Vínculo com o carrinho e a loja
    cart_id: Mapped[int] = mapped_column(ForeignKey("carts.id", ondelete="CASCADE"))
    store_id: Mapped[int] = mapped_column(ForeignKey("stores.id", ondelete="CASCADE"))

    # Vínculo com o produto original
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"))

    # Dados essenciais do item
    quantity: Mapped[int] = mapped_column()
    note: Mapped[str | None] = mapped_column(nullable=True)

    # Relacionamentos
    cart: Mapped["Cart"] = relationship(back_populates="items")
    product: Mapped["Product"] = relationship()  # Para fácil acesso aos dados do produto

    variants: Mapped[list["CartItemVariant"]] = relationship(
        back_populates="cart_item",
        cascade="all, delete-orphan"
    )

 # ✅ --- CAMPO FINGERPRINT ADICIONADO --- ✅
    fingerprint: Mapped[str] = mapped_column(index=True, doc="Hash único da configuração do item (produto + variantes) para evitar duplicatas.")

class CartItemVariant(Base, TimestampMixin):
    __tablename__ = "cart_item_variants"

    id: Mapped[int] = mapped_column(primary_key=True)

    # Vínculos
    cart_item_id: Mapped[int] = mapped_column(ForeignKey("cart_items.id", ondelete="CASCADE"))
    variant_id: Mapped[int] = mapped_column(ForeignKey("variants.id", ondelete="CASCADE"))
    store_id: Mapped[int] = mapped_column(ForeignKey("stores.id"))

    # Relacionamentos
    cart_item: Mapped["CartItem"] = relationship(back_populates="variants")
    options: Mapped[list["CartItemVariantOption"]] = relationship(
        back_populates="cart_item_variant",
        cascade="all, delete-orphan"
    )

    variant: Mapped["Variant"] = relationship()


class CartItemVariantOption(Base, TimestampMixin):
    __tablename__ = "cart_item_variant_options"

    id: Mapped[int] = mapped_column(primary_key=True)

    # Vínculos
    cart_item_variant_id: Mapped[int] = mapped_column(ForeignKey("cart_item_variants.id", ondelete="CASCADE"))
    variant_option_id: Mapped[int] = mapped_column(ForeignKey("variant_options.id", ondelete="CASCADE"))
    store_id: Mapped[int] = mapped_column(ForeignKey("stores.id"))
    quantity: Mapped[int] = mapped_column()

    # Relacionamento
    cart_item_variant: Mapped["CartItemVariant"] = relationship(back_populates="options")

    # a partir de um item de carrinho, permitindo buscar seu preço e nome.
    variant_option: Mapped["VariantOption"] = relationship()


class ScheduledPause(Base):
    __tablename__ = "scheduled_pauses"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    reason: Mapped[str | None] = mapped_column(String, nullable=True)  # Ex: "Manutenção da cozinha"
    start_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    end_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, server_default="true", nullable=False)

    # Vínculo
    store_id: Mapped[int] = mapped_column(ForeignKey("stores.id"), nullable=False)

    # Relacionamento
    store: Mapped["Store"] = relationship(back_populates="scheduled_pauses")



class ProductView(Base):
    __tablename__ = "product_views"

    # --- Colunas Principais ---
    id: Mapped[int] = mapped_column(primary_key=True)

    # Chave estrangeira para o produto que foi visto.
    # ON DELETE CASCADE: Se um produto for deletado, todos os seus registros de visualização somem junto.
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"), nullable=False)

    # Chave estrangeira para a loja, essencial para separar os dados de cada cliente.
    store_id: Mapped[int] = mapped_column(ForeignKey("stores.id", ondelete="CASCADE"), nullable=False)

    # O timestamp exato de quando a visualização ocorreu.
    # O banco de dados preencherá isso automaticamente.
    viewed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )

    # (Opcional, mas MUITO poderoso para futuras análises)
    # Se o cliente estiver logado, guardamos o ID dele.
    customer_id: Mapped[int | None] = mapped_column(ForeignKey("customers.id", ondelete="SET NULL"), nullable=True)

    # --- Relacionamentos (opcionais, mas boa prática) ---
    product: Mapped["Product"] = relationship()
    store: Mapped["Store"] = relationship()
    customer: Mapped["Customer | None"] = relationship()

    # --- Índices para Performance ---
    # Otimiza as buscas que faremos para a página de desempenho.
    __table_args__ = (
        Index("ix_product_views_store_id_viewed_at", "store_id", "viewed_at"),
        Index("ix_product_views_product_id_viewed_at", "product_id", "viewed_at"),
    )

    def __repr__(self):
        return f"<ProductView(product_id={self.product_id}, viewed_at='{self.viewed_at}')>"


class MasterProduct(Base):
    __tablename__ = "master_products"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), index=True)
    description: Mapped[str | None] = mapped_column(String(1000))
    ean: Mapped[str | None] = mapped_column(String(13), unique=True, index=True)
    file_key: Mapped[str | None] = mapped_column(String)  # Chave para a imagem no S3/AWS
    brand: Mapped[str | None] = mapped_column(String(80))  # Marca do produto, ex: "Coca-Cola"

    # ✅ SUGESTÃO: Adicione o vínculo com a categoria mestre
    category_id: Mapped[int | None] = mapped_column(ForeignKey("master_categories.id"))
    category:  Mapped[Optional["MasterCategory"]]  = relationship(back_populates="master_products")


    @hybrid_property
    def image_path(self):
        from src.core.aws import get_presigned_url
        return get_presigned_url(self.file_key) if self.file_key else None

    __table_args__ = (
        Index("ix_master_products_name", "name"),
    )


class MasterCategory(Base):
    __tablename__ = "master_categories"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(80), unique=True)

    # Relacionamento reverso
    master_products: Mapped[List["MasterProduct"]] = relationship(back_populates="category")


# Em src/core/models.py

class ProductCategoryLink(Base):
    __tablename__ = "product_category_links"

    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), primary_key=True)
    category_id: Mapped[int] = mapped_column(ForeignKey("categories.id"), primary_key=True)

    # CAMPOS PARA SOBRESCREVER OS VALORES DO PRODUTO NESTA CATEGORIA ESPECÍFICA
    price_override: Mapped[int | None] = mapped_column(nullable=True)
    pos_code_override: Mapped[str | None] = mapped_column(String, nullable=True)
    available_override: Mapped[bool | None] = mapped_column(nullable=True)

    # Relacionamentos para facilitar o acesso
    product: Mapped["Product"] = relationship(back_populates="category_links")
    category: Mapped["Category"] = relationship(back_populates="product_links")
