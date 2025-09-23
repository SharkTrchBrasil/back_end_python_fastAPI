from pydantic import BaseModel, Field


class ReviewCreate(BaseModel):
    stars: int = Field(..., ge=1, le=5) # Garante que as estrelas sejam entre 1 e 5
    comment: str | None = None