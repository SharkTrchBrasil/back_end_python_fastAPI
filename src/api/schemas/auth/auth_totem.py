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


class AuthenticateByUrlRequest(BaseModel):
    store_url: str = Field(..., min_length=3, max_length=50, pattern=r'^[a-z0-9-]+$')
    totem_token: str # Agora é obrigatório para o novo fluxo


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
# ✅ SCHEMA DE RESPOSTA ATUALIZADO E CORRIGIDO
# ===================================================================

class SecureMenuAuthResponse(BaseModel):
    """
    Resposta segura e completa para a autenticação do cardápio.
    Contém os tokens JWT para o cliente e o token de conexão para o WebSocket.
    """
    # --- ✅ 1. TOKEN DE CONEXÃO ADICIONADO ---
    connection_token: str = Field(
        ...,
        description="Token de uso único e curta duração para a conexão WebSocket."
    )

    # Tokens JWT para autenticação do cliente
    access_token: str = Field(..., description="Token JWT de acesso (curta duração)")
    refresh_token: str = Field(..., description="Token JWT para renovar o access_token")
    token_type: str = Field(default="bearer", description="Tipo do token (sempre 'bearer')")
    expires_in: int = Field(..., description="Tempo de expiração do access_token em segundos")

    # Dados da loja
    store_id: int = Field(..., description="ID da loja no banco de dados")
    store_url: str = Field(..., description="Slug da loja (usado na URL)")
    store_name: str = Field(..., description="Nome da loja para exibição")

    # Metadados opcionais
    allowed_domains: Optional[list[str]] = Field(default=None, description="Lista de domínios autorizados")

    class Config:
        json_schema_extra = {
            "example": {
                "connection_token": "vN_8a..._secure_nonce_..._for_websocket",
                "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                "token_type": "bearer",
                "expires_in": 1800,
                "store_id": 123,
                "store_url": "topburguer",
                "store_name": "Top Burguer",
                "allowed_domains": ["https://topburguer.menuhub.com.br"]
            }
        }


# ===================================================================
# SCHEMAS PARA REFRESH E VALIDAÇÃO (mantidos)
# ============================

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