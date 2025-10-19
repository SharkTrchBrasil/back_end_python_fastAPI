from __future__ import annotations
from decimal import Decimal

from sqlalchemy import JSON, Time, text, Date
from datetime import datetime, date, timezone
from typing import Optional, List

from sqlalchemy import DateTime, func, Index, LargeBinary, UniqueConstraint, CheckConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import DeclarativeBase

from src.core.aws import S3_PUBLIC_BASE_URL

from src.core.security.encryption import encryption_service
from src.core.utils.enums import CashbackType, TableStatus, CommandStatus, StoreVerificationStatus, PaymentMethodType, \
    CartStatus, ProductType, OrderStatus, PayableStatus, ThemeMode, CategoryType, FoodTagEnum, AvailabilityTypeEnum, \
    BeverageTagEnum, PricingStrategyType, CategoryTemplateType, OptionGroupType, ProductStatus, ChatbotMessageGroupEnum
from src.api.schemas.shared.base import VariantType, UIDisplayMode

from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy import Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
import uuid
from sqlalchemy import Column, Integer, ForeignKey, String, Enum, Numeric, Boolean
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

    subscriptions: Mapped[list["StoreSubscription"]] = relationship(
        "StoreSubscription",
        back_populates="store",
        lazy="select",
        cascade="all, delete-orphan",
        order_by="desc(StoreSubscription.created_at)"  # ✅ Mais recente primeiro
    )

    @hybrid_property
    def active_subscription(self) -> Optional["StoreSubscription"]:
        """
        ✅ CORRIGIDO: Retorna apenas assinatura ATIVA ou EM TRIAL
        """
        active_statuses = {'active', 'trialing'}
        for sub in self.subscriptions:
            if sub.status in active_statuses:
                return sub
        return None

    @hybrid_property
    def latest_subscription(self) -> Optional["StoreSubscription"]:
        """
        ✅ NOVO: Retorna a assinatura mais recente (qualquer status)
        Útil para acessar histórico de assinatura cancelada
        """
        return self.subscriptions[0] if self.subscriptions else None



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

    __table_args__ = (
        # Índice para lojas ativas por verificação
        Index(
            'idx_stores_active_verification',
            is_active,
            verification_status,
            postgresql_where=text('is_active = true')
        ),
        # Índice para busca case-insensitive por URL
        Index(
            'idx_stores_url_slug_lower',
            text('LOWER(url_slug)'),
            unique=True
        ),
        # Índice composto para filtro por segmento
        Index(
            'idx_stores_segment_active',
            segment_id,
            is_active,
            postgresql_where=text('is_active = true')
        ),
        # Índice para busca por CNPJ (já existe unique, mas adiciona performance)
        Index(
            'idx_stores_cnpj_active',
            cnpj,
            is_active,
            postgresql_where=text('cnpj IS NOT NULL')
        ),
    )


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

    __table_args__ = (
        # Índice para email case-insensitive
        Index(
            'idx_users_email_lower',
            text('LOWER(email)'),
            unique=True
        ),
        # Índice para telefone ativo
        Index(
            'idx_users_phone_active',
            phone,
            is_active,
            postgresql_where=text('is_active = true')
        ),
        # Índice para código de referência
        Index(
            'idx_users_referral_code',
            referral_code,
            unique=True,
            postgresql_where=text('referral_code IS NOT NULL')
        ),
    )


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

    __table_args__ = (
        Index("ix_store_user", "store_id", "user_id"),
        # Índice para usuário e loja
        Index(
            'idx_store_access_user_store',
            user_id,
            store_id,
            unique=True
        ),
        # Índice para loja e role
        Index(
            'idx_store_access_store_role',
            store_id,
            role_id
        ),
    )


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

    __table_args__ = (
        # Índice para categorias por loja, tipo e prioridade
        Index(
            'idx_categories_store_type_priority',
            store_id,
            type,
            priority
        ),
    )


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


    __table_args__ = (
        Index('idx_products_store_active', 'store_id', 'status'),
        # Índice para produtos por loja, status e prioridade
        Index(
            'idx_products_store_status_priority',
            store_id,
            status,
            priority,
            postgresql_where=text("status != 'ARCHIVED'")
        ),
        # Índice full-text search para nome do produto
        Index(
            'idx_products_search_name',
            text("to_tsvector('portuguese', name)"),
            postgresql_using='gin'
        ),
        # Índice para produtos por loja e tipo
        Index(
            'idx_products_store_type',
            store_id,
            product_type,
            status
        ),
    )

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



    __table_args__ = (
        Index('idx_product_category_link_category', 'category_id', 'product_id'),
        # Índice composto para links de categoria de produto
        Index(
            'idx_product_category_links_composite',
            category_id,
            product_id,
            is_available,
            postgresql_where=text('is_available = true')
        ),
        # Índice para produto e categoria
        Index(
            'idx_product_category_product_store',
            product_id,
            category_id
        ),
    )

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

    __table_args__ = (
        Index('idx_variants_store_type', 'store_id', 'type'),
    )


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
        Index('idx_variant_options_variant_store', 'variant_id', 'store_id'),
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

    __table_args__ = (
        Index('idx_coupons_store_active', 'store_id', 'is_active'),
        Index('idx_coupons_date_range', 'start_date', 'end_date', 'is_active'),
    )


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

    __table_args__ = (
        Index('idx_coupon_rules_coupon_type', 'coupon_id', 'rule_type'),
    )


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

    __table_args__ = (
        Index('idx_coupon_usages_customer_coupon', 'customer_id', 'coupon_id'),
        Index('idx_coupon_usages_used_at', 'used_at'),
    )


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

    __table_args__ = (
        Index('idx_totem_store_granted', 'store_id', 'granted'),
    )


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


    __table_args__ = (
        Index('idx_sessions_user_type', 'user_id', 'client_type'),
        Index('idx_sessions_store', 'store_id'),
        Index('idx_sessions_user_type_active', 'user_id', 'client_type', 'sid'),
        Index('idx_sessions_store_active', 'store_id', 'created_at'),
        Index('idx_sessions_sid_unique', 'sid', unique=True),
    )

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

    # ✅ ADICIONAR:
    __table_args__ = (
        Index('idx_customer_sessions_store', 'store_id'),
        Index('idx_customer_sessions_customer', 'customer_id'),
        Index('idx_customer_sessions_store_customer', 'store_id', 'customer_id'),
    )


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
        Index('idx_chatbot_messages_store_template', 'store_id', 'template_key', 'is_active'),
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

    __table_args__ = (
        Index('idx_chatbot_config_store_active', 'store_id', 'is_active', unique=True),
    )


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

    __table_args__ = (
        Index('idx_platform_methods_group_type', 'group_id', 'method_type'),
    )


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

    __table_args__ = (
        Index('idx_payment_activations_store_method', 'store_id', 'platform_payment_method_id'),
        Index('idx_payment_activations_store_active', 'store_id', 'is_active'),
    )


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

    __table_args__ = (
        Index('idx_store_hours_store_day', 'store_id', 'day_of_week', 'is_active'),
    )


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

    __table_args__ = (
        Index('idx_store_cities_store_active', 'store_id', 'is_active'),
    )


class StoreNeighborhood(Base, TimestampMixin):
    __tablename__ = "store_neighborhoods"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column()

    city_id: Mapped[int] = mapped_column(ForeignKey("store_cities.id", ondelete="CASCADE"))

    delivery_fee: Mapped[int] = mapped_column(default=0)
    free_delivery: Mapped[bool] = mapped_column(default=False)
    is_active: Mapped[bool] = mapped_column(default=True)

    city: Mapped["StoreCity"] = relationship("StoreCity", back_populates="neighborhoods")

    __table_args__ = (
        Index('idx_neighborhoods_city_active', 'city_id', 'is_active'),
    )


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

    __table_args__ = (
        Index('idx_payable_categories_store', 'store_id'),
    )


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

    __table_args__ = (
        Index('idx_suppliers_store_document', 'store_id', 'document'),
    )


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

    __table_args__ = (
        Index('idx_payable_recurrences_original', 'original_payable_id'),
        Index('idx_payable_recurrences_dates', 'start_date', 'end_date'),
    )


class StorePayable(Base, TimestampMixin):
    __tablename__ = "store_payables"

    id: Mapped[int] = mapped_column(primary_key=True)
    store_id: Mapped[int] = mapped_column(ForeignKey("stores.id", ondelete="CASCADE"))
    store: Mapped["Store"] = relationship(back_populates="payables")

    # Categoria da conta (ex: "Aluguel", "Energia", "Impostos")
    category_id: Mapped[int] = mapped_column(ForeignKey("payable_categories.id"))
    category: Mapped["PayableCategory"] = relationship(back_populates="payables")

    # Fornecedor (opcional)
    supplier_id: Mapped[int | None] = mapped_column(ForeignKey("suppliers.id"))
    supplier: Mapped["Supplier"] = relationship(back_populates="payables")

    # Informações da conta
    description: Mapped[str] = mapped_column()
    amount: Mapped[int] = mapped_column()  # Em centavos
    due_date: Mapped[date] = mapped_column()
    payment_status: Mapped[str] = mapped_column(String(50), default='pending')  # 'pending', 'paid', 'overdue'

    # Data de pagamento real (quando pago)
    paid_at: Mapped[datetime | None] = mapped_column()
    paid_amount: Mapped[int | None] = mapped_column()  # Pode ser diferente do valor original (juros/descontos)

    # Recorrência (opcional)
    parent_recurrence_id: Mapped[int | None] = mapped_column(ForeignKey("payable_recurrences.id"))
    parent_recurrence: Mapped["PayableRecurrence"] = relationship(
        back_populates="generated_payables",
        foreign_keys=[parent_recurrence_id]
    )

    # ✅ ADIÇÃO: Relacionamento para a recorrência que esta conta pode gerar
    recurrence: Mapped["PayableRecurrence"] = relationship(
        back_populates="original_payable",
        foreign_keys="[PayableRecurrence.original_payable_id]",
        uselist=False
    )

    __table_args__ = (
        Index('idx_store_payables_store_status', 'store_id', 'payment_status'),
        Index('idx_store_payables_due_date', 'due_date'),
        Index('idx_store_payables_category', 'category_id'),
        Index('idx_store_payables_supplier', 'supplier_id'),
    )


class Saloon(Base, TimestampMixin):
    __tablename__ = "saloons"

    id: Mapped[int] = mapped_column(primary_key=True)
    store_id: Mapped[int] = mapped_column(ForeignKey("stores.id", ondelete="CASCADE"))
    store: Mapped["Store"] = relationship(back_populates="saloons")

    name: Mapped[str] = mapped_column()
    description: Mapped[str | None] = mapped_column()
    is_active: Mapped[bool] = mapped_column(default=True)

    tables: Mapped[list["Tables"]] = relationship(back_populates="saloon")

    __table_args__ = (
        Index('idx_saloons_store_active', 'store_id'),
    )


class Tables(Base, TimestampMixin):
    __tablename__ = "tables"

    id: Mapped[int] = mapped_column(primary_key=True)
    store_id: Mapped[int] = mapped_column(ForeignKey("stores.id", ondelete="CASCADE"))
    store: Mapped["Store"] = relationship(back_populates="tables")

    saloon_id: Mapped[int] = mapped_column(ForeignKey("saloons.id", ondelete="CASCADE"))
    saloon: Mapped["Saloon"] = relationship(back_populates="tables")

    name: Mapped[str] = mapped_column()
    capacity: Mapped[int] = mapped_column()
    status: Mapped[str] = mapped_column(String(50), default='available')  # 'available', 'occupied', 'reserved'
    qr_code: Mapped[str | None] = mapped_column(unique=True)

    __table_args__ = (
        Index('idx_tables_store_saloon_status', 'store_id', 'saloon_id', 'status'),
    )


class MonthlyCharge(Base, TimestampMixin):
    __tablename__ = "monthly_charges"

    id: Mapped[int] = mapped_column(primary_key=True)
    store_id: Mapped[int] = mapped_column(ForeignKey("stores.id", ondelete="CASCADE"))
    store: Mapped["Store"] = relationship(back_populates="monthly_charges")

    billing_period: Mapped[str] = mapped_column()  # Formato: 'YYYY-MM'
    amount: Mapped[int] = mapped_column()  # Em centavos
    due_date: Mapped[date] = mapped_column()
    payment_status: Mapped[str] = mapped_column(String(50), default='pending')  # 'pending', 'paid', 'overdue'
    paid_at: Mapped[datetime | None] = mapped_column()

    __table_args__ = (
        Index('idx_monthly_charges_period_store', 'billing_period', 'store_id', 'payment_status'),
        Index('idx_monthly_charges_pending', 'payment_status', 'due_date'),
        Index('idx_monthly_charges_store_date', 'store_id', 'created_at'),
    )



class ProcessedWebhookEvent(Base, TimestampMixin):
    """
    Registra eventos de webhook já processados para garantir idempotência.

    Evita que o mesmo evento seja processado múltiplas vezes caso
    o webhook seja chamado mais de uma vez com o mesmo payload.
    """
    __tablename__ = "processed_webhook_events"

    id: Mapped[int] = mapped_column(primary_key=True)

    # ID único do evento fornecido pelo gateway
    event_id: Mapped[str] = mapped_column(
        String(100),
        unique=True,
        index=True,
        nullable=False,
        doc="ID único do evento fornecido pelo gateway de pagamento"
    )

    # Tipo do evento (charge.paid, charge.refunded, etc)
    event_type: Mapped[str] = mapped_column(
        String(50),
        index=True,
        nullable=False,
        doc="Tipo do evento (ex: charge.paid, charge.refunded)"
    )

    # Payload completo do evento (para auditoria)
    payload: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
        doc="Payload completo do webhook (para auditoria)"
    )

    # Quando foi processado
    processed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        doc="Momento em que o evento foi processado"
    )

    # ✅ Índice composto para busca rápida
    __table_args__ = (
        Index('ix_processed_events_lookup', 'event_id', 'event_type'),
        Index('ix_processed_events_date', 'processed_at'),
    )

    def __repr__(self) -> str:
        return (
            f"<ProcessedWebhookEvent(id={self.id}, "
            f"event_id='{self.event_id}', "
            f"event_type='{self.event_type}', "
            f"processed_at={self.processed_at})>"
        )