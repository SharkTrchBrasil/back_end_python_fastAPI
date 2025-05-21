from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, func, ForeignKey, Index, LargeBinary
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
    product_variants: Mapped[list["ProductVariant"]] = relationship()

    themes: Mapped[list["StoreTheme"]] = relationship()
    totem_authorizations: Mapped[list["TotemAuthorization"]] = relationship()




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

class StorePaymentMethods(Base, TimestampMixin):
    __tablename__ = "store_payment_methods"

    id: Mapped[int] = mapped_column(primary_key=True)

    store_id: Mapped[int] = mapped_column(ForeignKey("stores.id"))
    store: Mapped["Store"] = relationship()
    payment_type: Mapped[str] = mapped_column()  # 'Cash', 'Card', 'Pix', ...

    custom_name:  Mapped[str]  = mapped_column()
    custom_icon: Mapped[str] = mapped_column(nullable=True)

    change_back:        Mapped[bool] = mapped_column(default=False)
    credit_in_account:  Mapped[bool] = mapped_column(default=False)
    is_active:          Mapped[bool] = mapped_column(default=True)

    active_on_delivery: Mapped[bool] = mapped_column(default=True)
    active_on_pickup:   Mapped[bool] = mapped_column(default=True)
    active_on_counter:  Mapped[bool] = mapped_column(default=True)

    tax_rate:        Mapped[float] = mapped_column(default=0)
    days_to_receive: Mapped[int]   = mapped_column(default=0)
    has_fee:         Mapped[bool]  = mapped_column(default=False)

    pix_key:        Mapped[str]  = mapped_column(nullable=True)
    pix_key_active: Mapped[bool] = mapped_column(default=False)


class StoreType(Base):
    __tablename__ = "segments"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(unique=True, nullable=False)


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
    category: Mapped[Category] = relationship()
    file_key: Mapped[str] = mapped_column()

    #new  20/05
    product_variant_links: Mapped[list["ProductVariantProduct"]] = relationship(back_populates="product")


    variants: Mapped[list["ProductVariant"]] = relationship(
        secondary="product_variants_products",
        back_populates="products"
    )


    # variants: Mapped[list["ProductVariant"]] = relationship()

    ean: Mapped[str] = mapped_column(default="")
    code: Mapped[str] = mapped_column(default="")
    auto_code: Mapped[bool] = mapped_column(default=True)
    extra_code: Mapped[str] = mapped_column(default="")



    stock_quantity: Mapped[int] = mapped_column(default=0)
    control_stock: Mapped[bool] = mapped_column(default=False)
    min_stock: Mapped[int] = mapped_column(default=0)
    max_stock: Mapped[int] = mapped_column(default=0)

    unit: Mapped[str] = mapped_column(default="")
    allow_fraction: Mapped[bool] = mapped_column(default=False)

    observation: Mapped[str] = mapped_column(default="")
    location: Mapped[str] = mapped_column(default="")


class ProductVariant(Base, TimestampMixin):
    __tablename__ = "product_variants"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column()
    description: Mapped[str] = mapped_column()
    available: Mapped[bool] = mapped_column()

    min_quantity: Mapped[int] = mapped_column()
    max_quantity: Mapped[int] = mapped_column()
    repeatable: Mapped[bool] = mapped_column()

    store_id: Mapped[int] = mapped_column(ForeignKey("stores.id"))

    # new 20/05
   # product_id: Mapped[int] = mapped_column(ForeignKey("products.id"))
    # new  20/05
    #options: Mapped[list["ProductVariantOption"]] = relationship()

    product_links: Mapped[list["ProductVariantProduct"]] = relationship(back_populates="variant")
    products: Mapped[list["Product"]] = relationship(
        secondary="product_variants_products",
        back_populates="variants"
    )


class ProductVariantOption(Base, TimestampMixin):
    __tablename__ = "product_variant_options"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column()
    description: Mapped[str] = mapped_column()
    available: Mapped[bool] = mapped_column()
    price: Mapped[int] = mapped_column()

   # store_id: Mapped[int] = mapped_column(ForeignKey("stores.id"))
   # product_id: Mapped[int] = mapped_column(ForeignKey("products.id"))
    product_variant_id: Mapped[int] = mapped_column(ForeignKey("product_variants.id"))


 #new tablle 20/05
class ProductVariantProduct(Base):
    __tablename__ = "product_variants_products"

    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"))
    variant_id: Mapped[int] = mapped_column(ForeignKey("product_variants.id"))

    product: Mapped["Product"] = relationship(back_populates="product_variant_links")
    variant: Mapped["ProductVariant"] = relationship(back_populates="product_links")

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

    font_family: Mapped[str] = mapped_column()


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


class StoreHours(Base, TimestampMixin):
    __tablename__ = "store_hours"

    id: Mapped[int] = mapped_column(primary_key=True)
    store_id: Mapped[int] = mapped_column(ForeignKey("stores.id", ondelete="CASCADE"))

    day_of_week: Mapped[int] = mapped_column()         # 0 - domingo, 6 - sábado
    open_time: Mapped[str] = mapped_column()           # exemplo: '08:00'
    close_time: Mapped[str] = mapped_column()          # exemplo: '18:00'
    shift_number: Mapped[int] = mapped_column()
    is_active: Mapped[bool] = mapped_column(default=True)