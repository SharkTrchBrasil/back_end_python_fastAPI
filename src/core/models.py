from __future__ import annotations
from decimal import Decimal

from sqlalchemy import select, Boolean, JSON, Integer, Time, text, Date
from datetime import datetime, date, timezone
from typing import Optional, List

from sqlalchemy import DateTime, func, Index, LargeBinary, UniqueConstraint, Numeric, String, CheckConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import DeclarativeBase

from src.core.aws import S3_PUBLIC_BASE_URL

from src.core.encryption import encryption_service
from src.core.utils.enums import CashbackType, TableStatus, CommandStatus, StoreVerificationStatus, PaymentMethodType, \
    CartStatus, ProductType, OrderStatus, PayableStatus, ThemeMode, CategoryType, FoodTagEnum, AvailabilityTypeEnum, \
    BeverageTagEnum, PricingStrategyType, CategoryTemplateType, OptionGroupType, ProductStatus, ChatbotMessageGroupEnum
from src.api.schemas.shared.base import VariantType, UIDisplayMode

from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy import Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
import uuid
from sqlalchemy import Table, Column, Integer, ForeignKey, String, Enum, Numeric, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class TimestampMixin:
    # ✅ USA `default` em vez de `server_default`
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        # `default` usa uma função Python, não do banco.
        # Estamos explicitamente dizendo para usar a hora atual em UTC.
        default=lambda: datetime.now(timezone.utc),
        index=True
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        # `onupdate` também usa uma função Python.
        onupdate=lambda: datetime.now(timezone.utc)
    )


class Store(Base, TimestampMixin):
    __tablename__ = "stores"

    id: Mapped[int] = mapped_column(primary_key=True)
    store_uuid: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        server_default=text("gen_random_uuid()"),  # ← Mude aqui
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

    coupons: Mapped[List["Coupon"]] = relationship(
        back_populates="store",
        cascade="all, delete-orphan"  # ✅ ADICIONAR
    )

    # no Store
    store_customers = relationship(
        "StoreCustomer",
        back_populates="store",
        cascade="all, delete-orphan"  # ✅ ADICIONAR
    )

    theme: Mapped["StoreTheme"] = relationship(back_populates="store", uselist=False, cascade="all, delete-orphan")
    banners: Mapped[List["Banner"]] = relationship(back_populates="store", cascade="all, delete-orphan")

    # CORREÇÃO:
    orders: Mapped[List["Order"]] = relationship(
        "Order",
        back_populates="store",
        cascade="all, delete-orphan"
    )





    # ✅ ADICIONE ESTES CAMPOS DO PAGAR.ME:
    pagarme_customer_id: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        index=True,
        doc="ID do cliente no Pagar.me"
    )

    # ✅ CAMPO CRIPTOGRAFADO (armazena bytes)
    _pagarme_card_id_encrypted: Mapped[bytes | None] = mapped_column(
        "pagarme_card_id",  # Nome da coluna no banco
        LargeBinary,
        nullable=True,
        doc="ID do cartão no Pagar.me (criptografado)"
    )

    # ✅ PROPERTY QUE DESCRIPTOGRAFA AUTOMATICAMENTE
    @hybrid_property
    def pagarme_card_id(self) -> str | None:
        """Retorna o card_id descriptografado"""
        if not self._pagarme_card_id_encrypted:
            return None
        try:
            return encryption_service.decrypt(self._pagarme_card_id_encrypted)
        except Exception as e:
            import logging
            logging.error(f"Falha ao descriptografar card_id da loja {self.id}: {e}")
            return None

    # ✅ SETTER QUE CRIPTOGRAFA AUTOMATICAMENTE
    @pagarme_card_id.setter
    def pagarme_card_id(self, value: str | None):
        """Salva o card_id criptografado"""
        if value is None:
            self._pagarme_card_id_encrypted = None
        else:
            self._pagarme_card_id_encrypted = encryption_service.encrypt(value)





    monthly_charges: Mapped[list["MonthlyCharge"]] = relationship(
        back_populates="store",
        cascade="all, delete-orphan"  # ✅ ADICIONAR
    )
    products = relationship(
        "Product",
        back_populates="store",
        order_by="asc(Product.priority)",
        cascade="all, delete-orphan"  # ✅ ADICIONAR
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

    store_ratings: Mapped[List["StoreRating"]] = relationship(
        back_populates="store",
        cascade="all, delete-orphan"  # ✅ ADICIONAR
    )

    subscriptions: Mapped[list["StoreSubscription"]] = relationship(
        "StoreSubscription",
        back_populates="store",
        lazy="select",
        cascade="all, delete-orphan"  # ✅ ADICIONAR
    )



    accesses: Mapped[List["StoreAccess"]] = relationship(
        back_populates="store", cascade="all, delete-orphan"
    )


    saloons: Mapped[list["Saloon"]] = relationship(
        back_populates="store",
        cascade="all, delete-orphan",
        order_by="asc(Saloon.display_order)"
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

    # Dentro da classe Store, junto com os outros relacionamentos

    chatbot_messages: Mapped[list["StoreChatbotMessage"]] = relationship(
        back_populates="store",
        cascade="all, delete-orphan"
    )

    # Dentro da classe Store, junto com os outros relacionamentos
    chatbot_config: Mapped[Optional["StoreChatbotConfig"]] = relationship(
        back_populates="store",
        uselist=False,  # Indica que é uma relação um-para-um
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
    phone: Mapped[Optional[str]] = mapped_column(nullable=True)  # ALTERADO
    hashed_password: Mapped[str] = mapped_column()
    is_active: Mapped[bool] = mapped_column(default=True)
    is_email_verified: Mapped[bool] = mapped_column(default=False)

    is_superuser: Mapped[bool] = mapped_column(default=False, nullable=False)

    is_store_owner: Mapped[bool] = mapped_column(
        default=True,
        nullable=False,
        doc="True = usuário criou sua própria loja | False = foi adicionado como funcionário"
    )

    verification_code: Mapped[Optional[str]] = mapped_column(nullable=True)  # ALTERADO
    cpf: Mapped[Optional[str]] = mapped_column(unique=True, index=True, nullable=True)  # ALTERADO
    birth_date: Mapped[Optional[date]] = mapped_column(nullable=True)  # ALTERADO


    referral_code: Mapped[str] = mapped_column(unique=True, index=True)
    referred_by_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)  # ALTERADO

    referrer: Mapped[Optional["User"]] = relationship(remote_side=[id])  # ALTERADO

    sessions = relationship("StoreSession", back_populates="user", cascade="all, delete-orphan")

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


# --- MODELO PRINCIPAL DE CATEGORIA (ATUALIZADO) ---
class Category(Base, TimestampMixin):
    __tablename__ = "categories"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    priority: Mapped[int] = mapped_column(default=0)
    store_id: Mapped[int] = mapped_column(ForeignKey("stores.id"))
    file_key: Mapped[str | None] = mapped_column(String, nullable=True)
    is_active: Mapped[bool] = mapped_column(default=True)
    type: Mapped[CategoryType] = mapped_column(Enum(CategoryType, name="category_type_enum"),
                                               default=CategoryType.GENERAL)

    store: Mapped[Store] = relationship()
    product_links: Mapped[List["ProductCategoryLink"]] = relationship(back_populates="category",
                                                                      cascade="all, delete-orphan")

    # ✨ RELAÇÃO ATUALIZADA: Uma categoria agora tem vários "Grupos de Opções"
    option_groups: Mapped[List["OptionGroup"]] = relationship(back_populates="category", cascade="all, delete-orphan",
                                                              lazy="selectin")

    # Campos de cashback e impressora
    cashback_type: Mapped[CashbackType] = mapped_column(Enum(CashbackType, name="cashback_type_enum"),
                                                        default=CashbackType.NONE)
    cashback_value: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal('0.00'))
    printer_destination: Mapped[str | None] = mapped_column(String(50), nullable=True)

    pricing_strategy: Mapped[PricingStrategyType] = mapped_column(
        Enum(PricingStrategyType, name="pricing_strategy_type_enum"),
        nullable=False,
        server_default="SUM_OF_ITEMS"
    )

    price_varies_by_size: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=text('false')  # Define 'false' como padrão no banco
    )

    availability_type: Mapped[AvailabilityTypeEnum] = mapped_column(
        Enum(AvailabilityTypeEnum, name="availability_type_enum"),
        default=AvailabilityTypeEnum.ALWAYS,
        server_default="ALWAYS"
    )

    # ✅ NOVO CAMPO ADICIONADO AQUI
    selected_template: Mapped[CategoryTemplateType] = mapped_column(
        Enum(CategoryTemplateType, name="category_template_type_enum"),
        nullable=False,
        server_default=text("'BLANK'")  # Define 'BLANK' ou 'NONE' como padrão
    )

    schedules: Mapped[List["CategorySchedule"]] = relationship(back_populates="category", cascade="all, delete-orphan",
                                                               lazy="selectin")


class CategorySchedule(Base, TimestampMixin):
    __tablename__ = "category_schedules"

    id: Mapped[int] = mapped_column(primary_key=True)
    # Armazena os dias da semana (ex: [0, 1, 4] para Dom, Seg, Qui)
    days_of_week: Mapped[List[int]] = mapped_column(ARRAY(Integer), nullable=False)

    category_id: Mapped[int] = mapped_column(ForeignKey("categories.id"))
    category: Mapped["Category"] = relationship(back_populates="schedules")

    time_shifts: Mapped[List["TimeShift"]] = relationship(back_populates="schedule", cascade="all, delete-orphan",
                                                          lazy="selectin")


class TimeShift(Base, TimestampMixin):
    __tablename__ = "time_shifts"

    id: Mapped[int] = mapped_column(primary_key=True)
    start_time: Mapped[Time] = mapped_column(Time, nullable=False)  # Ex: 18:00
    end_time: Mapped[Time] = mapped_column(Time, nullable=False)  # Ex: 23:00

    schedule_id: Mapped[int] = mapped_column(ForeignKey("category_schedules.id"))
    schedule: Mapped["CategorySchedule"] = relationship(back_populates="time_shifts")


class OptionGroup(Base, TimestampMixin):
    __tablename__ = "option_groups"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    min_selection: Mapped[int] = mapped_column(default=1)
    max_selection: Mapped[int] = mapped_column(default=1)
    priority: Mapped[int] = mapped_column(default=0)
    category_id: Mapped[int] = mapped_column(ForeignKey("categories.id"))

    # CORREÇÃO: Use string simples sem text()
    pricing_strategy: Mapped[PricingStrategyType] = mapped_column(
        Enum(PricingStrategyType, name="pricing_strategy_type_enum"),
        nullable=False,
        server_default="SUM_OF_ITEMS"  # ← String simples
    )

    is_configurable: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=text('true')  # Para boolean pode usar text
    )

    # CORREÇÃO: Use string simples sem text()
    group_type: Mapped[OptionGroupType] = mapped_column(
        Enum(OptionGroupType, name="option_group_type_enum"),
        nullable=False,
        server_default="GENERIC"  # ← String simples
    )

    # Relacionamentos
    category: Mapped["Category"] = relationship(back_populates="option_groups")
    items: Mapped[List["OptionItem"]] = relationship(
        back_populates="group",
        cascade="all, delete-orphan",
        lazy="selectin"
    )


# Em seus modelos SQLAlchemy
class OptionItem(Base, TimestampMixin):
    __tablename__ = "option_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    description: Mapped[str | None] = mapped_column(String(255), nullable=True)
    price: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal('0.00'))
    is_active: Mapped[bool] = mapped_column(default=True)
    priority: Mapped[int] = mapped_column(default=0)

    # --- CAMPOS ADICIONADOS PARA O PENTE FINO ---
    external_code: Mapped[str | None] = mapped_column(String(50), nullable=True)  # ✅ Para o Cód. PDV
    slices: Mapped[int | None] = mapped_column(nullable=True)  # ✅ Para a Qtd. Pedaços
    max_flavors: Mapped[int | None] = mapped_column(nullable=True)  # ✅ Para a Qtd. Sabores
    # ✅ 1. ADICIONE O CAMPO AQUI
    file_key: Mapped[str | None] = mapped_column(String, nullable=True, doc="Chave do arquivo da imagem no S3.")

    option_group_id: Mapped[int] = mapped_column(ForeignKey("option_groups.id"))
    group: Mapped["OptionGroup"] = relationship(back_populates="items")

    flavor_prices: Mapped[List["FlavorPrice"]] = relationship(back_populates="size_option")

    tags: Mapped[List[FoodTagEnum]] = mapped_column(
        ARRAY(Enum(FoodTagEnum, name="food_tag_enum", create_type=False)),
        nullable=False,
        server_default="{}"
    )


class FlavorPrice(Base, TimestampMixin):
    __tablename__ = "flavor_prices"

    id: Mapped[int] = mapped_column(primary_key=True)
    price: Mapped[int] = mapped_column(nullable=False)  # Preço em centavos

    # ✅ NOVO CAMPO: Código PDV
    pos_code: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # ✅ NOVO CAMPO: Status de disponibilidade
    is_available: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    # --- Relacionamentos (continuam iguais) ---
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"))
    product: Mapped["Product"] = relationship(back_populates="prices")

    size_option_id: Mapped[int] = mapped_column(ForeignKey("option_items.id"))
    size_option: Mapped["OptionItem"] = relationship(back_populates="flavor_prices")

    __table_args__ = (UniqueConstraint('product_id', 'size_option_id', name='_product_size_price_uc'),)


class Product(Base, TimestampMixin):
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(80))
    # ✅ Torne a descrição opcional também, é uma boa prática
    description: Mapped[str | None] = mapped_column(String(1000), nullable=True)

    # ✅ Adicione os padrões aqui
    status: Mapped[ProductStatus] = mapped_column(
        Enum(ProductStatus, name="product_status_enum"),
        nullable=False,
        default=ProductStatus.ACTIVE,
        server_default=text("'ACTIVE'")
    )

    priority: Mapped[int] = mapped_column(default=0)

    featured: Mapped[bool] = mapped_column(default=False)

    store_id: Mapped[int] = mapped_column(ForeignKey("stores.id"))

    store: Mapped["Store"] = relationship(back_populates="products")

    category_links: Mapped[List["ProductCategoryLink"]] = relationship(back_populates="product",
                                                                       cascade="all, delete-orphan")

    ean: Mapped[str | None] = mapped_column(nullable=True)

    stock_quantity: Mapped[int] = mapped_column(default=0)
    control_stock: Mapped[bool] = mapped_column(default=False)
    min_stock: Mapped[int] = mapped_column(default=0)
    max_stock: Mapped[int] = mapped_column(default=0)
    unit: Mapped[str] = mapped_column(default="Unidade")

    serves_up_to: Mapped[int | None] = mapped_column(nullable=True, doc="Indica quantas pessoas o item serve")
    weight: Mapped[int | None] = mapped_column(nullable=True, doc="Peso do item em gramas ou ml")

    product_ratings: Mapped[List["ProductRating"]] = relationship(back_populates="product")
    sold_count: Mapped[int] = mapped_column(nullable=False, default=0)

    cashback_type: Mapped[CashbackType] = mapped_column(Enum(CashbackType, name="cashback_type_enum"),
                                                        default=CashbackType.NONE)
    cashback_value: Mapped[int] = mapped_column(default=0)

    product_type: Mapped[ProductType] = mapped_column(default=ProductType.PREPARED)

    order_items: Mapped[list["OrderProduct"]] = relationship(back_populates="product")

    video_url: Mapped[str | None] = mapped_column(String(500), nullable=True)

    gallery_images: Mapped[List["ProductImage"]] = relationship(
        back_populates="product",
        cascade="all, delete-orphan",
        order_by="asc(ProductImage.display_order)",
        lazy="selectin"  # 'selectin' é ótimo para carregar as galerias
    )

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

    dietary_tags: Mapped[List[FoodTagEnum]] = mapped_column(
        ARRAY(Enum(FoodTagEnum, name="food_tag_enum", create_type=False)),
        nullable=False,
        server_default="{}"
    )

    beverage_tags: Mapped[List[BeverageTagEnum]] = mapped_column(
        ARRAY(Enum(BeverageTagEnum, name="beverage_tag_enum")),  # 'create_type=True' é o padrão
        nullable=False,
        server_default="{}"
    )

    master_product_id: Mapped[int | None] = mapped_column(ForeignKey("master_products.id"), nullable=True)
    master_product: Mapped[Optional["MasterProduct"]] = relationship()

    prices: Mapped[List["FlavorPrice"]] = relationship(back_populates="product", cascade="all, delete-orphan")

    @hybrid_property
    def cover_image_key(self) -> str | None:
        """
        Retorna a chave da primeira imagem da galeria (a capa).
        A galeria já é ordenada por 'display_order' no relacionamento.
        """
        if self.gallery_images:
            return self.gallery_images[0].file_key
        return None


class ProductCategoryLink(Base):
    __tablename__ = "product_category_links"

    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), primary_key=True)
    category_id: Mapped[int] = mapped_column(ForeignKey("categories.id"), primary_key=True)

    # --- CAMPOS UNIFICADOS E CORRIGIDOS ---

    # Preço principal, obrigatório
    price: Mapped[int] = mapped_column(nullable=False)

    # Custo, opcional
    cost_price: Mapped[int | None] = mapped_column(nullable=True)

    # Regras de promoção
    is_on_promotion: Mapped[bool] = mapped_column(default=False)
    promotional_price: Mapped[int | None] = mapped_column(nullable=True)

    # Controles de visibilidade e ordem
    is_available: Mapped[bool] = mapped_column(default=True)
    is_featured: Mapped[bool] = mapped_column(default=False)
    display_order: Mapped[int] = mapped_column(default=0)  # 'display_order' é um nome melhor que 'priority' aqui

    # Campo de integração
    pos_code: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # Relacionamentos
    product: Mapped["Product"] = relationship(back_populates="category_links")
    category: Mapped["Category"] = relationship(back_populates="product_links")


class ProductImage(Base, TimestampMixin):
    __tablename__ = "product_images"
    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"))
    file_key: Mapped[str] = mapped_column(nullable=False)
    display_order: Mapped[int] = mapped_column(default=0)
    product: Mapped["Product"] = relationship(back_populates="gallery_images")


class Variant(Base, TimestampMixin):
    __tablename__ = "variants"

    id: Mapped[int] = mapped_column(primary_key=True)

    name: Mapped[str] = mapped_column(unique=True, doc="Nome único do template. Ex: 'Adicionais', 'Bebidas', 'Molhos'")
    is_available: Mapped[bool] = mapped_column(default=True)

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
    product_links: Mapped[list["ProductVariantLink"]] = relationship(back_populates="variant",
                                                                     cascade="all, delete-orphan")
    store: Mapped["Store"] = relationship(back_populates="variants")


class VariantOption(Base, TimestampMixin):
    __tablename__ = "variant_options"

    id: Mapped[int] = mapped_column(primary_key=True)

    variant_id: Mapped[int] = mapped_column(ForeignKey("variants.id", ondelete="CASCADE"))
    variant: Mapped["Variant"] = relationship(back_populates="options")

    linked_product_id: Mapped[int | None] = mapped_column(ForeignKey("products.id", ondelete="SET NULL"), nullable=True,
                                                          doc="...")
    linked_product: Mapped[Optional["Product"]] = relationship()
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

    @hybrid_property
    def resolved_name(self) -> str:
        """Retorna o nome de sobreposição ou o nome do produto vinculado."""
        if self.name_override:
            return self.name_override
        if self.linked_product:
            return self.linked_product.name
        return "Opção sem nome"

    @hybrid_property
    def resolved_price(self) -> int:
        """
        Retorna o preço da opção. Com a nova regra, ele é SEMPRE
        o price_override, ou 0 se não for definido.
        """
        return self.price_override if self.price_override is not None else 0

    @hybrid_property
    def is_actually_available(self) -> bool:
        """Verifica a disponibilidade real do item, considerando o controle de estoque."""
        if not self.available:
            return False
        if not self.track_inventory:
            return True
        return self.stock_quantity > 0


class ProductVariantLink(Base, TimestampMixin):
    __tablename__ = "product_variant_links"

    id: Mapped[int] = mapped_column(primary_key=True)

    # ✅ CORREÇÃO APLICADA AQUI
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"))
    variant_id: Mapped[int] = mapped_column(ForeignKey("variants.id"))

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

    # ✅ 3. ATUALIZE OS RELACIONAMENTOS PARA USAR `back_populates`
    product: Mapped["Product"] = relationship(back_populates="variant_links")
    variant: Mapped["Variant"] = relationship(back_populates="product_links")

    # ✅ 4. GARANTA A UNICIDADE COM UMA `UniqueConstraint`
    # Isso impede que o mesmo produto seja ligado ao mesmo grupo mais de uma vez.
    __table_args__ = (
        UniqueConstraint('product_id', 'variant_id', name='uq_product_variant'),
    )


class ProductDefaultOption(Base, TimestampMixin):
    __tablename__ = "product_default_options"

    product_id: Mapped[int] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"), primary_key=True)
    variant_option_id: Mapped[int] = mapped_column(ForeignKey("variant_options.id", ondelete="CASCADE"),
                                                   primary_key=True)

    # Relacionamentos para facilitar as consultas
    product: Mapped["Product"] = relationship(back_populates="default_options")
    option: Mapped["VariantOption"] = relationship()


class KitComponent(Base, TimestampMixin):
    __tablename__ = "kit_components"

    # ✅ CORREÇÃO APLICADA AQUI
    kit_product_id: Mapped[int] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"), primary_key=True)
    component_product_id: Mapped[int] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"), primary_key=True)

    quantity: Mapped[int] = mapped_column(default=1)  # Qtd do componente dentro do kit

    # Relacionamentos
    kit: Mapped["Product"] = relationship(foreign_keys=[kit_product_id], back_populates="components")
    component: Mapped["Product"] = relationship(foreign_keys=[component_product_id])


class Coupon(Base, TimestampMixin):
    __tablename__ = "coupons"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    description: Mapped[str] = mapped_column(String(255))

    # A AÇÃO do cupom
    discount_type: Mapped[str] = mapped_column(String(20))  # 'PERCENTAGE', 'FIXED_AMOUNT', 'FREE_DELIVERY'
    discount_value: Mapped[float] = mapped_column()  # Em % ou centavos

    max_discount_amount: Mapped[int] = mapped_column(nullable=True)  # Teto do desconto em centavos

    # Validade e Status
    start_date: Mapped[datetime] = mapped_column()
    end_date: Mapped[datetime] = mapped_column()
    is_active: Mapped[bool] = mapped_column(default=True)

    whatsapp_notification_sent_at: Mapped[datetime | None] = mapped_column(
        nullable=True,
        doc="Timestamp de quando a notificação em massa foi concluída."
    )
    whatsapp_notification_status: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
        default='pending',
        doc="Status do envio: pending, queued, sending, sent, failed"
    )

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
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"), unique=True)  # Garante um uso por pedido
    used_at: Mapped[datetime] = mapped_column(default=func.now(timezone.utc))

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



class StoreSession(Base):
    __tablename__ = "store_sessions"

    id = Column(Integer, primary_key=True, index=True)
    sid = Column(String, unique=True, nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    store_id = Column(Integer, ForeignKey("stores.id", ondelete="CASCADE"), nullable=True)
    client_type = Column(String, nullable=False)  # 'admin', 'totem', etc.

    # ✅ NOVOS CAMPOS
    device_name = Column(String, nullable=True)  # Ex: "iPhone 14 Pro"
    device_type = Column(String, nullable=True)  # Ex: "mobile", "desktop", "tablet"
    platform = Column(String, nullable=True)  # Ex: "iOS", "Windows", "Android"
    browser = Column(String, nullable=True)  # Ex: "Chrome", "Safari", "Flutter"
    ip_address = Column(String, nullable=True)  # IP de conexão

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_activity = Column(DateTime, default=datetime.utcnow)  # ✅ NOVO

    # Relacionamentos
    user = relationship("User", back_populates="sessions")
    store = relationship("Store")



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


class ChatbotMessageTemplate(Base, TimestampMixin):
    __tablename__ = "chatbot_message_templates"

    id: Mapped[int] = mapped_column(primary_key=True)

    # Chave única para uso no código (ex: "welcome_message", "order_accepted")
    message_key: Mapped[str] = mapped_column(String(100), unique=True, index=True)

    # Nome amigável para a UI (ex: "Mensagem de Boas-vindas")
    name: Mapped[str] = mapped_column(String(100))

    # Descrição que aparece no painel de admin
    description: Mapped[str | None] = mapped_column(Text)

    # Grupo ao qual a mensagem pertence (para organizar na UI)
    message_group: Mapped[ChatbotMessageGroupEnum] = mapped_column(Enum(ChatbotMessageGroupEnum))

    # O conteúdo padrão que toda loja terá ao iniciar
    default_content: Mapped[str] = mapped_column(Text)

    # (Opcional, mas muito útil) Lista de variáveis disponíveis para esta mensagem
    available_variables: Mapped[list[str] | None] = mapped_column(ARRAY(String))

    # Relacionamento para ver todas as configurações de lojas que usam este template
    store_configs: Mapped[list["StoreChatbotMessage"]] = relationship(back_populates="template")


class StoreChatbotMessage(Base, TimestampMixin):
    __tablename__ = "store_chatbot_messages"

    id: Mapped[int] = mapped_column(primary_key=True)

    store_id: Mapped[int] = mapped_column(ForeignKey("stores.id"), index=True)

    # Link para o template mestre
    template_key: Mapped[str] = mapped_column(ForeignKey("chatbot_message_templates.message_key"), index=True)

    # O conteúdo personalizado pelo lojista. Se for nulo, o sistema usa o default_content do template.
    custom_content: Mapped[str | None] = mapped_column(Text)

    # O switch de "ligado/desligado" para esta mensagem nesta loja
    is_active: Mapped[bool] = mapped_column(default=True)

    # Relacionamentos
    store: Mapped["Store"] = relationship()
    template: Mapped["ChatbotMessageTemplate"] = relationship(back_populates="store_configs")

    __table_args__ = (
        UniqueConstraint('store_id', 'template_key', name='_store_template_uc'),
    )

    @hybrid_property
    def final_content(self) -> str:
        """
        Retorna o conteúdo personalizado se existir, senão o conteúdo padrão do template.
        Este é o campo que o Pydantic Schema 'StoreChatbotMessageSchema' espera.
        """
        if self.custom_content:
            return self.custom_content
        # É crucial que o relacionamento 'template' seja carregado na consulta
        # (o que sua função `get_store_base_details` já faz corretamente!)
        if self.template:
            return self.template.default_content
        return ""


class StoreChatbotConfig(Base, TimestampMixin):
    __tablename__ = "store_chatbot_configs"

    id: Mapped[int] = mapped_column(primary_key=True)

    # Chave estrangeira para a loja. unique=True garante que cada loja só pode ter uma configuração.
    store_id: Mapped[int] = mapped_column(ForeignKey("stores.id"), unique=True, index=True)

    # Informações do WhatsApp conectado
    whatsapp_number: Mapped[str | None] = mapped_column(String(50), nullable=True)
    whatsapp_name: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # Status da conexão: 'disconnected', 'pending', 'awaiting_qr', 'connected', 'error'
    connection_status: Mapped[str] = mapped_column(String(50), default='disconnected', nullable=False)

    # Último QR Code ou código de conexão gerado
    last_qr_code: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_connection_code: Mapped[str | None] = mapped_column(String(20), nullable=True)

    # Timestamps
    last_connected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)  # <- NOVO CAMPO
    # (Opcional, mas útil) Caminho para o arquivo de sessão persistente
    session_path: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Relacionamento de volta para a classe Store (a última alteração que fizemos)
    store: Mapped["Store"] = relationship(back_populates="chatbot_config")


# ... (cole isso no final do seu arquivo models.py)

class ChatbotAuthCredential(Base):
    """
    Armazena as credenciais de autenticação da Baileys (WhatsApp)
    para cada sessão, permitindo a reconexão sem precisar ler o QR Code novamente.
    Esta tabela substitui o uso de arquivos no disco, sendo mais performática e
    estável para um ambiente de produção.
    """
    __tablename__ = "chatbot_auth_credentials"

    # Chave primária composta: cada credencial é única para uma sessão
    session_id: Mapped[str] = mapped_column(String(255), primary_key=True)
    cred_id: Mapped[str] = mapped_column(String(255), primary_key=True)

    # O valor da credencial, armazenado como JSONB para eficiência no PostgreSQL
    cred_value: Mapped[dict] = mapped_column(JSONB, nullable=False)

    def __repr__(self) -> str:
        return f"<ChatbotAuthCredential(session='{self.session_id}', cred='{self.cred_id}')>"


class PaymentMethodGroup(Base):
    __tablename__ = "payment_method_groups"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(50), unique=True)
    title: Mapped[str] = mapped_column(String(255), nullable=True)
    description: Mapped[str] = mapped_column(String(255), nullable=True)
    priority: Mapped[int] = mapped_column(default=0)

    # ✅ RELAÇÃO ATUALIZADA: Um grupo agora tem vários métodos diretamente.
    methods: Mapped[list["PlatformPaymentMethod"]] = relationship(back_populates="group")


class PlatformPaymentMethod(Base, TimestampMixin):
    __tablename__ = "platform_payment_methods"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(50), unique=True)
    description: Mapped[str] = mapped_column(String(255), nullable=True)
    method_type: Mapped[PaymentMethodType] = mapped_column(Enum(PaymentMethodType), nullable=False)
    icon_key: Mapped[str] = mapped_column(String(100), nullable=True)
    is_globally_enabled: Mapped[bool] = mapped_column(default=True)
    requires_details: Mapped[bool] = mapped_column(default=False)
    is_default_for_new_stores: Mapped[bool] = mapped_column(default=False, nullable=False)

    # ✅ CORREÇÃO: A chave estrangeira agora aponta para `payment_method_groups`.
    group_id: Mapped[int] = mapped_column(ForeignKey("payment_method_groups.id"), nullable=False)

    # ✅ CORREÇÃO: O relacionamento agora é com `PaymentMethodGroup`.
    group: Mapped["PaymentMethodGroup"] = relationship(back_populates="methods")

    activations: Mapped[list["StorePaymentMethodActivation"]] = relationship(back_populates="platform_method")


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

class StoreOperationConfig(Base, TimestampMixin):
    __tablename__ = "store_operation_config"  # Novo nome de tabela

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
    free_delivery_threshold: Mapped[float] = mapped_column(nullable=True)  # Valor a partir do qual o frete é grátis


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

    # ✅ CORREÇÃO: Usa o nome correto no back_populates
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

    opening_amount: Mapped[int] = mapped_column(Integer)
    cash_added: Mapped[int] = mapped_column(Integer, default=0)
    cash_removed: Mapped[int] = mapped_column(Integer, default=0)
    cash_difference: Mapped[int] = mapped_column(Integer, default=0)
    expected_amount: Mapped[int] = mapped_column(Integer, default=0)
    informed_amount: Mapped[int] = mapped_column(Integer, default=0)

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

    # ✅ CORREÇÃO: Adiciona o back_populates
    receivables: Mapped[list["StoreReceivable"]] = relationship(back_populates="customer")


class StoreCustomer(Base, TimestampMixin):
    __tablename__ = "store_customers"

    store_id: Mapped[int] = mapped_column(ForeignKey("stores.id"), primary_key=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"), primary_key=True)

    total_orders: Mapped[int] = mapped_column(default=1)
    total_spent: Mapped[int] = mapped_column(default=0)
    last_order_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True, nullable=True)
    store = relationship("Store", back_populates="store_customers")
    customer = relationship("Customer", back_populates="store_customers")

    # ✅ NOVO CAMPO ADICIONADO
    last_reactivation_attempt_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
        doc="Timestamp da última tentativa de envio de mensagem de reativação."
    )


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

    product_id: Mapped[int | None] = mapped_column(ForeignKey("products.id", ondelete="SET NULL"), nullable=True)
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
    cashback_amount_generated: Mapped[int] = mapped_column(default=0)
    cashback_used: Mapped[int] = mapped_column(default=0)

    # ✅ CORREÇÃO 1: Usando back_populates para consistência
    products: Mapped[list["OrderProduct"]] = relationship(
        back_populates="order",
        cascade="all, delete-orphan"  # Adicionando cascade que estava faltando
    )

    store = relationship("Store", back_populates="orders")

    transactions: Mapped[list["CashierTransaction"]] = relationship(back_populates="order")

    # Agendamento e consumo
    is_scheduled: Mapped[bool] = mapped_column(default=False)
    scheduled_for: Mapped[datetime | None] = mapped_column(nullable=True)
    consumption_type: Mapped[str] = mapped_column(default="dine_in")

    # Mesas/comandas
    table_id: Mapped[int | None] = mapped_column(ForeignKey("tables.id", ondelete="SET NULL"), nullable=True)
    # ✅ CORREÇÃO APLICADA AQUI
    table: Mapped[Optional["Tables"]] = relationship(back_populates="orders")

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

    coupon_usage: Mapped["CouponUsage"] = relationship(back_populates="order")

    review_request_sent_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
        doc="Timestamp de quando a solicitação de avaliação foi enviada."
    )

    # ✅ ADICIONE ESTE NOVO CAMPO
    stuck_alert_sent_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
        doc="Timestamp de quando o alerta de pedido preso foi enviado."
    )

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

    # ✅ CORREÇÃO 1: Adicionando a relação de volta para o Pedido
    order: Mapped["Order"] = relationship(back_populates="products")

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

    # ✅ ADICIONE ESTA COLUNA OBRIGATÓRIA
    category_id: Mapped[int] = mapped_column(ForeignKey("categories.id"), nullable=False)

    # ✅ E ADICIONE O RELACIONAMENTO (RECOMENDADO)
    category: Mapped["Category"] = relationship()

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

    # ✅ CORREÇÃO 1: Adicionando a relação de volta
    order_product: Mapped["OrderProduct"] = relationship(back_populates="variants")

    variant_id: Mapped[int] = mapped_column(
        ForeignKey("variants.id", ondelete="SET NULL"),
        nullable=True
    )

    store_id: Mapped[int] = mapped_column(ForeignKey("stores.id"))

    name: Mapped[str] = mapped_column()

    options: Mapped[List["OrderVariantOption"]] = relationship(back_populates="order_variant")


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
    # ✅ CORREÇÃO 1: Adicionando a relação de volta
    order_variant: Mapped["OrderVariant"] = relationship(back_populates="options")

    store_id: Mapped[int] = mapped_column(ForeignKey("stores.id"))

    name: Mapped[str] = mapped_column()
    price: Mapped[int] = mapped_column()
    quantity: Mapped[int] = mapped_column()


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





class Saloon(Base, TimestampMixin):
    __tablename__ = "saloons"

    id: Mapped[int] = mapped_column(primary_key=True)
    store_id: Mapped[int] = mapped_column(ForeignKey("stores.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    display_order: Mapped[int] = mapped_column(Integer, default=0)

    # Relacionamentos
    store: Mapped["Store"] = relationship(back_populates="saloons")
    tables: Mapped[list["Tables"]] = relationship(
        back_populates="saloon",
        cascade="all, delete-orphan",
        order_by="asc(Tables.name)"  # Ordena as mesas pelo nome
    )

    __table_args__ = (
        UniqueConstraint('store_id', 'name', name='uq_store_saloon_name'),
    )



class Tables(Base, TimestampMixin):
    __tablename__ = "tables"
    __table_args__ = (
        CheckConstraint("max_capacity > 0", name="check_max_capacity_positive"),
        Index("idx_table_store", "store_id", "status"),
        UniqueConstraint('saloon_id', 'name', name='uq_saloon_table_name'),  # ✅ Garante nome único da mesa por salão
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    store_id: Mapped[int] = mapped_column(ForeignKey("stores.id", ondelete="CASCADE"))
    # ✅ NOVO CAMPO: Chave estrangeira para o Salão
    saloon_id: Mapped[int] = mapped_column(ForeignKey("saloons.id", ondelete="CASCADE"), nullable=False, index=True)

    name: Mapped[str] = mapped_column(String(50))

    status: Mapped[TableStatus] = mapped_column(
        Enum(TableStatus, native_enum=True),  # <-- ALTERADO PARA True
        default=TableStatus.AVAILABLE,
        server_default=TableStatus.AVAILABLE.value  # Opcional, mas bom: define o padrão no DB
    )

    max_capacity: Mapped[int] = mapped_column(default=4)
    current_capacity: Mapped[int] = mapped_column(default=0)
    opened_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    closed_at: Mapped[datetime | None] = mapped_column(nullable=True)
    is_deleted: Mapped[bool] = mapped_column(default=False)
    deleted_at: Mapped[datetime | None] = mapped_column(nullable=True)
    location_description: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # ✅ NOVO RELACIONAMENTO: Mesa para Salão
    saloon: Mapped["Saloon"] = relationship(back_populates="tables")

    # Relacionamento com Order (já estava correto)
    orders: Mapped[list["Order"]] = relationship(back_populates="table")

    # ✅ back_populates corrigido para "table"
    commands: Mapped[list["Command"]] = relationship(back_populates="table")

    # ✅ back_populates corrigido para "table"
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
        Enum(CommandStatus, native_enum=True), # <-- ALTERADO PARA True
        default=CommandStatus.ACTIVE,
        server_default=CommandStatus.ACTIVE.value
    )
    attendant_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    notes: Mapped[str | None] = mapped_column(String(500), nullable=True)  # Observações especiais


    table: Mapped["Tables | None"] = relationship(back_populates="commands")

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

    # ✅ Relacionamento corrigido
    table: Mapped["Tables"] = relationship(back_populates="history")
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

    # ✅ CORREÇÃO APLICADA AQUI
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"), nullable=False)

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
    status: Mapped[str] = mapped_column(index=True)  # ex: "active", "past_due", "canceled"
    current_period_start: Mapped[datetime] = mapped_column()
    current_period_end: Mapped[datetime] = mapped_column(index=True)
    gateway_subscription_id: Mapped[str | None] = mapped_column(nullable=True)  # Preço do plano em CENTAVOS
    # Relacionamento com o plano principal assinado
    plan: Mapped["Plans"] = relationship(back_populates="subscriptions")
    # ✅ ADIÇÃO
    monthly_charges: Mapped[list["MonthlyCharge"]] = relationship(back_populates="subscription")
    # NOVO: Relacionamento para ver todos os add-ons contratados nesta assinatura
    subscribed_addons: Mapped[list["PlansAddon"]] = relationship(
        back_populates="store_subscription",
        cascade="all, delete-orphan"
    )


class Plans(Base, TimestampMixin):
    __tablename__ = "plans"

    id: Mapped[int] = mapped_column(primary_key=True)
    plan_name: Mapped[str] = mapped_column()
    available: Mapped[bool] = mapped_column(default=True)
    support_type: Mapped[str | None] = mapped_column(nullable=True)

    # ✅ NOSSA ESTRUTURA DE PREÇOS DIFERENCIADA
    minimum_fee: Mapped[int] = mapped_column(default=2990)  # R$ 29,90
    revenue_percentage: Mapped[Decimal] = mapped_column(Numeric(5, 4), default=Decimal('0.029'))  # 2.9%
    revenue_cap_fee: Mapped[int | None] = mapped_column(default=19900)  # R$ 199,00
    percentage_tier_start: Mapped[int | None] = mapped_column(default=110000)  # R$ 1.100,00
    percentage_tier_end: Mapped[int | None] = mapped_column(default=700000)  # R$ 7.000,00

    # ✅ NOSSOS DIFERENCIAIS EXCLUSIVOS
    first_month_free: Mapped[bool] = mapped_column(default=True)
    second_month_discount: Mapped[Decimal] = mapped_column(Numeric(3, 2), default=Decimal('0.50'))  # 50%
    third_month_discount: Mapped[Decimal] = mapped_column(Numeric(3, 2), default=Decimal('0.75'))  # 25%

    # ✅ CORREÇÃO APLICADA AQUI
    included_features: Mapped[List["PlansFeature"]] = relationship(back_populates="plan")
    subscriptions: Mapped[List["StoreSubscription"]] = relationship(back_populates="plan")


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
    created_at: Mapped[datetime] = mapped_column(default=func.now(timezone.utc))

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
    # ✅ CORREÇÃO APLICADA AQUI
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"))
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
    status: Mapped[CartStatus] = mapped_column(Enum(CartStatus, native_enum=False), index=True,
                                               default=CartStatus.ACTIVE)

    # Campos que podem ser definidos antes do checkout
    coupon_id: Mapped[int | None] = mapped_column(ForeignKey("coupons.id"), nullable=True)
    coupon_code: Mapped[str | None] = mapped_column(nullable=True)
    observation: Mapped[str | None] = mapped_column(nullable=True)

    recovery_notified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
        doc="Timestamp de quando a notificação de recuperação foi enviada."
    )

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

    # ✅ ADICIONE ESTA COLUNA OBRIGATÓRIA
    category_id: Mapped[int] = mapped_column(ForeignKey("categories.id"), nullable=False)

    # ✅ E ADICIONE O RELACIONAMENTO (OPCIONAL, MAS RECOMENDADO)
    category: Mapped["Category"] = relationship()

    variants: Mapped[list["CartItemVariant"]] = relationship(
        back_populates="cart_item",
        cascade="all, delete-orphan"
    )

    # ✅ --- CAMPO FINGERPRINT ADICIONADO --- ✅
    fingerprint: Mapped[str] = mapped_column(index=True,
                                             doc="Hash único da configuração do item (produto + variantes) para evitar duplicatas.")


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
    category: Mapped[Optional["MasterCategory"]] = relationship(back_populates="master_products")

    @hybrid_property
    def image_path(self):
        return f"{S3_PUBLIC_BASE_URL}/{self.file_key}" if self.file_key else None

    __table_args__ = (
        Index("ix_master_products_name", "name"),
    )


class MasterCategory(Base):
    __tablename__ = "master_categories"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(80), unique=True)

    # Relacionamento reverso
    master_products: Mapped[List["MasterProduct"]] = relationship(back_populates="category")


class ChatbotMessage(Base, TimestampMixin):
    __tablename__ = "chatbot_messages"

    id: Mapped[int] = mapped_column(primary_key=True)
    store_id: Mapped[int] = mapped_column(ForeignKey("stores.id", ondelete="CASCADE"), index=True)

    # Identificadores da mensagem
    message_uid: Mapped[str] = mapped_column(String(255), unique=True, index=True,
                                             doc="ID único da mensagem do WhatsApp para evitar duplicatas")
    chat_id: Mapped[str] = mapped_column(String(100), index=True, doc="ID do chat (ex: 5531..._@_s.whatsapp.net)")
    sender_id: Mapped[str] = mapped_column(String(100), doc="Quem enviou (pode ser o cliente ou o número da loja)")

    # Conteúdo da mensagem
    content_type: Mapped[str] = mapped_column(String(20), default="text")  # 'text', 'image', 'audio'
    text_content: Mapped[str | None] = mapped_column(Text, nullable=True)
    media_url: Mapped[str | None] = mapped_column(String(1024), nullable=True, doc="URL do arquivo de mídia no S3")
    media_mime_type: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # Metadados
    is_from_me: Mapped[bool] = mapped_column(Boolean, doc="True se foi a loja/bot que enviou, False se foi o cliente")
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True,
                                                doc="Timestamp original da mensagem do WhatsApp")

    # Relacionamento (opcional, mas bom)
    store: Mapped["Store"] = relationship()


class ChatbotConversationMetadata(Base, TimestampMixin):
    __tablename__ = "chatbot_conversation_metadata"

    # Chave primária composta para garantir uma entrada por chat/loja
    chat_id: Mapped[str] = mapped_column(String(100), primary_key=True)
    store_id: Mapped[int] = mapped_column(ForeignKey("stores.id", ondelete="CASCADE"), primary_key=True)

    customer_name: Mapped[str | None] = mapped_column(String(100))
    last_message_preview: Mapped[str | None] = mapped_column(Text)
    last_message_timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    customer_profile_pic_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)

    # O campo mágico para o nosso controle
    unread_count: Mapped[int] = mapped_column(default=0)

    store: Mapped["Store"] = relationship()


# ✅ DEPOIS (CORRETO):
class MonthlyCharge(Base, TimestampMixin):
    __tablename__ = "monthly_charges"

    id: Mapped[int] = mapped_column(primary_key=True)
    store_id: Mapped[int] = mapped_column(ForeignKey("stores.id"), index=True)
    subscription_id: Mapped[int] = mapped_column(ForeignKey("store_subscriptions.id"))

    charge_date: Mapped[date] = mapped_column(Date)
    billing_period_start: Mapped[date] = mapped_column(Date)
    billing_period_end: Mapped[date] = mapped_column(Date)

    total_revenue: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    calculated_fee: Mapped[Decimal] = mapped_column(Numeric(10, 2))

    status: Mapped[str] = mapped_column(default="pending", index=True)
    gateway_transaction_id: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # ✅ CORRETO: Renomeado para 'charge_metadata'
    charge_metadata: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # Relacionamentos
    store: Mapped["Store"] = relationship(back_populates="monthly_charges")
    subscription: Mapped["StoreSubscription"] = relationship(back_populates="monthly_charges")

    # ✅ ÍNDICES OTIMIZADOS
    __table_args__ = (
        Index('ix_monthly_charges_status', 'status'),
        Index('ix_monthly_charges_store_period', 'store_id', 'billing_period_start'),
        Index('ix_monthly_charges_gateway_id', 'gateway_transaction_id'),
        Index('ix_monthly_charges_gateway_status', 'gateway_transaction_id', 'status'),
        UniqueConstraint('store_id', 'billing_period_start', 'billing_period_end',
                         name='uq_store_billing_period'),
    )