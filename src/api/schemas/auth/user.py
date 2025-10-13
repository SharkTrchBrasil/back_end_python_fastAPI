# Em schemas/user.py
import re
from typing import Optional
from datetime import date
from pydantic import BaseModel, Field, ConfigDict, EmailStr, validator, field_validator


class UserSchema(BaseModel):
    id: int
    email: str
    name: str
    phone: str | None = None
    cpf: str | None = None
    birth_date: date | None = None


    is_store_owner: bool = Field(
        description="Indica se o usuário é proprietário de loja ou funcionário"
    )
    is_superuser: bool
    referral_code: str
    model_config = ConfigDict(from_attributes=True)



class UserCreate(BaseModel):
    email: str
    name: str = Field(..., min_length=3)
    phone: str
    password: str = Field(..., min_length=8)


    referral_code: str | None = None


# --- Schema de Atualização (Entrada da API) ---
# O que o Flutter envia no wizard para atualizar o perfil do responsável
class UserUpdate(BaseModel):
    name: str | None = Field(None, min_length=3)
    phone: str | None = None


    cpf: str | None = None
    birth_date: date | None = None  # A API espera receber no formato "AAAA-MM-DD"


# --- Outros Schemas (sem alteração) ---
class ChangePasswordData(BaseModel):
    old_password: str
    new_password: str = Field(..., min_length=8)


class ResendEmail(BaseModel):
    email: str


# ✅ NOVO SCHEMA PARA ESTA ROTA
class GrantStoreAccessRequest(BaseModel):
    """Schema para conceder/atualizar acesso de um usuário existente à loja."""
    user_email: EmailStr
    role_machine_name: str


class CreateStoreUserRequest(BaseModel):
    """
    Schema para criação de um novo usuário vinculado a uma loja.

    Attributes:
        name: Nome completo do usuário (mín. 3 caracteres)
        email: E-mail válido e único no sistema
        phone: Telefone com 10 ou 11 dígitos
        password: Senha com no mínimo 6 caracteres
        role_machine_name: Nome técnico da função (ex: 'manager', 'cashier')
    """

    name: str = Field(
        ...,
        min_length=3,
        max_length=100,
        description="Nome completo do usuário",
        examples=["João Silva", "Maria Santos"]
    )

    email: EmailStr = Field(
        ...,
        description="E-mail válido e único",
        examples=["joao.silva@example.com"]
    )

    phone: str = Field(
        ...,
        min_length=10,
        max_length=15,
        description="Telefone com DDD (10 ou 11 dígitos)",
        examples=["11987654321", "(11) 98765-4321"]
    )

    password: str = Field(
        ...,
        min_length=6,
        description="Senha com no mínimo 6 caracteres",
        examples=["senhaSegura123"]
    )

    role_machine_name: str = Field(
        ...,
        description="Nome técnico da função",
        examples=["manager", "cashier", "waiter", "stock_manager"]
    )

    @field_validator('phone')
    @classmethod
    def validate_phone(cls, v: str) -> str:
        """Valida e normaliza o telefone."""
        # Remove tudo que não for número
        phone_clean = re.sub(r'\D', '', v)

        # Valida comprimento
        if len(phone_clean) < 10 or len(phone_clean) > 11:
            raise ValueError('Telefone deve ter 10 ou 11 dígitos')

        return phone_clean  # ✅ RETORNA O TELEFONE LIMPO

    @field_validator('password')
    @classmethod
    def validate_password(cls, v: str) -> str:
        """Valida o comprimento mínimo da senha."""
        if len(v) < 6:
            raise ValueError('Senha deve ter no mínimo 6 caracteres')
        return v

    @field_validator('name')
    @classmethod
    def validate_name(cls, v: str) -> str:
        """Remove espaços extras do nome."""
        name_clean = v.strip()
        if len(name_clean) < 3:
            raise ValueError('Nome deve ter no mínimo 3 caracteres')
        return name_clean

    @field_validator('role_machine_name')
    @classmethod
    def validate_role(cls, v: str) -> str:
        """Valida se a role está na lista permitida."""
        allowed_roles = ['manager', 'cashier', 'waiter', 'stock_manager']
        if v not in allowed_roles:
            raise ValueError(
                f"Role '{v}' não é permitida. "
                f"Roles permitidas: {', '.join(allowed_roles)}"
            )
        return v

