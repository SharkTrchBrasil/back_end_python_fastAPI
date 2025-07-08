from slugify import slugify

from src.core import models


def generate_unique_slug(db, name: str) -> str:
    base_slug = slugify(name, separator='')  # Sem traços
    slug = base_slug
    i = 1
    while db.query(models.TotemAuthorization).filter_by(store_url=slug).first():
        slug = f"{base_slug}{i}"
        i += 1
    return slug
