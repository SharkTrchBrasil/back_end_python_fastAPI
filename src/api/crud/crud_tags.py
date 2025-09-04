# src/api/crud/crud_tags.py
from sqlalchemy.orm import Session
from src.core import models

def get_all_tags(db):
    return db.query(models.FoodTag).order_by(models.FoodTag.name).all()