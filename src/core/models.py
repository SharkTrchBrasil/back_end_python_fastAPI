from sqlalchemy import Enum
import enum
from datetime import datetime, date, timezone
from typing import Optional, List

from sqlalchemy import DateTime, func, ForeignKey, Index, LargeBinary, UniqueConstraint, Numeric, String, text, Enum, \
    CheckConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship



class Base(DeclarativeBase):
    pass


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now()  # Usa o timezone do servidor
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now()  # Esta é a forma correta para auto-update
    )



class Store(Base, TimestampMixin):
    __tablename__ = "stores"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column()
    phone: Mapped[str] = mapped_column()

    # Ativação
    is_active: Mapped[bool] = mapped_column(default=False, nullable=False)
    # store_url: Mapped[str] = mapped_column(unique=True, nullable=False)
    # Endereço
    zip_code: Mapped[Optional[str]] = mapped_column(nullable=True)
    street: Mapped[Optional[str]] = mapped_column(nullable=True)
    number: Mapped[Optional[str]] = mapped_column(nullable=True)
    neighborhood: Mapped[Optional[str]] = mapped_column(nullable=True)
    complement: Mapped[Optional[str]] = mapped_column(nullable=True)
    reference: Mapped[Optional[str]] = mapped_column(nullable=True)
    city: Mapped[Optional[str]] = mapped_column(nullable=True)
    state: Mapped[Optional[str]] = mapped_column(nullable=True)
    description: Mapped[Optional[str]] = mapped_column(nullable=True)

    # Identidade visual
    file_key: Mapped[Optional[str]] = mapped_column(nullable=True)
    banner_file_key: Mapped[Optional[str]] = mapped_column(nullable=True)

    # Redes sociais
    instagram: Mapped[Optional[str]] = mapped_column(nullable=True)
    facebook: Mapped[Optional[str]] = mapped_column(nullable=True)
    tiktok: Mapped[Optional[str]] = mapped_column(nullable=True)

    # Plano
    plan_type: Mapped[str] = mapped_column(default="free", nullable=False)
    store_url: Mapped[Optional[str]] = mapped_column(nullable=False)
    # Relacionamentos

    accesses = relationship("StoreAccess", back_populates="store")
    categories = relationship("Category", back_populates="store")
    variants = relationship("Variant", back_populates="store")
    totem_authorizations = relationship("TotemAuthorization", back_populates="store")

    payment_methods: Mapped[list["StorePaymentMethods"]] = relationship()
    products: Mapped[list["Product"]] = relationship()
    coupons: Mapped[list["Coupon"]] = relationship()

    # no Store
    store_customers = relationship("StoreCustomer", back_populates="store")

    themes: Mapped[list["StoreTheme"]] = relationship()

    payables: Mapped[list["StorePayable"]] = relationship()

    orders: Mapped[List["Order"]] = relationship("Order", back_populates="store", cascade="all, delete-orphan")

    cashier_sessions: Mapped[List["CashierSession"]] = relationship(
        "CashierSession", back_populates="store", cascade="all, delete-orphan"
    )

    # Configurações de entrega (relacionamento 1:1)
    delivery_config: Mapped[Optional["StoreDeliveryConfiguration"]] = relationship(
        back_populates="store", uselist=False, cascade="all, delete-orphan"
    )

    # Horários de funcionamento (relacionamento 1:N)
    hours: Mapped[List["StoreHours"]] = relationship(
        back_populates="store", cascade="all, delete-orphan"
    )

    # Cidades de entrega (relacionamento 1:N)
    cities: Mapped[List["StoreCity"]] = relationship(
        back_populates="store", cascade="all, delete-orphan"
    )

    store_ratings: Mapped[List["StoreRating"]] = relationship(back_populates="store")

    settings: Mapped["StoreSettings"] = relationship(
        back_populates="store", uselist=False, cascade="all, delete-orphan"
    )

    commands: Mapped[list["Command"]] = relationship(back_populates="store")


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column()
    name: Mapped[str] = mapped_column()
    hashed_password: Mapped[str] = mapped_column()
    is_active: Mapped[bool] = mapped_column(default=False)
    is_email_verified: Mapped[bool] = mapped_column(default=False)
    verification_code: Mapped[Optional[str]] = mapped_column(nullable=True)


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
    products: Mapped[list["Product"]] = relationship(
        back_populates="category",
        cascade="all, delete-orphan"
    )


class Product(Base, TimestampMixin):
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column()
    description: Mapped[str] = mapped_column()
    base_price: Mapped[int] = mapped_column()
    cost_price: Mapped[int] = mapped_column(default=0)
    available: Mapped[bool] = mapped_column()

    promotion_price: Mapped[int] = mapped_column(default=0)

    featured: Mapped[bool] = mapped_column()
    activate_promotion: Mapped[bool] = mapped_column()

    store_id: Mapped[int] = mapped_column(ForeignKey("stores.id"))
    category_id: Mapped[int] = mapped_column(ForeignKey("categories.id"))
    category: Mapped[Category] = relationship(back_populates="products")
    file_key: Mapped[str] = mapped_column()

    variant_links: Mapped[list["ProductVariantProduct"]] = relationship(
        back_populates="product",
        cascade="all, delete-orphan"
    )

    ean: Mapped[str] = mapped_column(default="")

    stock_quantity: Mapped[int] = mapped_column(default=0)
    control_stock: Mapped[bool] = mapped_column(default=False)
    min_stock: Mapped[int] = mapped_column(default=0)
    max_stock: Mapped[int] = mapped_column(default=0)
    unit: Mapped[str] = mapped_column(default="Unidade")
    tag: Mapped[str] = mapped_column(default="")

    product_ratings: Mapped[List["ProductRating"]] = relationship(back_populates="product")
    sold_count: Mapped[int] = mapped_column(nullable=False, default=0)


class Variant(Base, TimestampMixin):
    __tablename__ = "variants"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column()
    description: Mapped[str] = mapped_column()
    available: Mapped[bool] = mapped_column()
    min_quantity: Mapped[int] = mapped_column()
    max_quantity: Mapped[int] = mapped_column()
    repeatable: Mapped[bool] = mapped_column()

    store_id: Mapped[int] = mapped_column(ForeignKey("stores.id"))
    store: Mapped["Store"] = relationship()

    options: Mapped[list["VariantOptions"]] = relationship(
        back_populates="variant",
        cascade="all, delete-orphan"
    )

    product_links: Mapped[list["ProductVariantProduct"]] = relationship(
        back_populates="variant",
        cascade="all, delete-orphan"
    )


class VariantOptions(Base, TimestampMixin):
    __tablename__ = "variant_options"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column()
    description: Mapped[str] = mapped_column()
    available: Mapped[bool] = mapped_column()
    is_free: Mapped[bool] = mapped_column()
    price: Mapped[int] = mapped_column()
    discount_price: Mapped[int] = mapped_column()
    max_quantity: Mapped[int] = mapped_column()
    variant_id: Mapped[int] = mapped_column(ForeignKey("variants.id", ondelete="CASCADE"))
    variant: Mapped["Variant"] = relationship(back_populates="options")

    store_id: Mapped[int] = mapped_column(ForeignKey("stores.id"))
    store: Mapped["Store"] = relationship()


class ProductVariantProduct(Base):
    __tablename__ = "product_variants_products"
    __table_args__ = (
        UniqueConstraint('product_id', 'variant_id', name='uix_product_variant'),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    variant_id: Mapped[int] = mapped_column(ForeignKey("variants.id", ondelete="CASCADE"))
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"))

    product: Mapped["Product"] = relationship(back_populates="variant_links")
    variant: Mapped["Variant"] = relationship(back_populates="product_links")


class Coupon(Base, TimestampMixin):
    __tablename__ = "coupons"

    id: Mapped[int] = mapped_column(primary_key=True)

    store_id: Mapped[int] = mapped_column(ForeignKey("stores.id"))
    code: Mapped[str] = mapped_column(unique=True)

    discount_percent: Mapped[int | None] = mapped_column()
    discount_fixed: Mapped[int | None] = mapped_column()

    max_uses: Mapped[int] = mapped_column()

    used: Mapped[int] = mapped_column(default=0)

    product_id: Mapped[int | None] = mapped_column(ForeignKey("products.id"))
    #add aqui para buscar o produto selecionado
    product: Mapped[Product] = relationship()
    # ///
    start_date: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    end_date: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    # new campos
    maxUsesPerCustomer: Mapped[int | None] = mapped_column()

    minOrderValue: Mapped[int | None] = mapped_column()

    available: Mapped[bool] = mapped_column(default=True)

    onlyNewCustomers: Mapped[bool] = mapped_column(default=False)
    orders: Mapped[list["Order"]] = relationship(back_populates="coupon")


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
    store_id: Mapped[int] = mapped_column(ForeignKey("stores.id"))
    client_type: Mapped[str] = mapped_column()  # 'admin' ou 'totem'
    sid: Mapped[str] = mapped_column(unique=True)


class AdminConsolidatedStoreSelection(Base, TimestampMixin):  # Adicionei TimestampMixin aqui também para padronizar
    __tablename__ = 'admin_consolidated_store_selection'

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    admin_id: Mapped[int] = mapped_column(ForeignKey("totem_authorizations.id"), nullable=False)
    store_id: Mapped[int] = mapped_column(ForeignKey("stores.id"), nullable=False)

    __table_args__ = (UniqueConstraint('admin_id', 'store_id', name='uq_admin_store_selection'),)

    admin_authorization: Mapped[TotemAuthorization] = relationship(backref="consolidated_selections")
    store: Mapped[Store] = relationship()


class StoreTheme(Base, TimestampMixin):
    __tablename__ = "store_themes"

    id: Mapped[int] = mapped_column(primary_key=True)

    store_id: Mapped[int] = mapped_column(ForeignKey("stores.id"))

    primary_color: Mapped[str] = mapped_column()
    secondary_color: Mapped[str] = mapped_column()
    background_color: Mapped[str] = mapped_column()
    card_color: Mapped[str] = mapped_column()
    on_primary_color: Mapped[str] = mapped_column()
    on_secondary_color: Mapped[str] = mapped_column()
    on_background_color: Mapped[str] = mapped_column()
    on_card_color: Mapped[str] = mapped_column()
    inactive_color: Mapped[str] = mapped_column()
    on_inactive_color: Mapped[str] = mapped_column()

    # Novas cores personalizadas
    sidebar_background_color: Mapped[str] = mapped_column()
    sidebar_text_color: Mapped[str] = mapped_column()
    sidebar_icon_color: Mapped[str] = mapped_column()
    category_background_color: Mapped[str] = mapped_column()
    category_text_color: Mapped[str] = mapped_column()
    product_background_color: Mapped[str] = mapped_column()
    product_text_color: Mapped[str] = mapped_column()
    price_text_color: Mapped[str] = mapped_column()
    cart_background_color: Mapped[str] = mapped_column()
    cart_text_color: Mapped[str] = mapped_column()

    font_family: Mapped[str] = mapped_column()

    category_layout: Mapped[str] = mapped_column()
    product_layout: Mapped[str] = mapped_column()
    theme_name: Mapped[str] = mapped_column()


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


class StorePaymentMethods(Base, TimestampMixin):
    __tablename__ = "store_payment_methods"

    id: Mapped[int] = mapped_column(primary_key=True)
    store_id: Mapped[int] = mapped_column(ForeignKey("stores.id"))
    payment_type: Mapped[str] = mapped_column()  # 'Cash', 'Card', 'Pix', ...

    custom_name: Mapped[str] = mapped_column()
    custom_icon: Mapped[str] = mapped_column(nullable=True)

    is_active: Mapped[bool] = mapped_column(default=True)

    active_on_delivery: Mapped[bool] = mapped_column(default=True)
    active_on_pickup: Mapped[bool] = mapped_column(default=True)
    active_on_counter: Mapped[bool] = mapped_column(default=True)

    tax_rate: Mapped[float] = mapped_column(default=0)

    pix_key: Mapped[str] = mapped_column(nullable=True)

    orders = relationship("Order", back_populates="payment_method", passive_deletes=True)


class StoreDeliveryConfiguration(Base, TimestampMixin):
    __tablename__ = "store_delivery_options"

    id: Mapped[int] = mapped_column(primary_key=True)
    store_id: Mapped[int] = mapped_column(ForeignKey("stores.id"), unique=True)

    # DELIVERY
    delivery_enabled: Mapped[bool] = mapped_column(default=False)
    delivery_estimated_min: Mapped[int] = mapped_column(nullable=True)
    delivery_estimated_max: Mapped[int] = mapped_column(nullable=True)
    delivery_fee: Mapped[float] = mapped_column(nullable=True)
    delivery_min_order: Mapped[float] = mapped_column(nullable=True)
    delivery_scope: Mapped[str] = mapped_column(nullable=True, default='neighborhood')

    # PICKUP
    pickup_enabled: Mapped[bool] = mapped_column(default=False)
    pickup_estimated_min: Mapped[int] = mapped_column(nullable=True)
    pickup_estimated_max: Mapped[int] = mapped_column(nullable=True)
    pickup_instructions: Mapped[str] = mapped_column(nullable=True)

    # COUNTER / TABLE
    table_enabled: Mapped[bool] = mapped_column(default=False)
    table_estimated_min: Mapped[int] = mapped_column(nullable=True)
    table_estimated_max: Mapped[int] = mapped_column(nullable=True)
    table_instructions: Mapped[str] = mapped_column(nullable=True)

    store: Mapped["Store"] = relationship(back_populates="delivery_config")


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


class PayableStatus(str, enum.Enum):
    pending = "pending"
    paid = "paid"
    overdue = "overdue"
    cancelled = "cancelled"


class StorePayable(Base, TimestampMixin):
    __tablename__ = "store_payables"

    id: Mapped[int] = mapped_column(primary_key=True)

    store_id: Mapped[int] = mapped_column(ForeignKey("stores.id", ondelete="CASCADE"))

    title: Mapped[str] = mapped_column()
    description: Mapped[str] = mapped_column(default="")

    amount: Mapped[float] = mapped_column()  # Valor original
    discount: Mapped[float] = mapped_column(default=0.0)
    addition: Mapped[float] = mapped_column(default=0.0)

    due_date: Mapped[date] = mapped_column()
    payment_date: Mapped[date] = mapped_column(nullable=True)

    barcode: Mapped[str | None] = mapped_column(nullable=True)

    status: Mapped[PayableStatus] = mapped_column(default=PayableStatus.pending)

    is_recurring: Mapped[bool] = mapped_column(default=False)
    notes: Mapped[str | None] = mapped_column(nullable=True)

    # Relacionamentos
    store: Mapped["Store"] = relationship(back_populates="payables")


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
    payment_method_id: Mapped[int] = mapped_column(ForeignKey("store_payment_methods.id"))
    description: Mapped[Optional[str]] = mapped_column()
    order_id: Mapped[Optional[int]] = mapped_column(ForeignKey("orders.id"), nullable=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))  # Novo campo recomendado
    order: Mapped[Optional["Order"]] = relationship("Order", back_populates="transactions")

    cashier_session: Mapped["CashierSession"] = relationship("CashierSession", back_populates="transactions")
    user: Mapped["User"] = relationship("User")
    payment_method: Mapped["StorePaymentMethods"] = relationship("StorePaymentMethods")


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


class Address(Base):
    __tablename__ = "customer_addresses"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id", ondelete="CASCADE"), nullable=False)

    street: Mapped[str] = mapped_column(String(200), nullable=False)
    number: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    city_id: Mapped[int] = mapped_column(nullable=False)
    city_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    reference: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    delivery_scope: Mapped[str] = mapped_column(String(20), nullable=False, default='city')

    neighborhood_id: Mapped[Optional[int]] = mapped_column(ForeignKey("store_neighborhoods.id", ondelete="SET NULL"),
                                                           nullable=True)
    neighborhood_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    customer: Mapped["Customer"] = relationship("Customer", back_populates="customer_addresses")
    neighborhood: Mapped[Optional["StoreNeighborhood"]] = relationship("StoreNeighborhood", lazy="joined")


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
    store: Mapped[Store] = relationship()


class OrderStatus(enum.Enum):
    PENDING = "pending"
    PREPARING = "preparing"
    READY = "ready"
    DELIVERED = "delivered"
    CANCELED = "canceled"



class Order(Base, TimestampMixin):
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(primary_key=True)

    sequential_id: Mapped[int] = mapped_column()  # Número sequencial por dia
    public_id: Mapped[str] = mapped_column(unique=True)  # Código público aleatório (tipo ABC123)

    store_id: Mapped[int] = mapped_column(ForeignKey("stores.id"))

    customer_id: Mapped[int | None] = mapped_column(ForeignKey("customers.id"), nullable=True)

    customer_name: Mapped[str | None] = mapped_column(nullable=True)
    customer_phone: Mapped[str | None] = mapped_column(nullable=True)

    # ✅ Campos fixos de endereço no pedido
    street: Mapped[str] = mapped_column()
    number: Mapped[str | None] = mapped_column(nullable=True)
    complement: Mapped[str | None] = mapped_column(nullable=True)
    neighborhood: Mapped[str] = mapped_column()
    city: Mapped[str] = mapped_column()

    attendant_name: Mapped[str | None] = mapped_column(nullable=True)  # Só para PDV/Mesa

    order_type: Mapped[str] = mapped_column()  # Ex: "cardapio_digital", "mesa", "pdv"
    delivery_type: Mapped[str] = mapped_column()  # Ex: "retirada", "delivery"

    total_price: Mapped[int] = mapped_column()
    discounted_total_price: Mapped[int] = mapped_column()

    # totem_id: Mapped[int | None] = mapped_column(
    #     ForeignKey("totem_authorizations.id", ondelete="SET NULL"),
    #     nullable=True
    # )
    # totem: Mapped[TotemAuthorization | None] = relationship()

    payment_status: Mapped[str] = mapped_column()

    order_status: Mapped[OrderStatus] = mapped_column(
        Enum(OrderStatus, native_enum=False),
        default=OrderStatus.PENDING
    )

    payment_method_id: Mapped[int | None] = mapped_column(
        ForeignKey("store_payment_methods.id", ondelete="SET NULL"),
        nullable=True
    )
    payment_method = relationship("StorePaymentMethods", back_populates="orders")

    payment_method_name: Mapped[str | None] = mapped_column(nullable=True)

    coupon_id: Mapped[int | None] = mapped_column(
        ForeignKey("coupons.id", ondelete="SET NULL"),
        nullable=True
    )
    coupon = relationship("Coupon", back_populates="orders")

    needs_change: Mapped[bool] = mapped_column(default=False)
    change_amount: Mapped[float | None] = mapped_column(nullable=True)

    observation: Mapped[str | None] = mapped_column(nullable=True)
    delivery_fee: Mapped[int] = mapped_column(default=0)

    products: Mapped[list["OrderProduct"]] = relationship(backref="order")

    store = relationship("Store", back_populates="orders")
    transactions: Mapped[list["CashierTransaction"]] = relationship(back_populates="order")

    # ✅ Agendamento (tipo iFood)
    is_scheduled: Mapped[bool] = mapped_column(default=False)
    scheduled_for: Mapped[datetime | None] = mapped_column(nullable=True)

    # ✅ Tipo de consumo (onde o cliente vai comer)
    consumption_type: Mapped[str] = mapped_column(default="dine_in")

    # @property
    # def totem_name(self):
    #     return self.totem.totem_name if self.totem else None
    #
    table_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("tables.id", ondelete="SET NULL"), nullable=True
    )

    table: Mapped[Optional["Table"]] = relationship(back_populates="orders")



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

    name: Mapped[str] = mapped_column()
    price: Mapped[int] = mapped_column()
    quantity: Mapped[int] = mapped_column()
    note: Mapped[str] = mapped_column(default='', nullable=False)

    variants: Mapped[list["OrderVariant"]] = relationship(backref="product")


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

    options: Mapped[list["OrderVariantOption"]] = relationship(backref="variant")
    order_product: Mapped[OrderProduct] = relationship()


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

    order_variant: Mapped[OrderVariant] = relationship()


class TableStatus(enum.Enum):
    AVAILABLE = "available"
    OCCUPIED = "occupied"
    RESERVED = "reserved"
    MAINTENANCE = "maintenance"
    CLEANING = "cleaning"

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

class CommandStatus(enum.Enum):
    ACTIVE = "active"
    CLOSED = "closed"
    CANCELED = "canceled"

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
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id", ondelete="CASCADE"))
    amount: Mapped[int] = mapped_column()  # em centavos
    payment_method_id: Mapped[int | None] = mapped_column(ForeignKey("store_payment_methods.id", ondelete="SET NULL"), nullable=True)
    received_by: Mapped[str | None] = mapped_column(String(100), nullable=True)
    transaction_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    notes: Mapped[str | None] = mapped_column(String(500), nullable=True)
    is_confirmed: Mapped[bool] = mapped_column(default=True)

    order: Mapped["Order"] = relationship(back_populates="partial_payments")
    payment_method: Mapped["StorePaymentMethods | None"] = relationship()

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


class StoreCustomer(Base, TimestampMixin):
    __tablename__ = "store_customers"

    store_id: Mapped[int] = mapped_column(ForeignKey("stores.id"), primary_key=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"), primary_key=True)

    total_orders: Mapped[int] = mapped_column(default=1)
    total_spent: Mapped[int] = mapped_column(default=0)
    last_order_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    store = relationship("Store", back_populates="store_customers")
    customer = relationship("Customer", back_populates="store_customers")


class StoreSettings(Base, TimestampMixin):
    __tablename__ = "store_settings"
    store = relationship("Store", back_populates="settings", uselist=False)
    store_id: Mapped[int] = mapped_column(ForeignKey("stores.id", ondelete="CASCADE"), primary_key=True)

    is_delivery_active: Mapped[bool] = mapped_column(default=True)
    is_takeout_active: Mapped[bool] = mapped_column(default=True)
    is_table_service_active: Mapped[bool] = mapped_column(default=True)
    is_store_open: Mapped[bool] = mapped_column(default=True)

    auto_accept_orders: Mapped[bool] = mapped_column(default=False)
    auto_print_orders: Mapped[bool] = mapped_column(default=False)
