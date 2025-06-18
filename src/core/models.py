import enum
from datetime import datetime, date, timezone
from typing import Optional, List

from sqlalchemy import DateTime, func, ForeignKey, Index, LargeBinary, UniqueConstraint, Numeric, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship




class Base(DeclarativeBase):
    pass

class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now(), onupdate=func.now())

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

    # Redes sociais
    instagram: Mapped[Optional[str]] = mapped_column(nullable=True)
    facebook: Mapped[Optional[str]] = mapped_column(nullable=True)
    tiktok: Mapped[Optional[str]] = mapped_column(nullable=True)

    # Plano
    plan_type: Mapped[str] = mapped_column(default="free", nullable=False)

    # Relacionamentos


    accesses: Mapped[list["StoreAccess"]] = relationship()
    categories: Mapped[list["Category"]] = relationship()
    payment_methods: Mapped[list["StorePaymentMethods"]] = relationship()
    products: Mapped[list["Product"]] = relationship()
    coupons: Mapped[list["Coupon"]] = relationship()
    variants: Mapped[list["Variant"]] = relationship()

    themes: Mapped[list["StoreTheme"]] = relationship()
    totem_authorizations: Mapped[list["TotemAuthorization"]] = relationship()

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

    store: Mapped[Store] = relationship()
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
    tag: Mapped[str] = mapped_column()

    product_ratings: Mapped[List["ProductRating"]] = relationship(back_populates="product")


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


    store_id: Mapped[int] = mapped_column(ForeignKey("stores.id"))

    variant_id: Mapped[int] = mapped_column(ForeignKey("variants.id", ondelete="CASCADE"))
    variant: Mapped["Variant"] = relationship(back_populates="options")

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

    category_layout:  Mapped[str] = mapped_column()
    product_layout:  Mapped[str] = mapped_column()
    theme_name:  Mapped[str] = mapped_column()


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

    custom_name:  Mapped[str]  = mapped_column()
    custom_icon: Mapped[str] = mapped_column(nullable=True)

    is_active:          Mapped[bool] = mapped_column(default=True)

    active_on_delivery: Mapped[bool] = mapped_column(default=True)
    active_on_pickup:   Mapped[bool] = mapped_column(default=True)
    active_on_counter:  Mapped[bool] = mapped_column(default=True)

    tax_rate:        Mapped[float] = mapped_column(default=0)



    pix_key:        Mapped[str]  = mapped_column(nullable=True)

    orders = relationship("Order", back_populates="store_payment_method")
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

    day_of_week: Mapped[int] = mapped_column()         # 0 - domingo, 6 - sábado
    open_time: Mapped[str] = mapped_column()           # exemplo: '08:00'
    close_time: Mapped[str] = mapped_column()          # exemplo: '18:00'
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
    description: Mapped[str] = mapped_column( default="")

    amount: Mapped[float] = mapped_column()                    # Valor original
    discount: Mapped[float] = mapped_column(default=0.0)
    addition: Mapped[float] = mapped_column(default=0.0)

    due_date: Mapped[date] = mapped_column()
    payment_date: Mapped[date] = mapped_column(nullable=True)

    barcode: Mapped[str | None] = mapped_column( nullable=True)

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
    opened_at: Mapped[datetime] = mapped_column(default=datetime.now(timezone.utc),)
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

    customers_addresses: Mapped[list["Address"]] = relationship("Address", back_populates="customer", cascade="all, delete-orphan")

    store_ratings: Mapped[List["StoreRating"]] = relationship(back_populates="customer")
    product_ratings: Mapped[List["ProductRating"]] = relationship(back_populates="customer")


class Address(Base):
    __tablename__ = "customers_addresses"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id", ondelete="CASCADE"), nullable=False)
    street: Mapped[str] = mapped_column(String(200), nullable=False)
    city: Mapped[str] = mapped_column(String(100), nullable=False)
    state: Mapped[str] = mapped_column(String(50), nullable=True)
    postal_code: Mapped[str] = mapped_column(String(20), nullable=True)

    customer: Mapped["Customer"] = relationship("Customer", back_populates="customers_addresses")



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


class Order(Base, TimestampMixin):
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(primary_key=True)

    sequential_id: Mapped[int] = mapped_column()  # Número sequencial por dia
    public_id: Mapped[str] = mapped_column(unique=True)  # Código público aleatório (tipo ABC123)

    store_id: Mapped[int] = mapped_column(ForeignKey("stores.id"))

    customer_id: Mapped[int | None] = mapped_column(ForeignKey("customers.id"), nullable=True)
    customer_address_id: Mapped[int | None] = mapped_column(ForeignKey("customer_addresses.id"), nullable=True)

    name: Mapped[str] = mapped_column()  # Nome do cliente (se necessário)
    phone: Mapped[str] = mapped_column()
    cpf: Mapped[str] = mapped_column()

    attendant_name: Mapped[str | None] = mapped_column(nullable=True)  # Só para PDV/Mesa

    order_type: Mapped[str] = mapped_column()
    # Ex: "cardapio_digital", "mesa", "pdv"

    delivery_type: Mapped[str] = mapped_column()
    # Ex: "retirada", "delivery"

    total_price: Mapped[int] = mapped_column()

    payment_status: Mapped[str] = mapped_column()
    # Ex: "pendente", "pago", "cancelado"

    order_status: Mapped[str] = mapped_column()
    # Ex: "recebido", "em_preparo", "pronto", "finalizado", "cancelado"

    charge_id: Mapped[int | None] = mapped_column(ForeignKey("charges.id"), nullable=True)
    charge: Mapped["Charge"] = relationship()

    totem_id: Mapped[int | None] = mapped_column(ForeignKey("totem_authorizations.id"), nullable=True)

    products: Mapped[list["OrderProduct"]] = relationship(backref="order")

    payment_method_id = mapped_column(ForeignKey("store_payment_methods.id"), nullable=False)

    payment_method = relationship('StorePaymentMethods')


    needs_change: Mapped[bool] = mapped_column(default=False)  # precisa de troco?
    change_amount: Mapped[float | None] = mapped_column(nullable=True)  # valor que cliente vai entregar (dinheiro em espécie)




    store = relationship("Store", back_populates="orders")


class OrderProduct(Base, TimestampMixin):
    __tablename__ = "order_products"

    id: Mapped[int] = mapped_column(primary_key=True)

    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"))
    store_id: Mapped[int] = mapped_column(ForeignKey("stores.id"))
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"))

    name: Mapped[str] = mapped_column()
    price: Mapped[int] = mapped_column()
    quantity: Mapped[int] = mapped_column()
    note: Mapped[str] = mapped_column(default='')  # <<<<<<<<<< AQUI

    variants: Mapped[list["OrderVariant"]] = relationship(backref="product")



class OrderVariant(Base, TimestampMixin):
    __tablename__ = "order_variants"

    id: Mapped[int] = mapped_column(primary_key=True)

    order_product_id: Mapped[int] = mapped_column(ForeignKey("order_products.id"))
    store_id: Mapped[int] = mapped_column(ForeignKey("stores.id"))
    variant_id: Mapped[int] = mapped_column(ForeignKey("variants.id"))

    name: Mapped[str] = mapped_column()

    options: Mapped[list["OrderVariantOption"]] = relationship(backref="variant")



class OrderVariantOption(Base, TimestampMixin):
    __tablename__ = "order_variant_options"

    id: Mapped[int] = mapped_column(primary_key=True)

    order_variant_id: Mapped[int] = mapped_column(ForeignKey("order_variants.id"))
    store_id: Mapped[int] = mapped_column(ForeignKey("stores.id"))
    variant_option_id: Mapped[int] = mapped_column(ForeignKey("variant_options.id"))

    name: Mapped[str] = mapped_column()
    price: Mapped[int] = mapped_column()
    quantity: Mapped[int] = mapped_column()









































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








































