# src/api/schemas/auth/auth_totem.py
from typing import Optional
from pydantic import BaseModel, Field


# ===================================================================
# SCHEMAS EXISTENTES (mantém como estão)
# ===================================================================

# TOTEM NORMAL
class TotemAuth(BaseModel):
    totem_token: str
    totem_name: str


class TotemCheckTokenResponse(BaseModel):
    granted: bool
    public_key: str
    store_id: int | None


# VIA URL PERSONALIZADA
class AuthenticateByUrlRequest(BaseModel):
    store_url: str = Field(
        ...,
        min_length=3,
        max_length=50,
        pattern=r'^[a-z0-9-]+$',
        description="Slug da loja (apenas letras minúsculas, números e hífen)"
    )
    totem_token: Optional[str] = None


# Schema para a RESPOSTA COMPLETA do backend (o que o Flutter espera)
class TotemAuthorizationResponse(BaseModel):
    id: int
    totem_token: str
    totem_name: str
    public_key: str
    store_id: int
    granted: bool
    granted_by_id: Optional[int] = None
    sid: Optional[str] = None
    store_url: str

    class Config:
        from_attributes = True


class TotemTokenBySubdomainResponse(BaseModel):
    token: str
    store_id: int
    totem_name: str
    store_url: str


# ===================================================================
# ✅ NOVO SCHEMA PARA AUTENTICAÇÃO SEGURA COM JWT
# ===================================================================

class SecureMenuAuthResponse(BaseModel):
    """
    Resposta segura de autenticação do cardápio com JWT

    Este schema substitui o TotemAuthorizationResponse para 
    autenticação baseada em JWT com tokens de acesso e refresh.
    """
    # Tokens JWT
    access_token: str = Field(
        ...,
        description="Token JWT de acesso (válido por 24h)"
    )
    refresh_token: str = Field(
        ...,
        description="Token JWT para renovar o access_token"
    )
    token_type: str = Field(
        default="bearer",
        description="Tipo do token (sempre 'bearer')"
    )
    expires_in: int = Field(
        ...,
        description="Tempo de expiração do access_token em segundos"
    )

    # Dados da loja
    store_id: int = Field(
        ...,
        description="ID da loja no banco de dados"
    )
    store_url: str = Field(
        ...,
        description="Slug da loja (usado na URL)"
    )
    store_name: str = Field(
        ...,
        description="Nome da loja para exibição"
    )

    # Metadados opcionais
    allowed_domains: Optional[list[str]] = Field(
        default=None,
        description="Lista de domínios autorizados para esta loja"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                "token_type": "bearer",
                "expires_in": 86400,
                "store_id": 123,
                "store_url": "topburguer",
                "store_name": "Top Burguer",
                "allowed_domains": [
                    "https://topburguer.menuhub.com.br",
                    "https://www.topburguer.com.br"
                ]
            }
        }


# ===================================================================
# SCHEMA PARA REFRESH TOKEN
# ===================================================================

class RefreshTokenRequest(BaseModel):
    """Request para renovar o access_token"""
    refresh_token: str = Field(
        ...,
        description="Token JWT de refresh recebido no login"
    )


class RefreshTokenResponse(BaseModel):
    """Resposta com novo access_token"""
    access_token: str = Field(
        ...,
        description="Novo token JWT de acesso"
    )
    token_type: str = Field(
        default="bearer",
        description="Tipo do token"
    )
    expires_in: int = Field(
        ...,
        description="Tempo de expiração em segundos"
    )


# ===================================================================
# SCHEMA PARA VALIDAÇÃO DE TOKEN (DEBUG)
# ===================================================================

class ValidateTokenRequest(BaseModel):
    """Request para validar um token JWT"""
    token: str = Field(
        ...,
        description="Token JWT a ser validado"
    )


class ValidateTokenResponse(BaseModel):
    """Resposta da validação de token"""
    valid: bool = Field(
        ...,
        description="Se o token é válido"
    )
    store_id: Optional[int] = Field(
        None,
        description="ID da loja (se token válido)"
    )
    store_url: Optional[str] = Field(
        None,
        description="Slug da loja (se token válido)"
    )
    expires_at: Optional[int] = Field(
        None,
        description="Timestamp de expiração (se token válido)"
    )
    error: Optional[str] = Field(
        None,
        description="Mensagem de erro (se token inválido)"
    )