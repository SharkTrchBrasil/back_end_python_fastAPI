from src.core import models


def generate_unique_slug(db, base_slug: str) -> str:
    slug = base_slug
    i = 1
    while db.query(models.TotemAuthorization).filter_by(store_url=slug.replace('-', '')).first():
        slug = f"{base_slug}-{i}"
        i += 1
    return slug.replace('-', '')