from src.api.admin.schemas.category import Category
from src.api.admin.schemas.coupon import Coupon
from src.api.admin.schemas.payment_method import StorePaymentMethods
from src.api.admin.schemas.product import Product
from src.api.admin.schemas.store import Store


class FullStoreData(Store):
    categories: list[Category]
    coupons: list[Coupon]
    payment_methods: list[StorePaymentMethods]
    products: list[Product]
