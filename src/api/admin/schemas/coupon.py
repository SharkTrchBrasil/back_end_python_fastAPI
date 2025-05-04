from datetime import datetime

from pydantic import BaseModel

from src.api.admin.schemas.product import Product


class CouponBase(BaseModel):
    code: str
    discount_percent: int | None
    discount_fixed: int | None
    max_uses: int | None = None
    start_date: datetime
    end_date: datetime


    #new campos
    maxUsesPerCustomer: int | None = None
    minOrderValue: int | None = None
    available: bool
    onlyNewCustomers: bool


class CouponCreate(CouponBase):
    product_id: int | None


class Coupon(CouponBase):
    id: int
    used: int
    product: Product | None = None


class CouponUpdate(CouponBase):
    discount_percent: int | None = None
    discount_fixed: int | None = None

    max_uses: int | None = None

    start_date: datetime | None = None
    end_date: datetime | None = None
    product_id: int | None = None


    #mew campos
    maxUsesPerCustomer: int | None = None
    minOrderValue: int | None = None
    available: bool
    onlyNewCustomers: bool
