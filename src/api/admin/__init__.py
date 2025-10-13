from fastapi import APIRouter

from src.api.admin.routes.stores import router as stores_router
from src.api.admin.routes.products import router as products_router
from src.api.admin.routes.users import router as users_router
from src.api.admin.routes.auth import router as auth_router
from src.api.admin.routes.categories import router as categories_router
from src.api.admin.routes.variants import router as variants_router
from src.api.admin.routes.variant_options import router as options_router
from src.api.admin.routes.coupons import router as coupons_router
from src.api.admin.routes.totems import router as totems_router
from src.api.admin.routes.themes import router as themes_router
from src.api.admin.routes.pix_configs import router as pix_configs_router
from src.api.admin.webhooks.pix_webhook import router as webhook_router
from src.api.admin.routes.store_city import router as city_router
from src.api.admin.routes.store_neighborhood import router as neighborhood_router
from src.api.admin.routes.store_payable import router as payables_router
from src.api.admin.routes.store_customer import router as customers_router




from src.api.admin.routes.payment_methods import router as payment_methods_router
from src.api.admin.routes.store_hours import router as store_hours_router
from src.api.admin.routes.verify_email import router as verify_email_router

from src.api.admin.routes.store_operation_config import router as delivery_options_router

from src.api.admin.routes.cashier_session_routes import router as cashier_session_routes
from src.api.admin.routes.cashier_transaction_routes import router as  cashier_transaction_routes
from src.api.admin.routes.banners import router as banners_router
from src.api.admin.routes.store_ratings import router as store_ratings_router
from src.api.admin.routes.orders import router as orders_router
from src.api.admin.routes.store_customer import router as store_customer_router

from src.api.admin.routes.plans import router as plans_router
from src.api.admin.routes.subscriptions import router as subscriptions_router
from src.api.admin.routes.zipcode import router as zipcode_router
from src.api.admin.webhooks.subscription_webhook import router as master_webhook_router
from src.api.admin.routes.product_variants import router as product_variants_router
from src.api.admin.routes.segment import router as segments_router
from src.api.admin.routes.dashboard import router as dashboard_router
from src.api.admin.routes.partial_payment import router as partial_payment_router
from src.api.admin.routes.loyalty_routes import router as loyalty_router
from src.api.admin.routes.loyalty_customer_routes import router as loyalty_customer_router
from src.api.admin.routes.pauses import router as pauses_router
from src.api.admin.routes.holidays import router as holidays_router
from src.api.admin.routes.supplier_router import router as supplier_router
from src.api.admin.routes.payable_category_router import router as payable_category_router
from src.api.admin.routes.receivable_router import router as receivable_router
from src.api.admin.routes.receivable_category_router import router as receivable_category_router
from src.api.admin.routes.performance_router import router as performance_router
from src.api.admin.routes.master_products import router as master_products_router
from src.api.admin.routes.product_category_link import router as product_category_link_router
from src.api.admin.routes.table import router as table_router
from src.api.admin.routes.chatbot_api import router as chatbot_api_router
from src.api.admin.routes.chatbot_config import router as chatbot_config_router
# ✅ 1. IMPORTE OS DOIS ROUTERS DO MÓDULO 'categories'
from src.api.admin.routes.categories import router as categories_router, nested_router as categories_nested_router
from src.api.admin.routes.import_menu import router as import_menu_router
from src.api.admin.routes.sessions import router as sessions_router
router = APIRouter(prefix="/admin")
router.include_router(stores_router)
router.include_router(products_router)
router.include_router(users_router)
router.include_router(auth_router)
router.include_router(categories_router)
router.include_router(variants_router)
router.include_router(options_router)

router.include_router(coupons_router)
router.include_router(totems_router)
router.include_router(themes_router)
router.include_router(pix_configs_router)
router.include_router(webhook_router)

router.include_router(plans_router)
router.include_router(subscriptions_router)
router.include_router(zipcode_router)

router.include_router(payment_methods_router)
router.include_router(store_hours_router)

router.include_router(verify_email_router)



router.include_router(delivery_options_router)

router.include_router(city_router)
router.include_router(neighborhood_router)
router.include_router(payables_router)


router.include_router(cashier_session_routes)
router.include_router(cashier_transaction_routes)
router.include_router(banners_router)
router.include_router(store_ratings_router)

router.include_router(orders_router)



router.include_router(store_customer_router)

router.include_router(master_webhook_router)
router.include_router(product_variants_router)
router.include_router(segments_router)
router.include_router(dashboard_router)
router.include_router(partial_payment_router)
router.include_router(loyalty_router)
router.include_router(loyalty_customer_router)
router.include_router(pauses_router)
router.include_router(holidays_router)
router.include_router(supplier_router)
router.include_router(payable_category_router)
router.include_router(receivable_router)
router.include_router(receivable_category_router)
router.include_router(performance_router)
router.include_router(master_products_router)
router.include_router(product_category_link_router)
router.include_router(table_router)
router.include_router(chatbot_api_router)
router.include_router(chatbot_config_router)
router.include_router(categories_nested_router)
router.include_router(import_menu_router)
router.include_router(sessions_router)