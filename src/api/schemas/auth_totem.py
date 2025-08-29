from typing import Optional

from pydantic import BaseModel

# TOTEM NORMAL
class TotemAuth(BaseModel):
    totem_token: str
    totem_name: str

class TotemCheckTokenResponse(BaseModel):
    granted: bool
    public_key: str
    store_id: int | None

#TOTEM NORMAL VIA QRCODE


# VIA URL PERSONALIZADA
class AuthenticateByUrlRequest(BaseModel):
    store_url: str # O slug que o Flutter extrai do subdomínio
    totem_token: Optional[str] = None # O token local do Flutter (pode ser nulo na primeira vez)


# Schema para a RESPOSTA COMPLETA do backend (o que o Flutter espera)
# Ele deve refletir o seu modelo de SQLAlchemy `TotemAuthorization`
class TotemAuthorizationResponse(BaseModel):
    id: int
    totem_token: str
    totem_name: str
    public_key: str # Este campo geralmente é para chaves de criptografia, pode ser o mesmo que totem_token se não usado
    store_id: int
    granted: bool
    granted_by_id: Optional[int] = None
    sid: Optional[str] = None
    store_url: str # A URL sem os traços (slug)

    class Config:
        from_attributes = True

class TotemTokenBySubdomainResponse(BaseModel):
    token: str
    store_id: int
    totem_name: str
    store_url: str




