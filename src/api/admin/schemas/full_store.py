from src.core.models import Store, Category, Coupon, Product, StorePaymentMethods


class FullStoreData(Store):
    categories: list[Category]
    coupons: list[Coupon]
    payment_methods: list[StorePaymentMethods]
    products: list[Product]
