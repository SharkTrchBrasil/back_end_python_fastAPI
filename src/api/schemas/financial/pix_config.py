from pydantic import BaseModel


class StorePixConfig(BaseModel):
    pix_key: str
    client_id: str
    client_secret: str
    certificate: bytes